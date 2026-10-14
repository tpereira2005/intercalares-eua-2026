/**
 * Testes de fluxos do site exportado (apps/web/out), com o teclado e num Chromium real.
 *
 * Fluxos:
 *  1. navegação do início a cada secção só com o teclado;
 *  2. voto antecipado de um estado: controlos de comparação e gráficos que se atualizam;
 *  3. cenários da previsão: barra deslizante com as setas e "Repor a previsão publicada";
 *  4. resultados sem API (o servidor estático responde 404 a /api/*);
 *  5. alternância entre tema claro e escuro (e persistência);
 *  6. indicador de foco visível em todas as paragens do teclado.
 *
 * Uso (depois de `pnpm build`):
 *   pnpm --filter @intercalares/web fluxos
 *   CAMINHO_CHROMIUM=/caminho/para/chrome  usa um Chromium já instalado
 *   (por omissão: /opt/pw-browsers/chromium).
 */

// O código dentro de evaluate corre no navegador.
/* global window, document, getComputedStyle */

import { existsSync } from "node:fs";
import { chromium } from "playwright-core";
import { RAIZ, servir } from "./servidor-estatico.mjs";

const CAMINHO_CHROMIUM = process.env.CAMINHO_CHROMIUM ?? "/opt/pw-browsers/chromium";
const LIMITE_ESPERA = 5000;
/** Secções principais da navegação, pela ordem em que aparecem. */
const SECCOES = [
  "/voto-antecipado/",
  "/demografia/",
  "/mapa/",
  "/previsao/",
  "/sondagens/",
  "/resultados/",
  "/metodologia/",
];

/** Falha de um passo, com a mensagem que aparece no relatório. */
class Falha extends Error {}

function exigir(condicao, mensagem) {
  if (!condicao) throw new Falha(mensagem);
}

/** Passo a passo da paragem do teclado até ao elemento pedido. */
async function tabularAte(pagina, seletor, maximo = 80) {
  for (let i = 0; i < maximo; i += 1) {
    await pagina.keyboard.press("Tab");
    const chegou = await pagina.evaluate(
      (s) => document.activeElement?.matches(s) ?? false,
      seletor,
    );
    if (chegou) return i + 1;
  }
  throw new Falha(`o teclado não chegou a "${seletor}" em ${String(maximo)} paragens`);
}

async function esperarPor(pagina, funcao, argumento, mensagem) {
  try {
    await pagina.waitForFunction(funcao, argumento, { timeout: LIMITE_ESPERA });
  } catch {
    throw new Falha(mensagem);
  }
}

/* ---------- Fluxo 1: navegação por teclado ---------- */

async function fluxoNavegacao({ abrir }) {
  const pagina = await abrir("/");
  await pagina.keyboard.press("Tab");
  const primeira = await pagina.evaluate(() => document.activeElement?.getAttribute("href"));
  exigir(
    primeira?.startsWith("#") === true,
    `a primeira paragem do teclado devia ser a ligação "Saltar para o conteúdo", mas foi ${String(primeira)}`,
  );
  for (const destino of SECCOES) {
    await pagina.goto(new URL("/", pagina.url()).href, { waitUntil: "networkidle" });
    const seletor = `nav a[href="${destino}"]`;
    exigir(
      (await pagina.locator(seletor).count()) === 1,
      `a navegação não tem a ligação para ${destino}`,
    );
    await tabularAte(pagina, seletor);
    await pagina.keyboard.press("Enter");
    try {
      await pagina.waitForURL((u) => u.pathname === destino, { timeout: LIMITE_ESPERA });
    } catch {
      throw new Falha(`Enter na ligação ${destino} não abriu a página (URL: ${pagina.url()})`);
    }
    await pagina.waitForLoadState("networkidle");
    const h1 = await pagina.locator("main h1, h1").count();
    exigir(h1 === 1, `${destino} tem ${String(h1)} títulos h1 (esperado: 1)`);
    const atual = await pagina.locator(`nav a[href="${destino}"]`).getAttribute("aria-current");
    exigir(atual === "page", `${destino} não ficou marcada com aria-current="page" na navegação`);
  }
}

/* ---------- Fluxo 2: voto antecipado de um estado ---------- */

async function premirComTeclado(localizador, tecla = "Space") {
  await localizador.focus();
  await localizador.press(tecla);
}

