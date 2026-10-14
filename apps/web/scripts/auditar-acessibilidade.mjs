/**
 * Auditoria automática de acessibilidade e estabilidade do site exportado (apps/web/out).
 *
 * Para cada página e cada combinação de largura (1280 e 320 px) e tema (claro e escuro):
 * - corre o axe-core com as regras WCAG 2.0/2.1 A e AA e as boas práticas;
 * - confirma que há exatamente um h1 e nenhum deslocamento horizontal;
 * - mede o deslocamento cumulativo do esquema (CLS) até a página estabilizar.
 *
 * Uso (depois de `pnpm build`):
 *   pnpm --filter @intercalares/web auditar
 *   CAMINHO_CHROMIUM=/caminho/para/chrome  usa um Chromium já instalado.
 *
 * Exceção documentada em docs/acessibilidade.md: o axe junta os <text> de um SVG sem
 * espaços e marca "label-content-name-mismatch" nas linhas interativas dos gráficos,
 * cujo nome já começa pelo rótulo visível e inclui todos os valores mostrados.
 */

// O código dentro de evaluate e addInitScript corre no navegador.
/* global window, document */

import { readdir, readFile } from "node:fs/promises";
import { createRequire } from "node:module";
import path from "node:path";
import { chromium } from "playwright-core";
import { RAIZ, servir } from "./servidor-estatico.mjs";

const AXE = await readFile(createRequire(import.meta.url).resolve("axe-core/axe.min.js"), "utf8");
const PAGINAS = [
  "/",
  "/mapa/",
  "/previsao/",
  "/previsao/camara/",
  "/previsao/senado/",
  "/previsao/cenarios/",
  "/demografia/",
  "/sondagens/",
  "/resultados/",
  "/voto-antecipado/",
  "/metodologia/",
  "/sistema/",
  "/404.html",
];
const CONFIGURACOES = [
  { nome: "computador claro", largura: 1280, esquema: "light" },
  { nome: "computador escuro", largura: 1280, esquema: "dark" },
  { nome: "telemóvel claro", largura: 320, esquema: "light" },
  { nome: "telemóvel escuro", largura: 320, esquema: "dark" },
];
const LIMITE_CLS = 0.1;

/** Subpáginas de uma secção (estados, corridas), lidas da pasta exportada. */
async function subpaginas(seccao) {
  try {
    const entradas = await readdir(path.join(RAIZ, seccao), { withFileTypes: true });
    return entradas.filter((e) => e.isDirectory()).map((e) => `/${seccao}/${e.name}/`);
  } catch {
    return [];
  }
}

function excecaoDocumentada(regra, no) {
  return regra === "label-content-name-mismatch" && no.html.startsWith("<g ");
}

const { servidor, base } = await servir();
const navegador = await chromium.launch(
  process.env.CAMINHO_CHROMIUM ? { executablePath: process.env.CAMINHO_CHROMIUM } : {},
);
const paginas = [
  ...PAGINAS,
  ...(await subpaginas("voto-antecipado")),
  ...(await subpaginas("metodologia")),
  // Uma corrida basta: as páginas das sondagens partilham o mesmo modelo.
  ...(await subpaginas("sondagens")).slice(0, 1),
];
let problemas = 0;

for (const configuracao of CONFIGURACOES) {
  const contexto = await navegador.newContext({
    viewport: { width: configuracao.largura, height: 800 },
    colorScheme: configuracao.esquema,
  });
  await contexto.addInitScript(() => {
    window.__cls = 0;
    new PerformanceObserver((lista) => {
      for (const entrada of lista.getEntries()) {
        if (!entrada.hadRecentInput) window.__cls += entrada.value;
      }
    }).observe({ type: "layout-shift", buffered: true });
  });
  for (const endereco of paginas) {
    const pagina = await contexto.newPage();
    await pagina.goto(base + endereco, { waitUntil: "networkidle" });
    await pagina.waitForTimeout(500);
    await pagina.addScriptTag({ content: AXE });
    const resultado = await pagina.evaluate(async () => {
      const axe = await window.axe.run(document, {
        runOnly: {
          type: "tag",
          values: ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "best-practice"],
        },
      });
      return {
        violacoes: axe.violations.map((v) => ({
          id: v.id,
          ajuda: v.help,
          nos: v.nodes.map((n) => ({ alvo: n.target.join(" "), html: n.html })),
        })),
        h1: document.querySelectorAll("h1").length,
        larguraExcedente: document.documentElement.scrollWidth > window.innerWidth,
        cls: window.__cls,
      };
    });
    const falhas = [];
    for (const v of resultado.violacoes) {
      const nos = v.nos.filter((n) => !excecaoDocumentada(v.id, n));
      if (nos.length > 0) falhas.push(`${v.id}: ${v.ajuda} (${nos[0].alvo})`);
    }
    if (resultado.h1 !== 1) falhas.push(`${String(resultado.h1)} títulos h1 (esperado: 1)`);
    if (resultado.larguraExcedente) falhas.push("deslocamento horizontal");
    if (resultado.cls > LIMITE_CLS) falhas.push(`CLS ${resultado.cls.toFixed(3)}`);
    const estado = falhas.length === 0 ? "ok" : "FALHA";
    console.log(
      `${estado.padEnd(5)} ${configuracao.nome.padEnd(17)} ${endereco} (CLS ${resultado.cls.toFixed(3)})`,
    );
    for (const falha of falhas) console.log(`      ${falha}`);
    problemas += falhas.length;
    await pagina.close();
  }
  await contexto.close();
}

await navegador.close();
servidor.close();
if (problemas > 0) {
  console.error(`\n${String(problemas)} problema(s) encontrados.`);
  process.exitCode = 1;
}
