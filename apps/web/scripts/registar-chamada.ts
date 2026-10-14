/**
 * Regista ou retira a chamada de uma redação (lib/resultados/registo-chamada.ts).
 *
 *   node --experimental-strip-types scripts/registar-chamada.ts <previsao> <chamadas>
 *
 * <previsao> é o previsao-2026.json publicado (dá as corridas válidas); <chamadas> é o
 * chamadas-2026.json atual, que é reescrito (pode ainda não existir). O pedido vem das
 * variáveis CORRIDA, VENCEDOR, REDACAO, URL_CHAMADA, HORA, CANDIDATO e RETIRAR.
 */

import { existsSync, readFileSync, writeFileSync } from "node:fs";
import type { ChamadasRedacoes, PrevisaoCongresso } from "@intercalares/contratos";
import { ChamadaInvalida, registarChamada } from "../lib/resultados/registo-chamada.ts";

const [argPrevisao, argChamadas] = process.argv.slice(2);
if (!argPrevisao || !argChamadas) {
  console.error("Uso: registar-chamada.ts <previsao> <chamadas>");
  process.exit(2);
}
const ficheiroChamadas: string = argChamadas;

const previsao = JSON.parse(readFileSync(argPrevisao, "utf-8")) as PrevisaoCongresso;
const atual = existsSync(ficheiroChamadas)
  ? (JSON.parse(readFileSync(ficheiroChamadas, "utf-8")) as ChamadasRedacoes)
  : null;
const env = (nome: string) => process.env[nome] ?? "";

try {
  const novo = registarChamada(
    atual,
    {
      corrida: env("CORRIDA"),
      vencedor: env("VENCEDOR"),
      redacao: env("REDACAO"),
      url: env("URL_CHAMADA"),
      hora: env("HORA"),
      candidato: env("CANDIDATO"),
      retirar: env("RETIRAR") === "true",
    },
    new Set(previsao.corridas.map((c) => c.id)),
    previsao.ano,
    new Date(),
  );
  writeFileSync(ficheiroChamadas, `${JSON.stringify(novo, null, 2)}\n`);
  console.log(`Chamadas em vigor: ${String(novo.chamadas.length)}.`);
} catch (erro) {
  if (erro instanceof ChamadaInvalida) {
    console.error(erro.message);
    process.exit(1);
  }
  throw erro;
}
