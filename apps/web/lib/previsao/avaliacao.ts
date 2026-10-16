/**
 * Avaliação pública da previsão: a versão congelada a 1 de novembro, comparada com as
 * chamadas das redações (contrato ChamadasRedacoes), corrida a corrida.
 *
 * O Escrutínio não declara vencedores, por isso a avaliação só conta corridas que uma
 * redação já chamou; as outras ficam pendentes. As mesmas regras valem para os dois
 * partidos e para os outros prognosticadores: acerta quem dava o vencedor como favorito.
 * Uma classificação de empate não acerta nem falha e conta à parte.
 */

import type { ChamadaVista } from "../resultados/chamadas.ts";
import { CENTRO, comparacaoDaCorrida, type VistaPrognosticos } from "./prognosticos.ts";
import type { CorridaVista, Lado, VistaPrevisao } from "./vista.ts";

export interface CorridaAvaliada {
  corrida: CorridaVista;
  vencedor: Lado;
  /** Probabilidade que a previsão dava ao vencedor. */
  probVencedor: number;
  acertou: boolean;
  /** Mediana dos outros prognosticadores (0 a 6); `null` sem classificações. */
  consenso: number | null;
}

/** Corridas agrupadas pela probabilidade do favorito da previsão. */
export interface GrupoCalibracao {
  /** Limite inferior, incluído. */
  de: number;
  /** Limite superior: excluído, exceto no último grupo. */
  ate: number;
  n: number;
  /** Média da probabilidade do favorito: os acertos que a previsão esperava, em fração. */
  esperado: number | null;
  acertos: number;
}

export interface AvaliacaoPrognosticador {
  chave: string;
  nome: string;
  /** Corridas chamadas que este prognosticador classificou. */
  classificadas: number;
  acertos: number;
  /** Classificadas como empate: não acertam nem falham. */
  empates: number;
  /** Acertos da previsão do Escrutínio nas mesmas corridas, para comparar como iguais. */
  acertosEscrutinio: number;
}

export interface VistaAvaliacao {
  congelada: boolean;
  /** Corridas em jogo (as que não estavam decididas antes da eleição). */
  emJogo: number;
  avaliadas: CorridaAvaliada[];
  acertos: number;
  /** Média de (1 − p do vencedor)²; 0 é perfeito, 0,25 é dizer 50% em todas. */
  brier: number | null;
  calibracao: GrupoCalibracao[];
  /** Corridas ganhas por um candidato que não conta como D nem R. */
  outro: string[];
  prognosticadores: AvaliacaoPrognosticador[];
  /** Os outros prognosticadores estavam congelados no mesmo dia que a previsão. */
  prognosticosCongelados: boolean | null;
}

// As mesmas faixas do scorecard do pipeline (`pipeline/modelo/avaliacao.py`, `FAIXAS`).
const LIMITES = [0.5, 0.6, 0.7, 0.8, 0.9, 0.95, 1] as const;

function grupos(avaliadas: readonly CorridaAvaliada[]): GrupoCalibracao[] {
  const resultado: GrupoCalibracao[] = [];
  for (let i = 0; i < LIMITES.length - 1; i++) {
    const de = LIMITES[i] ?? 0;
    const ate = LIMITES[i + 1] ?? 1;
    const ultimo = i === LIMITES.length - 2;
    const membros = avaliadas.filter((a) => {
      const p = Math.max(a.corrida.probD, 1 - a.corrida.probD);
      return p >= de && (ultimo ? p <= ate : p < ate);
    });
    const soma = membros.reduce((s, a) => s + Math.max(a.corrida.probD, 1 - a.corrida.probD), 0);
    resultado.push({
      de,
      ate,
      n: membros.length,
      esperado: membros.length > 0 ? soma / membros.length : null,
      acertos: membros.filter((a) => a.acertou).length,
    });
  }
  return resultado;
}

export function avaliarPrevisao(
  previsao: VistaPrevisao,
  chamadas: readonly ChamadaVista[],
  prognosticos: VistaPrognosticos | null,
): VistaAvaliacao {
  const vencedores = new Map(chamadas.map((c) => [c.corrida, c.vencedor]));
  const todas = [...previsao.corridasSenado, ...previsao.corridasCamara].filter(
    (c) => c.decidida === null,
  );
  const avaliadas: CorridaAvaliada[] = [];
  const outro: string[] = [];
  const porPrognosticador = new Map<string, AvaliacaoPrognosticador>();

  for (const corrida of todas) {
    const vencedor = vencedores.get(corrida.id);
    if (vencedor === undefined) continue;
    if (vencedor === "outro") {
      outro.push(corrida.id);
      continue;
    }
    const probVencedor = vencedor === "D" ? corrida.probD : 1 - corrida.probD;
    // Com 50% exatos não há favorito: conta como falha, para não favorecer ninguém.
    const acertou = probVencedor > 0.5;
    const comparacao = prognosticos ? comparacaoDaCorrida(prognosticos, corrida) : null;
    avaliadas.push({
      corrida,
      vencedor,
      probVencedor,
      acertou,
      consenso: comparacao?.consenso ?? null,
    });
    for (const c of comparacao?.classificacoes ?? []) {
      const atual = porPrognosticador.get(c.chave) ?? {
        chave: c.chave,
        nome: c.nome,
        classificadas: 0,
        acertos: 0,
        empates: 0,
        acertosEscrutinio: 0,
      };
      atual.classificadas += 1;
      if (c.posicao === CENTRO) atual.empates += 1;
      else if ((c.posicao < CENTRO ? "D" : "R") === vencedor) atual.acertos += 1;
      if (acertou) atual.acertosEscrutinio += 1;
      porPrognosticador.set(c.chave, atual);
    }
  }

  const brier =
    avaliadas.length > 0
      ? avaliadas.reduce((s, a) => s + (1 - a.probVencedor) ** 2, 0) / avaliadas.length
      : null;
  return {
    congelada: previsao.congelada,
    emJogo: todas.length,
    avaliadas,
    acertos: avaliadas.filter((a) => a.acertou).length,
    brier,
    calibracao: grupos(avaliadas),
    outro,
    prognosticadores: [...porPrognosticador.values()].sort(
      (a, b) => b.classificadas - a.classificadas || a.nome.localeCompare(b.nome),
    ),
    prognosticosCongelados: prognosticos ? prognosticos.congelado : null,
  };
}
