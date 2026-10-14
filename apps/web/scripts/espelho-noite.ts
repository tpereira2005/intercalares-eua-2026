/**
 * Prepara o espelho de emergência da noite (lib/ao-vivo/espelho.ts).
 *
 *   node --experimental-strip-types scripts/espelho-noite.ts <entrada> <saida>
 *
 * <entrada> tem os ficheiros descarregados das Releases (parciais.json,
 * projecao-noite-2026.json, historico-noite-2026.json, chamadas-2026.json; os que
 * faltarem ficam de fora).
 * <saida> recebe resultados.json e noite.json, na forma das respostas da API.
 */

import { existsSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import path from "node:path";
import { FICHEIRO_NOITE, FICHEIRO_RESULTADOS, montarEspelho } from "../lib/ao-vivo/espelho.ts";

const [argEntrada, argSaida] = process.argv.slice(2);
if (!argEntrada || !argSaida) {
  console.error("Uso: espelho-noite.ts <entrada> <saida>");
  process.exit(2);
}
const entrada: string = argEntrada;
const saida: string = argSaida;

function ler(nome: string): unknown {
  const ficheiro = path.join(entrada, nome);
  return existsSync(ficheiro) ? (JSON.parse(readFileSync(ficheiro, "utf-8")) as unknown) : null;
}

const espelho = montarEspelho(
  {
    parciais: ler("parciais.json"),
    projecao: ler("projecao-noite-2026.json"),
    historico: ler("historico-noite-2026.json"),
    chamadas: ler("chamadas-2026.json"),
  },
  new Date(),
);
mkdirSync(saida, { recursive: true });
if (espelho.resultados) {
  writeFileSync(path.join(saida, FICHEIRO_RESULTADOS), JSON.stringify(espelho.resultados));
}
if (espelho.noite) {
  writeFileSync(path.join(saida, FICHEIRO_NOITE), JSON.stringify(espelho.noite));
}
console.log(
  `Espelho: resultados ${espelho.resultados ? "sim" : "não"}, noite ${espelho.noite ? "sim" : "não"}.`,
);
if (espelho.rejeitados.length > 0) {
  console.error(`Fora do espelho por não cumprirem o contrato: ${espelho.rejeitados.join(", ")}`);
  process.exit(1);
}
