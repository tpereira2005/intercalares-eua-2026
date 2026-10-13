// Gera src/gerado/contratos.ts a partir de schemas/json/contratos.schema.json.
// Nunca editar o ficheiro gerado à mão: alterar o modelo pydantic e correr
// `pnpm contratos:gerar` na raiz.
import { readFile, writeFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import { compile } from "json-schema-to-typescript";

const origem = fileURLToPath(
  new URL("../../../schemas/json/contratos.schema.json", import.meta.url),
);
const destino = fileURLToPath(new URL("../src/gerado/contratos.ts", import.meta.url));

const esquema = JSON.parse(await readFile(origem, "utf8"));

// O pydantic dá um título a cada campo ("Nome", "Url"...). Sem os remover, o
// gerador cria um tipo de topo por campo, com colisões entre modelos.
function removerTitulosDeCampos(no) {
  if (Array.isArray(no)) return no.forEach(removerTitulosDeCampos);
  if (no === null || typeof no !== "object") return;
  if (no.properties) {
    for (const campo of Object.values(no.properties)) delete campo.title;
  }
  Object.values(no).forEach(removerTitulosDeCampos);
}
removerTitulosDeCampos(esquema);
const codigo = await compile(esquema, "Contratos", {
  bannerComment:
    "/* Ficheiro gerado por packages/contratos/scripts/gerar.mjs. Não editar à mão. */",
  unreachableDefinitions: true,
  additionalProperties: false,
  strictIndexSignatures: true,
  format: true,
});
await writeFile(destino, codigo);
console.log(`Tipos escritos em ${destino}`);
