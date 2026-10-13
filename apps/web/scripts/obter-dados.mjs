/**
 * Descarrega os agregados publicados pelo pipeline para apps/web/dados/, antes
 * do build. Por omissão lista a Release pública fixa do repositório e obtém
 * cada ficheiro de estado (`nc.json`, `ga.json`, ...). Uma variável de ambiente
 * permite indicar outras origens, separadas por vírgulas (endereços ou
 * ficheiros locais).
 *
 * Uso: pnpm --filter @intercalares/web dados:obter
 *   URL_DADOS_VOTO_ANTECIPADO=https://.../nc.json,caminho/local/ga.json
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
const REPOSITORIO = "tpereira2005/intercalares-eua-2026";
const ETIQUETA = "dados-voto-antecipado";
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

async function obterUm(origem) {
  const nome = path.basename(new URL(origem, "file:///").pathname);
  if (!NOME_ESTADO.test(nome)) throw new Error(`${origem} não tem nome de estado (xx.json)`);
  const destino = path.join(PASTA, nome);
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
}

try {
  await obter();
} catch (erro) {
  console.warn(`Sem dados do voto antecipado (${String(erro)}); as páginas ficam em preparação.`);
}
