/**
 * Escreve wrangler.ensaio.json, a configuração do Worker de ensaio da noite eleitoral
 * (docs/teste-carga-noite.md, secção "Ensaio na Cloudflare"), a partir de wrangler.jsonc.
 *
 * O Worker de ensaio tem outro nome (`intercalares-eua-2026-ensaio`, no mesmo
 * subdomínio workers.dev e no plano gratuito), não tem cron nem base de dados D1 e lê os
 * ficheiros de uma Release de ensaio. Assim nada do ensaio toca no Worker de produção.
 *
 * Uso: node scripts/configurar-ensaio.mjs --etiqueta resultados-ensaio
 *   [--etiqueta-noite resultados-ensaio] [--ano-noite 2024] [--intervalo 60]
 *
 * O Modelo publica a projeção de ensaio na mesma Release, com o ano da noite reconstruída
 * no nome (`projecao-noite-2024.json`, `historico-noite-2024.json`).
 */

import { readFileSync, writeFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const RAIZ_EDGE = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
export const NOME_ENSAIO = "intercalares-eua-2026-ensaio";
const REPOSITORIO = "https://github.com/tpereira2005/intercalares-eua-2026";

/** Tira comentários e vírgulas finais de JSONC, respeitando o texto entre aspas. */
export function lerJsonc(texto) {
  let saida = "";
  let emTexto = false;
  for (let i = 0; i < texto.length; i++) {
    const c = texto[i];
    if (emTexto) {
      saida += c;
      if (c === "\\") saida += texto[++i] ?? "";
      else if (c === '"') emTexto = false;
    } else if (c === '"') {
      emTexto = true;
      saida += c;
    } else if (c === "/" && texto[i + 1] === "/") {
      while (i < texto.length && texto[i] !== "\n") i++;
      saida += "\n";
    } else if (c === "/" && texto[i + 1] === "*") {
      i = texto.indexOf("*/", i + 2) + 1;
    } else saida += c;
  }
  return JSON.parse(saida.replace(/,(\s*[}\]])/g, "$1"));
}

const ETIQUETA = /^[A-Za-z0-9._-]{1,64}$/;

export function configuracaoEnsaio(base, { etiqueta, etiquetaNoite, anoNoite, intervalo }) {
  for (const e of [etiqueta, etiquetaNoite]) {
    if (!ETIQUETA.test(e)) throw new Error(`Etiqueta inválida: ${e}`);
  }
  if (!/^20\d\d$/.test(String(anoNoite))) throw new Error(`Ano da noite inválido: ${anoNoite}`);
  if (etiqueta === "resultados-2026") throw new Error("O ensaio não lê a Release de produção");
  const url = (tag, ficheiro) => `${REPOSITORIO}/releases/download/${tag}/${ficheiro}`;
  const resto = { ...base };
  delete resto.d1_databases;
  return {
    ...resto,
    name: NOME_ENSAIO,
    triggers: { crons: [] },
    vars: {
      ...base.vars,
      AMBIENTE: "ensaio",
      INTERVALO_S: String(intervalo),
      URL_PARCIAIS: url(etiqueta, "parciais.json"),
      URL_CHAMADAS: url(etiqueta, "chamadas-2026.json"),
      URL_SAUDE: url(etiqueta, "saude.json"),
      URL_PROJECAO_NOITE: url(etiquetaNoite, `projecao-noite-${anoNoite}.json`),
      URL_HISTORICO_NOITE: url(etiquetaNoite, `historico-noite-${anoNoite}.json`),
    },
  };
}

function argumento(nome, omissao) {
  const i = process.argv.indexOf(`--${nome}`);
  return i >= 0 ? (process.argv[i + 1] ?? omissao) : omissao;
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  const base = lerJsonc(readFileSync(path.join(RAIZ_EDGE, "wrangler.jsonc"), "utf-8"));
  const config = configuracaoEnsaio(base, {
    etiqueta: argumento("etiqueta", "resultados-ensaio"),
    etiquetaNoite: argumento("etiqueta-noite", "resultados-ensaio"),
    anoNoite: argumento("ano-noite", "2024"),
    intervalo: Number(argumento("intervalo", "60")),
  });
  const destino = path.join(RAIZ_EDGE, "wrangler.ensaio.json");
  writeFileSync(destino, `${JSON.stringify(config, null, 2)}\n`);
  console.log(`Escrito ${destino} (${config.name}, ${config.vars.URL_PARCIAIS})`);
}
