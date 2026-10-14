/**
 * Gera o código dos validadores dos contratos usados pela API ao vivo.
 *
 * Os Workers não permitem `eval` nem `new Function`, por isso o ajv não pode compilar
 * esquemas em tempo de execução. Este script compila-os aqui, com o mesmo esquema que o
 * site usa no build (schemas/json/contratos.schema.json), e escreve o código resultante
 * em src/gerado/validadores.js. O teste validadores.test.ts falha se estiver desatualizado.
 *
 * Uso: pnpm --filter @intercalares/edge validadores:gerar
 */

import { readFile, writeFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import Ajv2020 from "ajv/dist/2020.js";
import standaloneCode from "ajv/dist/standalone/index.js";
import adicionarFormatos from "ajv-formats";

const RAIZ_EDGE = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const ESQUEMA = path.resolve(RAIZ_EDGE, "../../schemas/json/contratos.schema.json");
export const DESTINO = path.join(RAIZ_EDGE, "src/gerado/validadores.js");
export const CONTRATOS = ["ResultadosParciais", "ProjecaoNoite", "HistoricoNoite"];

/** Cópia de ajv/dist/runtime/ucs2length.js (comprimento em pontos de código). */
const UCS2LENGTH = `function ucs2length(str) {
  const len = str.length;
  let length = 0;
  let pos = 0;
  let value;
  while (pos < len) {
    length++;
    value = str.charCodeAt(pos++);
    if (value >= 0xd800 && value <= 0xdbff && pos < len) {
      value = str.charCodeAt(pos);
      if ((value & 0xfc00) === 0xdc00) pos++;
    }
  }
  return length;
}`;

/** Código ESM com uma função de validação exportada por contrato. */
export async function gerarCodigo() {
  const esquema = JSON.parse(await readFile(ESQUEMA, "utf-8"));
  const ajv = new Ajv2020({
    allErrors: false,
    strict: false,
    code: { source: true, esm: true, lines: false },
  });
  adicionarFormatos(ajv);
  ajv.addSchema(esquema);
  const exportacoes = Object.fromEntries(CONTRATOS.map((c) => [c, `${esquema.$id}#/$defs/${c}`]));
  // Mesmo em modo ESM, o ajv importa o seu código de apoio com require(), que não existe
  // no Worker. Os formatos passam a import com nome (igual em Node, Vite e esbuild) e a
  // contagem de carateres UTF-16 do ajv fica copiada aqui.
  const codigo = standaloneCode(ajv, exportacoes)
    .replace(/^"use strict";/, "")
    .replaceAll('require("ajv-formats/dist/formats").fullFormats', "fullFormats")
    .replaceAll('require("ajv/dist/runtime/ucs2length").default', "ucs2length");
  if (codigo.includes("require(")) throw new Error("Código de apoio do ajv por converter.");
  return [
    "// Gerado por scripts/gerar-validadores.mjs a partir de schemas/json/contratos.schema.json. Não editar.",
    'import { fullFormats } from "ajv-formats/dist/formats.js";',
    UCS2LENGTH,
    codigo,
    "",
  ].join("\n");
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  await writeFile(DESTINO, await gerarCodigo());
  console.log(`Escrito ${path.relative(process.cwd(), DESTINO)}`);
}
