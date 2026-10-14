/**
 * Idade por condado e por distrito (linhas `geografia` de VotoAntecipadoEstado).
 *
 * O pipeline publica, para cada unidade e ano, os votos antecipados até ao mesmo
 * dia do ciclo e os recenseados de cada faixa larga. Aqui só se dividem contagens:
 * quota da faixa nos votos da unidade, a mesma quota no ano de comparação e a
 * participação da faixa (votos / recenseados). Unidades com poucos votos ficam
 * marcadas, porque as quotas variam muito ao acaso.
 */

import type {
  LinhaGeografia,
  LinhaGeografiaAgregada,
  LinhaHistoricoGeografia,
} from "@intercalares/contratos";

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
  /**
   * Quota de voto novo nos votos de cada faixa (quem se absteve ou se recenseou depois da
   * eleição de referência), pela ordem de FAIXAS_LARGAS; `null` sem histórico.
   */
  novos: (number | null)[];
}

export interface UnidadeGeografica {
  nivel: NivelGeografico;
  codigo: string;
  nome: string;
  anos: AnoUnidade[];
}

/** Linha de geografia com recenseados opcionais (os estados sem ficheiro de eleitores não os têm). */
export type LinhaGeografiaComum = Pick<
  LinhaGeografia,
  "ano" | "nivel" | "codigo" | "nome" | "faixa" | "votos"
> & { registados?: number };

/**
 * Linhas por faixa de um estado agregado (Pensilvânia): as que têm `partido = "total"`.
 * As linhas por partido (`faixa = "total"` e partido concreto) ficam de fora.
 */
export function linhasPorFaixa(linhas: readonly LinhaGeografiaAgregada[]): LinhaGeografiaComum[] {
  return linhas.flatMap((l) =>
    l.partido === "total" && l.faixa !== undefined
      ? [
          {
            ano: l.ano,
            nivel: l.nivel,
            codigo: l.codigo,
            nome: l.nome,
            faixa: l.faixa,
            votos: l.votos,
          },
        ]
      : [],
  );
}

/** Agrupa as linhas por unidade e ano. Faixas em falta contam zero; "desconhecida" fica fora. */
export function agruparGeografia(linhas: readonly LinhaGeografiaComum[]): UnidadeGeografica[] {
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
        novos: FAIXAS_LARGAS.map(() => null),
      };
      unidade.anos.push(ano);
    }
    if (l.faixa === "total") {
      ano.votosTotal = l.votos;
      ano.registadosTotal = l.registados ?? 0;
    } else {
      const indice = FAIXAS_LARGAS.indexOf(l.faixa as FaixaLarga);
      if (indice >= 0) {
        ano.votos[indice] = l.votos;
        ano.registados[indice] = l.registados ?? 0;
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

const HABITUAIS = new Set(["antecipado_na_referencia", "dia_eleicao_na_referencia"]);
const NOVOS = new Set(["absteve_se_na_referencia", "recenseado_apos_referencia"]);

/**
 * Junta às unidades a quota de voto novo de cada faixa e ano (linhas `historico_geografia`).
 * A regra é a do painel do momento do voto: novos sobre habituais e novos; quem não tem
 * histórico fica de fora.
 */
export function juntarHistorico(
  unidades: readonly UnidadeGeografica[],
  historico: readonly LinhaHistoricoGeografia[],
): UnidadeGeografica[] {
  const somas = new Map<string, { novos: number; todos: number }>();
  for (const l of historico) {
    if (!HABITUAIS.has(l.grupo) && !NOVOS.has(l.grupo)) continue;
    const chave = `${l.nivel}:${l.codigo}:${String(l.ano)}:${l.faixa}`;
    const soma = somas.get(chave) ?? { novos: 0, todos: 0 };
    soma.todos += l.votos;
    if (NOVOS.has(l.grupo)) soma.novos += l.votos;
    somas.set(chave, soma);
  }
  return unidades.map((u) => ({
    ...u,
    anos: u.anos.map((a) => ({
      ...a,
      novos: FAIXAS_LARGAS.map((f) => {
        const soma = somas.get(`${u.nivel}:${u.codigo}:${String(a.ano)}:${f}`);
        return soma && soma.todos > 0 ? soma.novos / soma.todos : null;
      }),
    })),
  }));
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
  /** Quota de voto novo nos votos da faixa, em 2026 e no ano de comparação. */
  novos: number | null;
  novosBase: number | null;
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
          novos: atual.novos[i] ?? null,
          novosBase: base?.novos[i] ?? null,
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
