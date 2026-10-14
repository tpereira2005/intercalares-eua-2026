/**
 * Avaliação da previsão depois da noite: compara as chamadas das redações com a previsão
 * congelada. Só entram as corridas chamadas para um dos dois partidos e que a previsão
 * tinha; a contagem lenta vai acrescentando corridas ao longo dos dias.
 */

import type { ChamadaVista } from "../resultados/chamadas.ts";

export interface Surpresa {
  corrida: string;
  vencedor: "D" | "R";
  candidato: string | null;
  /** Probabilidade que a previsão dava ao vencedor. */
  probVencedor: number;
}

export interface AvaliacaoPrevisao {
  avaliadas: number;
  /** Corridas chamadas para o favorito da previsão (probabilidade acima de 50%). */
  acertos: number;
  /** Média de (p − resultado)², com p a probabilidade democrata; 0 é perfeito, 0,25 é atirar uma moeda. */
  brier: number | null;
  /** Corridas ganhas por quem a previsão dava como menos provável, da maior surpresa à menor. */
  surpresas: Surpresa[];
}

/** `probD` tem a probabilidade democrata de cada corrida na previsão congelada. */
export function avaliarPrevisao(
  chamadas: readonly ChamadaVista[],
  probD: Readonly<Record<string, number>>,
): AvaliacaoPrevisao {
  let acertos = 0;
  let soma = 0;
  const surpresas: Surpresa[] = [];
  const avaliadas = chamadas.flatMap((c) => {
    const p = probD[c.corrida];
    if (p === undefined || c.vencedor === "outro") return [];
    return [{ c, p, vencedor: c.vencedor }];
  });
  for (const { c, p, vencedor } of avaliadas) {
    const resultado = vencedor === "D" ? 1 : 0;
    soma += (p - resultado) ** 2;
    const probVencedor = vencedor === "D" ? p : 1 - p;
    // Um empate exato na previsão não conta como acerto nem como surpresa.
    if (probVencedor > 0.5) acertos += 1;
    else if (probVencedor < 0.5) {
      surpresas.push({ corrida: c.corrida, vencedor, candidato: c.candidato, probVencedor });
    }
  }
  surpresas.sort((a, b) => a.probVencedor - b.probVencedor || a.corrida.localeCompare(b.corrida));
  return {
    avaliadas: avaliadas.length,
    acertos,
    brier: avaliadas.length > 0 ? soma / avaliadas.length : null,
    surpresas,
  };
}