async function fluxoVotoAntecipado({ abrir, estadoVoto }) {
  const pagina = await abrir(`/voto-antecipado/${estadoVoto}/`);
  const comparar = pagina.getByRole("group", { name: "Comparar com" });
  const botoes = comparar.getByRole("button");
  exigir((await botoes.count()) >= 2, "o grupo 'Comparar com' devia ter pelo menos dois anos");
  const linhas = pagina.locator('svg g[role="button"]');
  exigir((await linhas.count()) > 0, "o gráfico de composição não tem linhas interativas");
  const antes = await linhas.first().getAttribute("aria-label");
  const anoAntes = /\b(20\d\d)\b/.exec(antes ?? "")?.[1];
  exigir(anoAntes !== undefined, `o nome da primeira linha não indica o ano comparado: "${antes}"`);

  const outro = botoes.filter({ hasNotText: anoAntes }).first();
  const anoOutro = (await outro.innerText()).trim();
  await premirComTeclado(outro);
  exigir(
    (await outro.getAttribute("aria-pressed")) === "true",
    `o botão "${anoOutro}" não ficou ativo depois de Espaço`,
  );
  await esperarPor(
    pagina,
    (ano) =>
      document.querySelector('svg g[role="button"]')?.getAttribute("aria-label")?.includes(ano) ===
      true,
    anoOutro,
    `o gráfico não passou a comparar com ${anoOutro}`,
  );

  // Muda a pergunta: o gráfico principal tem de mudar.
  const tituloAntes = await pagina.locator("svg[role='group']").first().getAttribute("aria-label");
  const pergunta = pagina.getByRole("group", { name: "Pergunta" }).getByRole("button");
  exigir((await pergunta.count()) >= 2, "o grupo 'Pergunta' devia ter pelo menos duas opções");
  await premirComTeclado(pergunta.nth(1), "Enter");
  exigir(
    (await pergunta.nth(1).getAttribute("aria-pressed")) === "true",
    "a segunda pergunta não ficou ativa depois de Enter",
  );
  await esperarPor(
    pagina,
    (anterior) =>
      document.querySelector("svg[role='group']")?.getAttribute("aria-label") !== anterior,
    tituloAntes,
    "o gráfico principal não mudou ao mudar a pergunta",
  );

  // Escolher uma faixa numa linha do gráfico com Enter fica refletido no estado da linha.
  const linha = pagina.locator('svg g[role="button"]').nth(1);
  await premirComTeclado(linha, "Enter");
  exigir(
    (await linha.getAttribute("aria-pressed")) === "true",
    "a linha escolhida com Enter não ficou com aria-pressed=true",
  );
}

/* ---------- Fluxo 3: cenários da previsão ---------- */

async function fluxoCenarios({ abrir }) {
  const pagina = await abrir("/previsao/cenarios/");
  const cartoes = pagina.locator("[aria-live='polite']").first();
  const barra = pagina.locator('input[type="range"]');
  const repor = pagina.getByRole("button", { name: "Repor a previsão publicada" });
  const inicial = await cartoes.innerText();
  const valorInicial = await barra.inputValue();
  exigir(await repor.isDisabled(), "'Repor a previsão publicada' devia estar desativado no início");

  await barra.focus();
  for (let i = 0; i < 4; i += 1) await barra.press("ArrowRight");
  const depois = await barra.inputValue();
  exigir(depois !== valorInicial, "as setas não mudaram o valor da barra deslizante");
  const alterado = await cartoes.innerText();
  exigir(
    alterado !== inicial,
    "os cartões da Câmara e do Senado não mudaram depois de mover a barra com as setas",
  );
  exigir(
    /Câmara/.test(alterado) && /Senado/.test(alterado),
    "os cartões já não mostram a Câmara e o Senado",
  );

  await barra.press("ArrowLeft");
  exigir(
    (await barra.inputValue()) !== depois,
    "a seta para a esquerda não recuou a barra deslizante",
  );
  await barra.press("End");
  const maximo = await barra.inputValue();
  exigir(maximo === (await barra.getAttribute("max")), "a tecla Fim não levou a barra ao extremo");

  // Erro das sondagens: as setas movem o botão de opção escolhido.
  const radios = pagina.locator('input[type="radio"]');
  const marcadoAntes = await radios.evaluateAll((l) => l.findIndex((r) => r.checked));
  await radios.nth(marcadoAntes).focus();
  await pagina.keyboard.press("ArrowRight");
  const marcadoDepois = await radios.evaluateAll((l) => l.findIndex((r) => r.checked));
  exigir(marcadoDepois !== marcadoAntes, "as setas não mudaram o erro das sondagens escolhido");

  exigir(await repor.isEnabled(), "'Repor a previsão publicada' devia estar ativo após alterações");
  await premirComTeclado(repor, "Enter");
  exigir(
    (await barra.inputValue()) === valorInicial,
    "'Repor a previsão publicada' não devolveu a barra à posição inicial",
  );
  exigir(
    (await radios.evaluateAll((l) => l.findIndex((r) => r.checked))) === marcadoAntes,
    "'Repor a previsão publicada' não repôs o erro das sondagens",
  );
  exigir(
    (await cartoes.innerText()) === inicial,
    "depois de repor, os cartões não voltaram à previsão publicada",
  );
  exigir(
    await repor.isDisabled(),
    "'Repor a previsão publicada' devia ficar desativado após repor",
  );
}

