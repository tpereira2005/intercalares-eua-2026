/**
 * Descarrega os ficheiros publicados pelo pipeline para apps/web/dados/, antes
 * do build:
 * - voto antecipado: lista a Release pública `dados-voto-antecipado` e obtém
 *   cada ficheiro de estado (`nc.json`, `ga.json`, ...);
 * - previsão: `previsao-2026.json` e `historico-previsao-2026.json` da Release
 *   `dados-previsao`, gravados como dados/previsao/2026.json e historico-2026.json.
 * - sondagens: `sondagens-2026.json` da Release `dados-previsao`, gravado como
 *   dados/sondagens/2026.json;
 * - resultados: `parciais.json` da Release `resultados-2026` (contrato ResultadosParciais),
 *   gravado como dados/resultados/parciais.json;
 * - sinal etário: `idade-nc.json` da Release `dados-voto-antecipado` (contrato
 *   DiagnosticoIdade), gravado como dados/idade/nc.json; só existe a partir de 20 de outubro;
 * - projeção da noite: `projecao-noite-2026.json` e `historico-noite-2026.json` da Release
 *   `dados-noite`, gravados como dados/noite/projecao.json e historico.json.
 * Variáveis de ambiente permitem indicar outras origens (endereços ou ficheiros locais).
 *
 * Uso: pnpm --filter @intercalares/web dados:obter
 *   URL_DADOS_VOTO_ANTECIPADO=https://.../nc.json,caminho/local/ga.json
 *   URL_DADOS_PREVISAO=caminho/2026.json  URL_HISTORICO_PREVISAO=caminho/historico.json
 *   URL_DADOS_SONDAGENS=caminho/sondagens.json  URL_DADOS_RESULTADOS=caminho/parciais.json
 *   URL_PROJECAO_NOITE=caminho/projecao.json  URL_HISTORICO_NOITE=caminho/historico.json
 *   URL_IDADE_NC=caminho/idade-nc.json
 *   GITHUB_TOKEN (opcional) evita o limite de pedidos anónimos à API.
 *
 * Sem rede ou sem Release, o script avisa e termina sem erro: as páginas mostram
 * "em preparação". A validação contra o contrato é feita no build.
 */

