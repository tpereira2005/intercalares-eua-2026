/**
 * Voto contado e voto que falta em cada corrida, ao lado da projeção do modelo.
 *
 * O voto esperado vem do Modelo C (`votos_esperados`); os votos contados e a separação
 * por modalidade vêm da contagem oficial. Aqui só se fazem contas de somar e dividir:
 * quanto falta, que parte do contado veio de cada modalidade e por quanto o partido
 * atrás teria de ganhar o voto que falta para empatar.
 */

import type { LinhaResultados, ModalidadeResultado } from "../resultados/vista.ts";
import type { Lado } from "../previsao/vista.ts";

export interface ModoFalta {
  modo: ModalidadeResultado;
  votos: number;
  /** Parte do voto esperado. */
  fracao: number;
  /** Margem D − R da modalidade, em pontos; `null` sem votos de D nem de R. */
  margem: number | null;
}

export interface VotoQueFalta {
  linha: LinhaResultados;
  contados: number;
  esperados: number;
  falta: number;
  /** Parte do voto esperado já contada (0 a 1). */
  fracaoContada: number;
  modos: ModoFalta[];
  /** Votos contados em unidades que não separam por modalidade. */
  semModo: number;
  /** Partido à frente na contagem; `null` em empate. */
  lider: Lado | null;
  /**
   * Margem, em pontos, por que o partido atrás teria de ganhar o voto que falta para
   * empatar. `null` sem líder ou sem voto por contar.
   */
  precisa: number | null;
  /** Margens em pontos (D − R): projeção, intervalo de 80% e contagem. */
  margem: number;
  margemP10: number;
  margemP90: number;
  margemContada: number | null;
}

function margemPontos(d: number, r: number, total: number): number | null {
  return total > 0 && d + r > 0 ? ((d - r) / total) * 100 : null;
}

export function votoQueFalta(linha: LinhaResultados): VotoQueFalta | null {
  const { contagem, projecao } = linha;
  if (!contagem || !projecao || projecao.decidida) return null;
  const esperadosModelo = projecao.votosEsperados;
  if (esperadosModelo === null || esperadosModelo <= 0 || contagem.total === 0) return null;
  // A contagem pode ter avançado depois da projeção: o esperado nunca fica abaixo do contado.
  const esperados = Math.max(esperadosModelo, contagem.total);
  const falta = esperados - contagem.total;
  const vantagem = contagem.votosD - contagem.votosR;
  const lider: Lado | null = vantagem > 0 ? "D" : vantagem < 0 ? "R" : null;
  const comModo = contagem.porModo.reduce((n, m) => n + m.total, 0);
  return {
    linha,
    contados: contagem.total,
    esperados,
    falta,
    fracaoContada: contagem.total / esperados,
    modos: contagem.porModo.map((m) => ({
      modo: m.modo,
      votos: m.total,
      fracao: m.total / esperados,
      margem: margemPontos(m.votosD, m.votosR, m.total),
    })),
    semModo: Math.max(0, contagem.total - comModo),
    lider,
    precisa: lider === null || falta < 1 ? null : (Math.abs(vantagem) / falta) * 100,
    margem: projecao.margem,
    margemP10: projecao.margemP10,
    margemP90: projecao.margemP90,
    margemContada: contagem.margem === null ? null : contagem.margem * 100,
  };
}

/** Corridas por decidir com voto esperado, da mais renhida na projeção para a menos. */
export function corridasComFalta(linhas: readonly LinhaResultados[]): VotoQueFalta[] {
  return linhas
    .flatMap((l) => {
      const v = votoQueFalta(l);
      return v ? [v] : [];
    })
    .sort(
      (a, b) => Math.abs(a.margem) - Math.abs(b.margem) || a.linha.id.localeCompare(b.linha.id),
    );
}
