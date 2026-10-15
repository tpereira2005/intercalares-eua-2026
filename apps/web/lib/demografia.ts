/**
 * Comparação entre estados para a página /demografia/: as três perguntas (composição,
 * participação e momento do voto) para os jovens e os 65+, em cada estado com idade.
 *
 * Não há aqui metodologia nova: quotas, desvios e grupos do momento vêm das vistas de
 * cada estado (vista.ts e agregado.ts), sempre no mesmo dia do ciclo do ano de
 * referência desse estado. Esta camada só soma faixas em grupos e alinha os estados.
 */

import type { NivelQualidade } from "@/components/ui/QualidadeDados.tsx";
import type { FaixaAgregada, VistaAgregada } from "./voto-antecipado/agregado.ts";
import type { VistasEstados } from "./voto-antecipado/carregar.ts";
import type { FaixaEtaria, MomentoFaixa, VistaVotoAntecipado } from "./voto-antecipado/vista.ts";

export type Grupo = "jovens" | "mais65";
export const GRUPOS: readonly Grupo[] = ["jovens", "mais65"];

const FAIXAS_GRUPO: Record<Grupo, readonly FaixaAgregada[]> = {
  jovens: ["18-24", "25-29"],
  mais65: ["65-74", "75+"],
};

export interface Composicao {
  /** Quota do grupo nos votos de 2026 e no mesmo dia do ano de referência. */
  quota: number;
  quotaBase: number;
}

export interface Momento {
  habituais: number;
  antecipacao: number;
  novos: number;
}

export interface EstadoDemografia {
  estado: VistaVotoAntecipado["estado"];
  qualidade: NivelQualidade;
  naoOficial: boolean;
  votos: number;
  dadosAte: string;
  diasAntes: number;
  anoBase: number | null;
  /** Os jovens são só os 18–24 quando a fonte não separa os 25–29 (faixas de dez anos). */
  soMenos25: boolean;
  composicao: Record<Grupo, Composicao | null>;
  /** Observados / esperados − 1 ao ritmo do ano de referência (só com ficheiro de eleitores). */
  desvio: Record<Grupo | "todos", number | null>;
  /** Habituais, antecipação e voto novo em 2026 e no ano de referência do histórico. */
  momento: {
    anoReferencia: number | null;
    anoComparar: number | null;
    grupos: Record<Grupo | "todos", { atual: Momento | null; base: Momento | null }>;
  } | null;
}

function composicaoDe(
  faixas: readonly { faixa: string; quota: number | null; quotaBase: number | null }[],
  grupo: readonly string[],
): Composicao | null {
  const linhas = faixas.filter((f) => grupo.includes(f.faixa));
  if (linhas.length === 0) return null;
  let quota = 0;
  let quotaBase = 0;
  for (const l of linhas) {
    if (l.quota === null || l.quotaBase === null) return null;
    quota += l.quota;
    quotaBase += l.quotaBase;
  }
  return { quota, quotaBase };
}

/** Grupos do momento somados pelas faixas do grupo, pesados pelos votos de cada faixa. */
export function juntarMomento(
  faixas: readonly MomentoFaixa[],
  grupo: readonly string[] | "todos",
): Momento | null {
  const linhas =
    grupo === "todos"
      ? faixas.filter((f) => f.faixa === "total")
      : faixas.filter((f) => grupo.includes(f.faixa));
  const votos = linhas.reduce((s, f) => s + f.votos, 0);
  if (votos <= 0) return null;
  const media = (campo: keyof Momento) =>
    linhas.reduce((s, f) => s + f[campo] * f.votos, 0) / votos;
  return {
    habituais: media("habituais"),
    antecipacao: media("antecipacao"),
    novos: media("novos"),
  };
}

function desvioDe(vista: VistaVotoAntecipado, grupo: readonly string[] | null): number | null {
  const faixas = (vista.comparacoes[0]?.faixas ?? []).filter(
    (f) => grupo === null || grupo.includes(f.faixa),
  );
  const esperado = faixas.reduce((s, f) => s + f.esperado, 0);
  return esperado > 0 ? faixas.reduce((s, f) => s + f.votos, 0) / esperado - 1 : null;
}

export function demografiaIndividual(vista: VistaVotoAntecipado): EstadoDemografia {
  const principal = vista.comparacoes[0];
  const faixas = principal?.faixas ?? [];
  const atual = vista.momento.find((m) => m.ano === vista.ano);
  const base = vista.momento.find((m) => m.ano !== vista.ano && m.ano === principal?.anoBase);
  const grupoMomento = (g: readonly string[] | "todos") => ({
    atual: atual ? juntarMomento(atual.faixas, g) : null,
    base: base ? juntarMomento(base.faixas, g) : null,
  });
  return {
    estado: vista.estado,
    qualidade: vista.momento.length > 0 ? "individual" : faixas.length > 0 ? "parcial" : "agregado",
    naoOficial: false,
    votos: vista.votos,
    dadosAte: vista.dadosAte,
    diasAntes: vista.diasAntes,
    anoBase: principal?.anoBase ?? null,
    soMenos25: false,
    composicao: {
      jovens: composicaoDe(faixas, FAIXAS_GRUPO.jovens),
      mais65: composicaoDe(faixas, FAIXAS_GRUPO.mais65),
    },
    desvio: {
      todos: desvioDe(vista, null),
      jovens: desvioDe(vista, FAIXAS_GRUPO.jovens),
      mais65: desvioDe(vista, FAIXAS_GRUPO.mais65),
    },
    momento: atual
      ? {
          anoReferencia: atual.anoReferencia,
          anoComparar: base?.ano ?? null,
          grupos: {
            todos: grupoMomento("todos"),
            jovens: grupoMomento(FAIXAS_GRUPO.jovens),
            mais65: grupoMomento(FAIXAS_GRUPO.mais65),
          },
        }
      : null,
  };
}

export function demografiaAgregada(vista: VistaAgregada): EstadoDemografia {
  const principal = vista.comparacoes[0];
  const faixas = (principal?.faixas ?? []).map((f) => ({ ...f, faixa: f.categoria }));
  const jovens: readonly FaixaAgregada[] = vista.faixasDezAnos ? ["18-24"] : FAIXAS_GRUPO.jovens;
  return {
    estado: vista.estado,
    qualidade: vista.dimensoes.includes("faixa") ? "parcial" : "agregado",
    naoOficial: vista.naoOficial,
    votos: vista.votos,
    dadosAte: vista.dadosAte,
    diasAntes: vista.diasAntes,
    anoBase: principal?.anoBase ?? null,
    soMenos25: vista.faixasDezAnos,
    composicao: {
      jovens: composicaoDe(faixas, jovens),
      mais65: composicaoDe(faixas, FAIXAS_GRUPO.mais65),
    },
    desvio: { todos: null, jovens: null, mais65: null },
    momento: null,
  };
}

/** Estados com idade, do que tem mais votos para o que tem menos. */
export function demografiaTodos(vistas: VistasEstados): EstadoDemografia[] {
  return [
    ...vistas.individuais.map(demografiaIndividual),
    ...vistas.agregados.map(demografiaAgregada),
  ]
    .filter((e) => e.composicao.jovens !== null || e.composicao.mais65 !== null)
    .sort((a, b) => b.votos - a.votos || a.estado.localeCompare(b.estado));
}

/** Faixas que formam cada grupo, para os textos. */
export function faixasGrupo(grupo: Grupo): readonly FaixaEtaria[] {
  return FAIXAS_GRUPO[grupo] as readonly FaixaEtaria[];
}