import { copyFile, mkdir, rm, writeFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const RAIZ_WEB = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const PASTA = path.join(RAIZ_WEB, "dados", "voto-antecipado");
const PASTA_PREVISAO = path.join(RAIZ_WEB, "dados", "previsao");
const REPOSITORIO = "tpereira2005/intercalares-eua-2026";
const ETIQUETA = "dados-voto-antecipado";
const ETIQUETA_PREVISAO = "dados-previsao";
/** Ficheiro local, asset da Release e variável de ambiente de cada ficheiro da previsão. */
const FICHEIROS_PREVISAO = [
  { destino: "2026.json", asset: "previsao-2026.json", variavel: "URL_DADOS_PREVISAO" },
  {
    destino: "historico-2026.json",
    asset: "historico-previsao-2026.json",
    variavel: "URL_HISTORICO_PREVISAO",
  },
  { destino: "cenarios-2026.json", asset: "cenarios-2026.json", variavel: "URL_CENARIOS_PREVISAO" },
  {
    destino: "alteracoes-2026.json",
    asset: "alteracoes-2026.json",
    variavel: "URL_ALTERACOES_PREVISAO",
  },
];
const PASTA_RESULTADOS = path.join(RAIZ_WEB, "dados", "resultados");
const ETIQUETA_RESULTADOS = "resultados-2026";
const PASTA_NOITE = path.join(RAIZ_WEB, "dados", "noite");
const ETIQUETA_NOITE = "dados-noite";
const FICHEIROS_NOITE = [
  { destino: "projecao.json", asset: "projecao-noite-2026.json", variavel: "URL_PROJECAO_NOITE" },
  {
    destino: "historico.json",
    asset: "historico-noite-2026.json",
    variavel: "URL_HISTORICO_NOITE",
  },
];
const LIMITE_BYTES = 20 * 1024 * 1024;
const NOME_ESTADO = /^[a-z]{2}\.json$/;
const AGENTE = `Escrutinio/0.1 (+https://github.com/${REPOSITORIO})`;

async function pedir(url, cabecalhos = {}) {
  const resposta = await fetch(url, {
    headers: { "User-Agent": AGENTE, ...cabecalhos },
    redirect: "follow",
    signal: AbortSignal.timeout(60_000),
  });
  if (!resposta.ok) throw new Error(`${url} respondeu ${String(resposta.status)}`);
  return resposta;
}

/** Endereços de descarga dos ficheiros de estado publicados na Release. */
async function origensDaRelease() {
  const url = `https://api.github.com/repos/${REPOSITORIO}/releases/tags/${ETIQUETA}`;
  const base = { Accept: "application/vnd.github+json" };
  const token = process.env.GITHUB_TOKEN;
  let resposta;
  try {
    resposta = await pedir(url, token ? { ...base, Authorization: `Bearer ${token}` } : base);
  } catch (erro) {
    // Um token sem acesso à API (401) não deve impedir a leitura pública.
    if (!token) throw erro;
    resposta = await pedir(url, base);
  }
  const release = await resposta.json();
  return release.assets.filter((a) => NOME_ESTADO.test(a.name)).map((a) => a.browser_download_url);
}

/** Copia ou descarrega uma origem para `destino`, confirmando que é JSON e não é enorme. */
async function gravar(origem, destino) {
  if (!/^https?:\/\//.test(origem)) {
    await copyFile(path.resolve(origem), destino);
    return destino;
  }
  const corpo = Buffer.from(await (await pedir(origem)).arrayBuffer());
  if (corpo.length > LIMITE_BYTES) throw new Error(`${origem} tem mais de 20 MB`);
  JSON.parse(corpo.toString("utf-8"));
  await writeFile(destino, corpo);
  return destino;
}

async function obterUm(origem) {
  const nome = path.basename(new URL(origem, "file:///").pathname);
  if (!NOME_ESTADO.test(nome)) throw new Error(`${origem} não tem nome de estado (xx.json)`);
  return gravar(origem, path.join(PASTA, nome));
}

async function obterPrevisao() {
  // Pasta limpa: sem previsão publicada, a página volta a "em preparação".
  await rm(PASTA_PREVISAO, { recursive: true, force: true });
  await mkdir(PASTA_PREVISAO, { recursive: true });
  for (const { destino, asset, variavel } of FICHEIROS_PREVISAO) {
    const origem =
      process.env[variavel] ??
      `https://github.com/${REPOSITORIO}/releases/download/${ETIQUETA_PREVISAO}/${asset}`;
    try {
      const gravado = await gravar(origem, path.join(PASTA_PREVISAO, destino));
      console.log(`Previsão em ${path.relative(process.cwd(), gravado)}`);
    } catch (erro) {
      console.warn(`Sem ${asset} (${String(erro)}).`);
    }
  }
}

async function obterSondagens() {
  // Pasta limpa: sem sondagens publicadas, as páginas voltam a "em preparação".
  const pasta = path.join(RAIZ_WEB, "dados", "sondagens");
  await rm(pasta, { recursive: true, force: true });
  await mkdir(pasta, { recursive: true });
  const origem =
    process.env.URL_DADOS_SONDAGENS ??
    `https://github.com/${REPOSITORIO}/releases/download/${ETIQUETA_PREVISAO}/sondagens-2026.json`;
  try {
    const gravado = await gravar(origem, path.join(pasta, "2026.json"));
    console.log(`Sondagens em ${path.relative(process.cwd(), gravado)}`);
  } catch (erro) {
    console.warn(`Sem sondagens-2026.json (${String(erro)}).`);
  }
}

async function obterResultados() {
  // Pasta limpa: sem contagem publicada, a página volta a "em preparação".
  await rm(PASTA_RESULTADOS, { recursive: true, force: true });
  await mkdir(PASTA_RESULTADOS, { recursive: true });
  const origem =
    process.env.URL_DADOS_RESULTADOS ??
    `https://github.com/${REPOSITORIO}/releases/download/${ETIQUETA_RESULTADOS}/parciais.json`;
  try {
    const gravado = await gravar(origem, path.join(PASTA_RESULTADOS, "parciais.json"));
    console.log(`Resultados em ${path.relative(process.cwd(), gravado)}`);
  } catch (erro) {
    console.warn(`Sem parciais.json (${String(erro)}).`);
  }
  const chamadas =
    process.env.URL_CHAMADAS ??
    `https://github.com/${REPOSITORIO}/releases/download/${ETIQUETA_RESULTADOS}/chamadas-2026.json`;
  try {
    const gravado = await gravar(chamadas, path.join(PASTA_RESULTADOS, "chamadas.json"));
    console.log(`Chamadas em ${path.relative(process.cwd(), gravado)}`);
  } catch (erro) {
    console.warn(`Sem chamadas-2026.json (${String(erro)}).`);
  }
}

async function obterIdade() {
  // Pasta limpa: sem ficheiro publicado, a página diz que ainda é cedo.
  const pasta = path.join(RAIZ_WEB, "dados", "idade");
  await rm(pasta, { recursive: true, force: true });
  await mkdir(pasta, { recursive: true });
  const origem =
    process.env.URL_IDADE_NC ??
    `https://github.com/${REPOSITORIO}/releases/download/${ETIQUETA}/idade-nc.json`;
  try {
    const gravado = await gravar(origem, path.join(pasta, "nc.json"));
    console.log(`Sinal etário em ${path.relative(process.cwd(), gravado)}`);
  } catch (erro) {
    console.warn(`Sem idade-nc.json (${String(erro)}).`);
  }
}

async function obterNoite() {
  // Pasta limpa: sem projeção publicada, a página mostra só a contagem e a previsão.
  await rm(PASTA_NOITE, { recursive: true, force: true });
  await mkdir(PASTA_NOITE, { recursive: true });
  for (const { destino, asset, variavel } of FICHEIROS_NOITE) {
    const origem =
      process.env[variavel] ??
      `https://github.com/${REPOSITORIO}/releases/download/${ETIQUETA_NOITE}/${asset}`;
    try {
      const gravado = await gravar(origem, path.join(PASTA_NOITE, destino));
      console.log(`Projeção da noite em ${path.relative(process.cwd(), gravado)}`);
    } catch (erro) {
      console.warn(`Sem ${asset} (${String(erro)}).`);
    }
  }
}

async function obter() {
  const indicadas = process.env.URL_DADOS_VOTO_ANTECIPADO;
  const origens = indicadas
    ? indicadas
        .split(",")
        .map((o) => o.trim())
        .filter(Boolean)
    : await origensDaRelease().catch((erro) => {
        // Sem acesso à API (limite de pedidos, por exemplo), tenta pelo menos a Carolina do Norte.
        console.warn(`Não foi possível listar a Release (${String(erro)}).`);
        return [`https://github.com/${REPOSITORIO}/releases/download/${ETIQUETA}/nc.json`];
      });
  // Começa de uma pasta limpa: um estado retirado da Release não fica no site.
  await rm(PASTA, { recursive: true, force: true });
  await mkdir(PASTA, { recursive: true });
  for (const origem of origens) {
    try {
      const destino = await obterUm(origem);
      console.log(`Dados do voto antecipado em ${path.relative(process.cwd(), destino)}`);
    } catch (erro) {
      console.warn(`Sem dados de ${origem} (${String(erro)}).`);
    }
  }
  if (origens.length === 0) console.warn("A Release não tem ficheiros de estado.");
  // O resumo nacional diz que estados prioritários ficam de fora, e porquê.
  if (!indicadas) {
    const origem = `https://github.com/${REPOSITORIO}/releases/download/${ETIQUETA}/nacional.json`;
    try {
      await gravar(origem, path.join(PASTA, "nacional.json"));
      console.log("Resumo nacional do voto antecipado obtido.");
    } catch (erro) {
      console.warn(`Sem nacional.json (${String(erro)}).`);
    }
  }
}

try {
  await obter();
} catch (erro) {
  console.warn(`Sem dados do voto antecipado (${String(erro)}); as páginas ficam em preparação.`);
}

try {
  await obterIdade();
} catch (erro) {
  console.warn(`Sem sinal etário (${String(erro)}).`);
}

try {
  await obterPrevisao();
} catch (erro) {
  console.warn(`Sem previsão (${String(erro)}); a página fica em preparação.`);
}

try {
  await obterResultados();
} catch (erro) {
  console.warn(`Sem resultados (${String(erro)}); a página fica em preparação.`);
}

try {
  await obterNoite();
} catch (erro) {
  console.warn(`Sem projeção da noite (${String(erro)}).`);
}

try {
  await obterSondagens();
} catch (erro) {
  console.warn(`Sem sondagens (${String(erro)}); as páginas ficam em preparação.`);
}