/* ---------- Fluxo 4: resultados sem API ---------- */

async function fluxoResultadosSemApi({ contexto, base }) {
  const pagina = await contexto.newPage();
  const erros = [];
  const pedidosApi = [];
  pagina.on("pageerror", (e) => erros.push(`erro de script: ${e.message}`));
  pagina.on("response", (r) => {
    if (new URL(r.url()).pathname.startsWith("/api/")) pedidosApi.push(r.status());
  });
  pagina.on("console", (m) => {
    // Os 404 da API são o cenário do teste; qualquer outro erro conta.
    if (m.type() === "error" && !/status of 404/.test(m.text())) erros.push(m.text());
  });
  await pagina.goto(`${base}/resultados/`, { waitUntil: "networkidle" });
  await pagina.waitForTimeout(800);
  exigir(
    pedidosApi.length > 0,
    "a página de resultados não pediu nada a /api/* (o fluxo sem API não foi exercitado)",
  );
  exigir(
    pedidosApi.every((s) => s === 404),
    `/api/* devia responder 404 no servidor estático, mas respondeu ${pedidosApi.join(", ")}`,
  );
  exigir(erros.length === 0, `a página de resultados deu erros sem API: ${erros.join(" | ")}`);
  exigir((await pagina.locator("h1").count()) === 1, "a página de resultados perdeu o título h1");
  const texto = await pagina.locator("main").innerText();
  exigir(texto.trim().length > 100, "a página de resultados ficou vazia sem API");
  exigir(
    (await pagina.locator("nextjs-portal, #__next-build-watcher").count()) === 0,
    "apareceu a janela de erro do Next em /resultados/",
  );
  await pagina.close();
}

/* ---------- Fluxo 5: tema claro e escuro ---------- */

async function fluxoTema({ abrir }) {
  const pagina = await abrir("/");
  const fundo = () => pagina.evaluate(() => getComputedStyle(document.body).backgroundColor);
  const tema = () => pagina.evaluate(() => document.documentElement.getAttribute("data-theme"));
  const grupo = pagina.getByRole("group", { name: "Tema visual" });

  await premirComTeclado(grupo.getByRole("button", { name: "Claro" }), "Enter");
  exigir((await tema()) === "light", "o tema 'Claro' não pôs data-theme=light");
  const claro = await fundo();
  await premirComTeclado(grupo.getByRole("button", { name: "Escuro" }), "Enter");
  exigir((await tema()) === "dark", "o tema 'Escuro' não pôs data-theme=dark");
  const escuro = await fundo();
  exigir(claro !== escuro, "o fundo da página não mudou entre o tema claro e o escuro");
  exigir(
    (await grupo.getByRole("button", { name: "Escuro" }).getAttribute("aria-pressed")) === "true",
    "o botão 'Escuro' não ficou com aria-pressed=true",
  );

  await pagina.reload({ waitUntil: "networkidle" });
  exigir((await tema()) === "dark", "o tema escuro não se manteve depois de recarregar a página");
  await premirComTeclado(grupo.getByRole("button", { name: "Claro" }), "Enter");
  exigir(
    (await tema()) === "light" && (await fundo()) === claro,
    "voltar ao tema claro não repôs o fundo claro",
  );
}

