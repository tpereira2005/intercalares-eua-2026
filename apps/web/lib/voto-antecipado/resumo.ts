/**
 * Resumo de um estado para o painel inicial e o mapa: poucos números, sempre
 * face à comparação principal (a intercalar mais recente, no mesmo dia do ciclo).
 */

import type { NivelQualidade } from "@/components/ui/QualidadeDados.tsx";
import type { VistaAgregada } from "./agregado.ts";
import type { VistasEstados } from "./carregar.ts";
import type { FaixaEtaria, LinhaFaixa, VistaVotoAntecipado } from "./vista.ts";

export interface ResumoEstado {
  estado: VistaVotoAntecipado["estado"];
  votos: number;
  dadosAte: string;
  diasAntes: number;
  anoBase: number | null;
  /** Votos do ano de referência até ao mesmo dia do ciclo. */
  votosBase: number | null;
  /** Votos / votos no mesmo dia do ano de referência − 1 (o "ritmo"). */
  variacaoVotos: number | null;
  /** Observados / esperados − 1, ao ritmo do ano de referência. */
  desvio: { todos: number | null; mais65: number | null; jovens: number | null };
  quota65: number | null;
  quota65Base: number | null;
  /** Habituais que ainda não votaram, somando os partidos. */
  restantes: number | null;
  /** Boletins por correspondência pedidos e ainda por devolver (estados agregados). */
  pendentes: number | null;
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
    votosBase: principal?.votosBase ?? null,
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
    pendentes: null,
    qualidade: qualidadeDe(vista),
  };
}

/**
 * Estados sem ficheiro de eleitores: não há esperados, por isso os desvios
 * ficam vazios e o mapa usa o ritmo. Parcial quando a fonte tem a idade.
 */
export function resumirAgregado(vista: VistaAgregada): ResumoEstado {
  const principal = vista.comparacoes[0];
  const idosos = (principal?.faixas ?? []).filter((f) =>
    (MAIS_65 as readonly string[]).includes(f.categoria),
  );
  const soma = (valores: (number | null)[]) =>
    valores.some((v) => v === null) ? null : valores.reduce<number>((s, v) => s + (v ?? 0), 0);
  const partidos = vista.pedidos.partidos;
  return {
    estado: vista.estado,
    votos: vista.votos,
    dadosAte: vista.dadosAte,
    diasAntes: vista.diasAntes,
    anoBase: principal?.anoBase ?? null,
    votosBase: principal?.votosBase ?? null,
    variacaoVotos: principal?.ritmo ?? null,
    desvio: { todos: null, mais65: null, jovens: null },
    quota65: idosos.length > 0 ? soma(idosos.map((f) => f.quota)) : null,
    quota65Base: idosos.length > 0 ? soma(idosos.map((f) => f.quotaBase)) : null,
    restantes: null,
    pendentes: partidos.length > 0 ? partidos.reduce((s, p) => s + p.pendentes, 0) : null,
    qualidade: vista.dimensoes.includes("faixa") ? "parcial" : "agregado",
  };
}

/** Resumos de todos os estados com dados, do que tem mais votos para o que tem menos. */
export function resumirTodos(vistas: VistasEstados): ResumoEstado[] {
  return [...vistas.individuais.map(resumirEstado), ...vistas.agregados.map(resumirAgregado)].sort(
    (a, b) => b.votos - a.votos || a.estado.localeCompare(b.estado),
  );
}
