/**
 * Idade por condado e por distrito (linhas `geografia` de VotoAntecipadoEstado).
 *
 * O pipeline publica, para cada unidade e ano, os votos antecipados até ao mesmo
 * dia do ciclo e os recenseados de cada faixa larga. Aqui só se dividem contagens:
 * quota da faixa nos votos da unidade, a mesma quota no ano de comparação e a
 * participação da faixa (votos / recenseados). Unidades com poucos votos ficam
 * marcadas, porque as quotas variam muito ao acaso.
 */

import type { LinhaGeografia } from "@intercalares/contratos";

export const FAIXAS_LARGAS = ["18-29", "30-49", "50-64", "65+"] as const;
export type FaixaLarga = (typeof FAIXAS_LARGAS)[number];
export type NivelGeografico = LinhaGeografia["nivel"];

/** Abaixo destes votos numa unidade (em qualquer dos dois anos), a quota é pouco fiável. */
export const MINIMO_VOTOS_UNIDADE = 100;

/** Contagens de um ano numa unidade: por faixa larga, pela ordem de FAIXAS_LARGAS, e o total. */
export interface AnoUnidade {
  ano: number;
  votos: number[];
  registados: number[];
  votosTotal: number;
  registadosTotal: number;
}

export interface UnidadeGeografica {
  nivel: NivelGeografico;
  codigo: string;
  nome: string;
  anos: AnoUnidade[];
}

/** Agrupa as linhas por unidade e ano. Faixas em falta contam zero; "desconhecida" fica fora. */
export function agruparGeografia(linhas: readonly LinhaGeografia[]): UnidadeGeografica[] {
  const unidades = new Map<string, UnidadeGeografica>();
  for (const l of linhas) {
    const chave = `${l.nivel}:${l.codigo}`;
    let unidade = unidades.get(chave);
    if (!unidade) {
      unidade = { nivel: l.nivel, codigo: l.codigo, nome: l.nome, anos: [] };
      unidades.set(chave, unidade);
    }
    let ano = unidade.anos.find((a) => a.ano === l.ano);
    if (!ano) {
      ano = {
        ano: l.ano,
        votos: FAIXAS_LARGAS.map(() => 0),
        registados: FAIXAS_LARGAS.map(() => 0),
        votosTotal: 0,
        registadosTotal: 0,
      };
      unidade.anos.push(ano);
    }
    if (l.faixa === "total") {
      ano.votosTotal = l.votos;
      ano.registadosTotal = l.registados;
    } else {
      const indice = FAIXAS_LARGAS.indexOf(l.faixa as FaixaLarga);
      if (indice >= 0) {
        ano.votos[indice] = l.votos;
        ano.registados[indice] = l.registados;
      }
    }
  }
  return [...unidades.values()]
    .map((u) => ({ ...u, anos: u.anos.sort((a, b) => b.ano - a.ano) }))
    .sort((a, b) =>
      a.nivel === b.nivel
        ? a.nivel === "distrito"
          ? Number(a.codigo) - Number(b.codigo)
          : a.nome.localeCompare(b.nome, "pt-PT", { numeric: true })
        : a.nivel === "distrito"
          ? -1
          : 1,
    );
}

export interface LinhaUnidade {
  codigo: string;
  nome: string;
  votos: number;
  votosFaixa: number;
  /** Quota da faixa nos votos da unidade em 2026 (composição). */
  quota: number | null;
  quotaBase: number | null;
  /** quota − quotaBase, em fração. */
  diferenca: number | null;
  /** Votos da faixa / recenseados da faixa (participação até ao dia). */
  taxa: number | null;
  taxaBase: number | null;
  /** Menos de MINIMO_VOTOS_UNIDADE votos num dos dois anos. */
  poucosVotos: boolean;
}

function razao(a: number, b: number): number | null {
  return b > 0 ? a / b : null;
}

/** Linhas de uma tabela: uma faixa, um nível e um ano de comparação, por ordem de diferença. */
export function linhasUnidades(
  unidades: readonly UnidadeGeografica[],
  nivel: NivelGeografico,
  faixa: FaixaLarga,
  ano: number,
  anoBase: number,
): LinhaUnidade[] {
  const i = FAIXAS_LARGAS.indexOf(faixa);
  return unidades
    .filter((u) => u.nivel === nivel)
    .flatMap((u) => {
      const atual = u.anos.find((a) => a.ano === ano);
      if (!atual) return [];
      const base = u.anos.find((a) => a.ano === anoBase);
      const votosFaixa = atual.votos[i] ?? 0;
      const quota = razao(votosFaixa, atual.votosTotal);
      const quotaBase = base ? razao(base.votos[i] ?? 0, base.votosTotal) : null;
      return [
        {
          codigo: u.codigo,
          nome: u.nome,
          votos: atual.votosTotal,
          votosFaixa,
          quota,
          quotaBase,
          diferenca: quota !== null && quotaBase !== null ? quota - quotaBase : null,
          taxa: razao(votosFaixa, atual.registados[i] ?? 0),
          taxaBase: base ? razao(base.votos[i] ?? 0, base.registados[i] ?? 0) : null,
          poucosVotos:
            atual.votosTotal < MINIMO_VOTOS_UNIDADE ||
            (base !== undefined && base.votosTotal < MINIMO_VOTOS_UNIDADE),
        },
      ];
    })
    .sort(
      (a, b) =>
        Number(a.poucosVotos) - Number(b.poucosVotos) ||
        (b.diferenca ?? -Infinity) - (a.diferenca ?? -Infinity) ||
        a.nome.localeCompare(b.nome, "pt-PT", { numeric: true }),
    );
}
