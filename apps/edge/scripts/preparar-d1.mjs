/**
 * Garante que a base de dados D1 existe na conta Cloudflare e escreve o seu
 * identificador em wrangler.jsonc, só na cópia de trabalho do workflow de
 * implantação. O identificador não é segredo, mas assim o repositório não
 * depende de uma conta concreta e a primeira implantação não exige passos
 * manuais.
 *
 * Uso (com CLOUDFLARE_API_TOKEN e CLOUDFLARE_ACCOUNT_ID definidos):
 *   node apps/edge/scripts/preparar-d1.mjs
 */

import { execFileSync } from "node:child_process";
import { readFile, writeFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const RAIZ_EDGE = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const CONFIG = path.join(RAIZ_EDGE, "wrangler.jsonc");
const NOME = "intercalares-eua-2026";
const MARCADOR = "00000000-0000-0000-0000-000000000000";

function wrangler(...argumentos) {
  return execFileSync("pnpm", ["exec", "wrangler", ...argumentos], {
    cwd: RAIZ_EDGE,
    encoding: "utf-8",
    env: { ...process.env, WRANGLER_SEND_METRICS: "false" },
    stdio: ["ignore", "pipe", "inherit"],
  });
}

function procurar() {
  const saida = wrangler("d1", "list", "--json");
  // O wrangler pode escrever avisos antes do JSON; lê a partir do primeiro "[".
  const lista = JSON.parse(saida.slice(saida.indexOf("[")));
  return lista.find((b) => b.name === NOME)?.uuid ?? null;
}

let id = procurar();
if (id === null) {
  console.log(`A criar a base de dados D1 ${NOME} (plano gratuito).`);
  wrangler("d1", "create", NOME);
  id = procurar();
}
if (id === null) throw new Error(`Não foi possível encontrar nem criar a base de dados ${NOME}.`);

const config = await readFile(CONFIG, "utf-8");
if (!config.includes(MARCADOR)) {
  console.log("O wrangler.jsonc já tem um database_id; nada a alterar.");
} else {
  await writeFile(CONFIG, config.replace(MARCADOR, id));
  console.log(`Base de dados D1 ${NOME}: ${id}`);
}
