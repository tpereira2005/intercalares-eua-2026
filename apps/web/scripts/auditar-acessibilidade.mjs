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

import { createReadStream } from "node:fs";
import { readdir, readFile, stat } from "node:fs/promises";
import { createServer } from "node:http";
import { createRequire } from "node:module";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { chromium } from "playwright-core";

const RAIZ = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "out");
const AXE = await readFile(createRequire(import.meta.url).resolve("axe-core/axe.min.js"), "utf8");
const TIPOS = {
  ".html": "text/html; charset=utf-8",
  ".js": "text/javascript",
  ".css": "text/css",
  ".json": "application/json",
  ".svg": "image/svg+xml",
  ".woff2": "font/woff2",
  ".woff": "font/woff",
  ".txt": "text/plain; charset=utf-8",
};
const PAGINAS = [
  "/",
  "/mapa/",
  "/previsao/",
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

/** Servidor estático mínimo sobre a pasta exportada. */
function servir() {
  const servidor = createServer(async (pedido, resposta) => {
    const caminho = decodeURIComponent(new URL(pedido.url ?? "/", "http://x").pathname);
    let ficheiro = path.join(RAIZ, caminho);
    if (!ficheiro.startsWith(RAIZ)) {
      resposta.writeHead(403).end();
      return;
    }
    try {
      if ((await stat(ficheiro)).isDirectory()) ficheiro = path.join(ficheiro, "index.html");
      await stat(ficheiro);
    } catch {
      resposta.writeHead(404).end();
      return;
    }
    resposta.writeHead(200, {
      "Content-Type": TIPOS[path.extname(ficheiro)] ?? "application/octet-stream",
    });
    createReadStream(ficheiro).pipe(resposta);
  });
  return new Promise((resolver) => {
    servidor.listen(0, "127.0.0.1", () => {
      const endereco = servidor.address();
      resolver({ servidor, base: `http://127.0.0.1:${String(endereco.port)}` });
    });
  });
}

/** Páginas dos estados, lidas da pasta exportada. */
async function paginasEstados() {
  try {
    const entradas = await readdir(path.join(RAIZ, "voto-antecipado"), { withFileTypes: true });
    return entradas.filter((e) => e.isDirectory()).map((e) => `/voto-antecipado/${e.name}/`);
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
const paginas = [...PAGINAS, ...(await paginasEstados())];
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
