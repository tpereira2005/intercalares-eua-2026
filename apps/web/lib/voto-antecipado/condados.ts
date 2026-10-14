/**
 * Sinal dos condados de Trump e de Harris: de que condados vêm os votos antecipados,
 * pela margem presidencial de 2024, em 2026 e no mesmo dia do ano de referência.
 *
 * É um sinal ecológico: mais votos em condados de Trump não dizem quem votou dentro
 * deles (plano, secção 3.3). Os números vêm do resumo nacional; aqui só se calculam
 * quotas e variações.
 */

import type { LinhaEstadoNacional, VotoAntecipadoNacional } from "@intercalares/contratos";

export interface PontoCondados {
  ano: number;
  votos: number;
  /** Quota dos votos antecipados que vem de condados que Trump venceu em 2024. */
  quotaTrump: number | null;
  /** Margem de 2024 (D − R, pontos) ponderada pelos votos de cada condado. */
  margem: number | null;
}

export interface SinalCondadosEstado {
  estado: LinhaEstadoNacional["estado"];
  atual: PontoCondados;
  base: PontoCondados | null;
  /** Variação da quota de Trump (fração) e da margem ponderada (pontos) face à base. */
  variacaoQuota: number | null;
  variacaoMargem: number | null;
}

function ponto(
  s: NonNullable<LinhaEstadoNacional["condados_presidenciais"]>[number],
): PontoCondados {
  const votos = s.votos_trump + s.votos_harris;
  return {
    ano: s.ano,
    votos,
    quotaTrump: votos > 0 ? s.votos_trump / votos : null,
    margem: s.margem_ponderada,
  };
}

/** Estados com o sinal, do que tem mais votos para o que tem menos. */
export function sinalCondados(nacional: VotoAntecipadoNacional | null): SinalCondadosEstado[] {
  if (!nacional) return [];
  return nacional.estados
    .flatMap((linha) => {
      const sinais = linha.condados_presidenciais ?? [];
      const atual = sinais.find((s) => s.ano === nacional.ano);
      if (!atual) return [];
      const base = sinais.find((s) => s.ano === linha.ano_base);
      const a = ponto(atual);
      const b = base ? ponto(base) : null;
      const diferenca = (x: number | null, y: number | null) =>
        x === null || y === null ? null : x - y;
      return [
        {
          estado: linha.estado,
          atual: a,
          base: b,
          variacaoQuota: diferenca(a.quotaTrump, b?.quotaTrump ?? null),
          variacaoMargem: diferenca(a.margem, b?.margem ?? null),
        },
      ];
    })
    .sort((x, y) => y.atual.votos - x.atual.votos || x.estado.localeCompare(y.estado));
}
