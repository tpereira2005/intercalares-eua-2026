/**
 * Resumo de um estado para o painel inicial e o mapa: poucos números, sempre
 * face à comparação principal (a intercalar mais recente, no mesmo dia do ciclo).
 */

import type { NivelQualidade } from "@/components/ui/QualidadeDados.tsx";
import type { FaixaEtaria, LinhaFaixa, VistaVotoAntecipado } from "./vista.ts";

export interface ResumoEstado {
  estado: VistaVotoAntecipado["estado"];
  votos: number;
  dadosAte: string;
  diasAntes: number;
  anoBase: number | null;
  variacaoVotos: number | null;
  /** Observados / esperados − 1, ao ritmo do ano de referência. */
  desvio: { todos: number | null; mais65: number | null; jovens: number | null };
  quota65: number | null;
  quota65Base: number | null;
  /** Habituais que ainda não votaram, somando os partidos. */
  restantes: number | null;
  qualidade: NivelQualidade;
}

const MAIS_65: readonly FaixaEtaria[] = ["65-74", "75+"];
const JOVENS: readonly FaixaEtaria[] = ["18-24", "25-29"];

function desvioDe(faixas: readonly LinhaFaixa[]): number | null {
  const esperado = faixas.reduce((s, f) => s + f.esperado, 0);
  return esperado > 0 ? faixas.reduce((s, f) => s + f.votos, 0) / esperado - 1 : null;
}

/**
 * Individual: há idade e histórico de voto eleitor a eleitor. Parcial: há
 * comparação por idade, sem histórico. Agregado: só totais.
 */
function qualidadeDe(vista: VistaVotoAntecipado): NivelQualidade {
  if (vista.comparacoes.length === 0) return "agregado";
  return vista.momento.length > 0 ? "individual" : "parcial";
}

export function resumirEstado(vista: VistaVotoAntecipado): ResumoEstado {
  const principal = vista.comparacoes[0];
  const faixas = principal?.faixas ?? [];
  const de = (grupo: readonly FaixaEtaria[]) => faixas.filter((f) => grupo.includes(f.faixa));
  const idosos = de(MAIS_65);
  return {
    estado: vista.estado,
    votos: vista.votos,
    dadosAte: vista.dadosAte,
    diasAntes: vista.diasAntes,
    anoBase: principal?.anoBase ?? null,
    variacaoVotos: principal?.variacaoVotos ?? null,
    desvio: {
      todos: desvioDe(faixas),
      mais65: desvioDe(idosos),
      jovens: desvioDe(de(JOVENS)),
    },
    quota65: idosos.length > 0 ? idosos.reduce((s, f) => s + f.quota, 0) : null,
    quota65Base: idosos.length > 0 ? idosos.reduce((s, f) => s + f.quotaBase, 0) : null,
    restantes:
      vista.reserva.partidos.length > 0
        ? vista.reserva.partidos.reduce((s, p) => s + p.restantes, 0)
        : null,
    qualidade: qualidadeDe(vista),
  };
}