/* ---------- Fluxo 6: foco visível ---------- */

async function fluxoFocoVisivel({ abrir, estadoVoto }) {
  for (const endereco of [
    "/",
    `/voto-antecipado/${estadoVoto}/`,
    "/mapa/",
    "/previsao/cenarios/",
    "/resultados/",
  ]) {
    const pagina = await abrir(endereco);
    const semFoco = [];
    let paragens = 0;
    for (let i = 0; i < 250; i += 1) {
      await pagina.keyboard.press("Tab");
      const estado = await pagina.evaluate(() => {
        const el = document.activeElement;
        if (!el || el === document.body) return null;
        const visivel = (e) => {
          const c = getComputedStyle(e);
          return c.outlineStyle !== "none" && parseFloat(c.outlineWidth) > 0;
        };
        const nome =
          el.tagName.toLowerCase() +
          (el.getAttribute("aria-label") ?? el.textContent ?? "").trim().slice(0, 40);
        if (el instanceof window.SVGElement) {
          const fundo = el.querySelector("rect");
          const traco = fundo ? getComputedStyle(fundo) : null;
          const ok =
            visivel(el) ||
            (traco !== null &&
              traco.stroke !== "none" &&
              traco.stroke !== "rgba(0, 0, 0, 0)" &&
              parseFloat(traco.strokeWidth) > 0);
          return { nome, ok };
        }
        const alvo = el.matches("input.sr-only") ? el.closest("label") : el;
        return { nome, ok: visivel(el) || (alvo !== null && visivel(alvo)) };
      });
      if (estado === null) break;
      paragens += 1;
      if (!estado.ok) semFoco.push(estado.nome);
    }
    exigir(paragens > 3, `${endereco}: o teclado só tem ${String(paragens)} paragens`);
    exigir(
      semFoco.length === 0,
      `${endereco}: sem indicador de foco visível em ${semFoco.slice(0, 3).join("; ")}`,
    );
    await pagina.close();
  }
}

/* ---------- Execução ---------- */

if (!existsSync(RAIZ)) {
  console.error(`Não existe ${RAIZ}. Corre primeiro \`pnpm build\`.`);
  process.exit(1);
}
if (!existsSync(CAMINHO_CHROMIUM)) {
  console.error(
    `Chromium não encontrado em ${CAMINHO_CHROMIUM}. Indica o caminho em CAMINHO_CHROMIUM.`,
  );
  process.exit(1);
}

const { servidor, base } = await servir();
const navegador = await chromium.launch({ executablePath: CAMINHO_CHROMIUM });
const estadoVoto = "nc";
const FLUXOS = [
  ["Navegação do início a cada secção só com o teclado", fluxoNavegacao],
  ["Voto antecipado: controlos de comparação e gráficos", fluxoVotoAntecipado],
  ["Cenários: barra deslizante e repor a previsão", fluxoCenarios],
  ["Resultados sem API (404 em /api/*)", fluxoResultadosSemApi],
  ["Tema claro e escuro", fluxoTema],
  ["Indicador de foco visível", fluxoFocoVisivel],
];

let falhados = 0;
for (const [nome, fluxo] of FLUXOS) {
  const contexto = await navegador.newContext({
    viewport: { width: 1280, height: 900 },
    colorScheme: "light",
  });
  const abrir = async (endereco) => {
    const pagina = await contexto.newPage();
    await pagina.goto(base + endereco, { waitUntil: "networkidle" });
    return pagina;
  };
  try {
    await fluxo({ abrir, contexto, base, estadoVoto });
    console.log(`ok    ${nome}`);
  } catch (erro) {
    falhados += 1;
    const mensagem = erro instanceof Falha ? erro.message : `erro inesperado: ${String(erro)}`;
    console.log(`FALHA ${nome}\n      ${mensagem}`);
  }
  await contexto.close();
}

await navegador.close();
servidor.close();
if (falhados > 0) {
  console.error(`\n${String(falhados)} fluxo(s) falharam.`);
  process.exitCode = 1;
} else {
  console.log(`\n${String(FLUXOS.length)} fluxos ok.`);
}
