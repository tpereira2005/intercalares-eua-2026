/**
 * Vista da projeção da noite eleitoral (contratos ProjecaoNoite e HistoricoNoite,
 * produzidos pelo estimador do modelo; docs/metodologia/noite-eleitoral.md).
 *
 * Não há aqui metodologia nova: probabilidades, margens e intervalos vêm do modelo.
 * Esta camada só seleciona e reorganiza.
 */

import type { HistoricoNoite, ProjecaoNoite, ResumoCamaraNoite } from "@intercalares/contratos";
import { aparar, type Camara, type PontoEvolucao } from "../previsao/vista.ts";

export interface CamaraNoite {
  camara: Camara;
  total: number;
  maioria: number;
  probD: number;
  probR: number;
  /** Probabilidade de controlo democrata na previsão congelada de partida. */
  probDPrior: number;
  media: number;
  mediana: number;
  p10: number;
  p90: number;
  corridasComVotos: number;
  distribuicao: { lugares: number; probabilidade: number }[];
}

export interface CorridaNoite {
  id: string;
  camara: Camara;
  probD: number;
  probDPrior: number;
  /** Margens em pontos percentuais, D − R. */
  margem: number;
  margemPrior: number;
  margemP10: number;
  margemP90: number;
  margemContada: number | null;
  fracaoContada: number | null;
  votosContados: number;
  /** Votos que o modelo espera no total da corrida (contados e por contar). */
  votosEsperados: number | null;
  decidida: boolean;
}

export interface VistaNoite {
  ano: number;
  instante: string;
  geradoEm: string;
  cortePrior: string;
  priorCongelado: boolean;
  reconstruido: boolean;
  /** Ficheiro que não é a contagem real com a previsão congelada: leva sempre selo. */
  ensaio: boolean;
  simulacoes: number;
  fontes: { nome: string; url: string }[];
  notas: string[];
  desvio: { media: number; desvioPadrao: number; corridas: number };
  camara: CamaraNoite;
  senado: CamaraNoite;
  corridas: Map<string, CorridaNoite>;
  /** Evolução ao longo da noite, ou `null` sem histórico compatível. */
  evolucao: { camara: PontoEvolucao[]; senado: PontoEvolucao[] } | null;
}

function camara(r: ResumoCamaraNoite): CamaraNoite {
  return {
    camara: r.camara,
    total: r.lugares_total,
    maioria: r.maioria,
    probD: r.prob_controlo_d,
    probR: r.prob_controlo_r,
    probDPrior: r.prob_controlo_d_prior,
    media: r.lugares_d_media,
    mediana: r.lugares_d_mediana,
    p10: r.lugares_d_p10,
    p90: r.lugares_d_p90,
    corridasComVotos: r.corridas_com_votos,
    distribuicao: aparar(r.distribuicao),
  };
}

/**
 * Evolução do histórico que corresponde à projeção mostrada: mesmo ano, mesmo ponto de
 * partida e mesma natureza (real ou reconstruída), e só até ao instante da projeção.
 */
function evolucao(
  projecao: ProjecaoNoite,
  historico: HistoricoNoite | null,
): VistaNoite["evolucao"] {
  if (
    historico?.ano !== projecao.ano ||
    historico.corte_prior !== projecao.corte_prior ||
    historico.reconstruido !== projecao.reconstruido
  ) {
    return null;
  }
  const limite = Date.parse(projecao.instante);
  const pontos = [...historico.pontos]
    .filter((p) => Date.parse(p.instante) <= limite)
    .sort((a, b) => Date.parse(a.instante) - Date.parse(b.instante));
  if (pontos.length === 0) return null;
  const serie = (c: Camara): PontoEvolucao[] =>
    pontos.map((p) => ({
      corte: p.instante,
      probD: p[c].prob_controlo_d,
      probR: p[c].prob_controlo_r,
      mediana: p[c].lugares_d_mediana,
      p10: p[c].lugares_d_p10,
      p90: p[c].lugares_d_p90,
    }));
  return { camara: serie("camara"), senado: serie("senado") };
}

export function construirVistaNoite(
  projecao: ProjecaoNoite,
  historico: HistoricoNoite | null,
): VistaNoite {
  return {
    ano: projecao.ano,
    instante: projecao.instante,
    geradoEm: projecao.metadados.gerado_em,
    cortePrior: projecao.corte_prior,
    priorCongelado: projecao.prior_congelado,
    reconstruido: projecao.reconstruido,
    ensaio: projecao.reconstruido || !projecao.prior_congelado,
    simulacoes: projecao.simulacoes,
    fontes: projecao.metadados.fontes
      .filter((f, i, todas) => todas.findIndex((g) => g.nome === f.nome) === i)
      .map((f) => ({ nome: f.nome, url: f.url })),
    notas: [...projecao.notas],
    desvio: {
      media: projecao.desvio_nacional.media,
      desvioPadrao: projecao.desvio_nacional.desvio_padrao,
      corridas: projecao.desvio_nacional.corridas_informativas,
    },
    camara: camara(projecao.camara),
    senado: camara(projecao.senado),
    corridas: new Map(
      projecao.corridas.map((c) => [
        c.id,
        {
          id: c.id,
          camara: c.camara,
          probD: c.prob_d,
          probDPrior: c.prob_d_prior,
          margem: c.margem_projetada,
          margemPrior: c.margem_prior,
          margemP10: c.margem_p10,
          margemP90: c.margem_p90,
          margemContada: c.margem_contada,
          fracaoContada: c.fracao_contada,
          votosContados: c.votos_contados,
          votosEsperados: c.votos_esperados,
          decidida: c.decidida,
        },
      ]),
    ),
    evolucao: evolucao(projecao, historico),
  };
}
