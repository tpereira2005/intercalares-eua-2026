/**
 * Composição do voto antecipado por partido de registo e por modalidade, no mesmo dia
 * do ciclo do ano de referência (série diária do contrato VotoAntecipadoEstado).
 *
 * Só se somam e dividem os votos da série; não há modelo. O partido é o de registo, não
 * o voto de cada eleitor.
 */

import type { PontoSerie } from "@intercalares/contratos";
import { PARTIDOS, type PartidoRegisto } from "./vista.ts";

export type ModalidadeVoto = "correio" | "presencial";
export const MODALIDADES: readonly ModalidadeVoto[] = ["correio", "presencial"];

export interface ParteComposicao<C extends string> {
  categoria: C;
  votos: number;
  /** Fração dos votos do ano; `null` sem votos. */
  quota: number | null;
  votosBase: number | null;
  quotaBase: number | null;
}

export interface ComposicaoEstado {
  anoBase: number | null;
  partidos: ParteComposicao<PartidoRegisto>[];
  modalidades: ParteComposicao<ModalidadeVoto>[];
  /** Quota democrata menos quota republicana entre quem já votou (fração). */
  vantagemDemRep: number | null;
  vantagemDemRepBase: number | null;
}

function votosEm(
  serie: readonly PontoSerie[],
  ano: number,
  diasAntes: number,
  filtro: (p: PontoSerie) => boolean,
): number | null {
  const pontos = serie.filter(
    (p) => p.ano === ano && p.dias_antes === diasAntes && p.faixa === "total" && filtro(p),
  );
  return pontos.length === 0 ? null : pontos.reduce((s, p) => s + p.votos, 0);
}

function partes<C extends string>(
  serie: readonly PontoSerie[],
  ano: number,
  anoBase: number | null,
  diasAntes: number,
  categorias: readonly C[],
  filtro: (p: PontoSerie, c: C) => boolean,
): ParteComposicao<C>[] {
  const contar = (a: number) =>
    categorias.map((c) => votosEm(serie, a, diasAntes, (p) => filtro(p, c)));
  const atuais = contar(ano);
  const base = anoBase === null ? null : contar(anoBase);
  const total = (lista: (number | null)[]) => lista.reduce<number>((s, v) => s + (v ?? 0), 0);
  const totalAtual = total(atuais);
  const totalBase = base ? total(base) : 0;
  if (atuais.every((v) => v === null)) return [];
  return categorias.map((categoria, i) => {
    const votos = atuais[i] ?? 0;
    const votosBase = base?.[i] ?? null;
    return {
      categoria,
      votos,
      quota: totalAtual > 0 ? votos / totalAtual : null,
      votosBase,
      quotaBase: votosBase !== null && totalBase > 0 ? votosBase / totalBase : null,
    };
  });
}

export function composicaoEstado(
  serie: readonly PontoSerie[],
  ano: number,
  anoBase: number | null,
  diasAntes: number,
): ComposicaoEstado {
  const partidos = partes(
    serie,
    ano,
    anoBase,
    diasAntes,
    PARTIDOS,
    (p, c) => p.partido === c && p.modalidade === "total",
  );
  const modalidades = partes(
    serie,
    ano,
    anoBase,
    diasAntes,
    MODALIDADES,
    (p, c) => p.partido === "total" && p.modalidade === c,
  );
  const quota = (lado: PartidoRegisto, campo: "quota" | "quotaBase") =>
    partidos.find((p) => p.categoria === lado)?.[campo] ?? null;
  const vantagem = (campo: "quota" | "quotaBase") => {
    const d = quota("dem", campo);
    const r = quota("rep", campo);
    return d === null || r === null ? null : d - r;
  };
  return {
    anoBase,
    partidos,
    modalidades,
    vantagemDemRep: vantagem("quota"),
    vantagemDemRepBase: vantagem("quotaBase"),
  };
}
