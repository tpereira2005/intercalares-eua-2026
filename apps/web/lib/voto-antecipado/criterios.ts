/**
 * "Quem já votou" por vários critérios ao mesmo tempo (partido de registo, modalidade,
 * histórico de voto e idade), cada um face ao mesmo dia do ano de referência. A idade é
 * um critério entre os outros, em faixas largas.
 */

import type { FaixaEtaria, PartidoRegisto, VistaVotoAntecipado } from "./vista.ts";
import type { ModalidadeVoto } from "./composicao.ts";

export type Criterio = "partido" | "modalidade" | "historico" | "idade";
export type GrupoHistorico = "habituais" | "antecipacao" | "novos";
export type FaixaLarga = "18-29" | "30-49" | "50-64" | "65+";

const FAIXAS_LARGAS: readonly { faixa: FaixaLarga; inclui: readonly FaixaEtaria[] }[] = [
  { faixa: "18-29", inclui: ["18-24", "25-29"] },
  { faixa: "30-49", inclui: ["30-39", "40-49"] },
  { faixa: "50-64", inclui: ["50-64"] },
  { faixa: "65+", inclui: ["65-74", "75+"] },
];

export interface LinhaCriterio {
  categoria: PartidoRegisto | ModalidadeVoto | GrupoHistorico | FaixaLarga;
  quota: number;
  /** Quota no mesmo dia do ano de referência; `null` sem comparação. */
  quotaBase: number | null;
}

export interface BlocoCriterio {
  criterio: Criterio;
  /** Ano com que se compara (o histórico pode usar outro ano que não o da comparação). */
  anoBase: number | null;
  linhas: LinhaCriterio[];
}

function partido(vista: VistaVotoAntecipado): BlocoCriterio | null {
  const { partidos, anoBase } = vista.composicao;
  const linhas = partidos.flatMap((p) =>
    p.quota === null ? [] : [{ categoria: p.categoria, quota: p.quota, quotaBase: p.quotaBase }],
  );
  return linhas.length > 0 ? { criterio: "partido", anoBase, linhas } : null;
}

function modalidade(vista: VistaVotoAntecipado): BlocoCriterio | null {
  const { modalidades, anoBase } = vista.composicao;
  const linhas = modalidades.flatMap((m) =>
    m.quota === null ? [] : [{ categoria: m.categoria, quota: m.quota, quotaBase: m.quotaBase }],
  );
  return linhas.length > 0 ? { criterio: "modalidade", anoBase, linhas } : null;
}

function historico(vista: VistaVotoAntecipado): BlocoCriterio | null {
  const atual = vista.momento.find((m) => m.ano === vista.ano);
  const total = atual?.faixas.find((f) => f.faixa === "total");
  if (!atual || !total) return null;
  const anoBase = vista.composicao.anoBase;
  const base = vista.momento
    .find((m) => m.ano === anoBase)
    ?.faixas.find((f) => f.faixa === "total");
  const grupos: readonly GrupoHistorico[] = ["habituais", "antecipacao", "novos"];
  return {
    criterio: "historico",
    anoBase: base ? anoBase : null,
    linhas: grupos.map((g) => ({
      categoria: g,
      quota: total[g],
      quotaBase: base ? base[g] : null,
    })),
  };
}

function idade(vista: VistaVotoAntecipado): BlocoCriterio | null {
  const comparacao = vista.comparacoes[0];
  if (!comparacao || comparacao.faixas.length === 0) return null;
  return {
    criterio: "idade",
    anoBase: comparacao.anoBase,
    linhas: FAIXAS_LARGAS.map(({ faixa, inclui }) => {
      const linhas = comparacao.faixas.filter((f) => inclui.includes(f.faixa));
      return {
        categoria: faixa,
        quota: linhas.reduce((s, f) => s + f.quota, 0),
        quotaBase: linhas.reduce((s, f) => s + f.quotaBase, 0),
      };
    }),
  };
}

/** Os critérios com dados, sempre pela mesma ordem: partido, modalidade, histórico, idade. */
export function criteriosQuemVotou(vista: VistaVotoAntecipado): BlocoCriterio[] {
  return [partido(vista), modalidade(vista), historico(vista), idade(vista)].filter(
    (b): b is BlocoCriterio => b !== null,
  );
}
