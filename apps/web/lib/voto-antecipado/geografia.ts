/**
 * Idade por condado e por distrito (linhas `geografia` de VotoAntecipadoEstado).
 *
 * O pipeline publica, para cada unidade e ano, os votos antecipados até ao mesmo
 * dia do ciclo e os recenseados de cada faixa larga. Aqui só se dividem contagens:
 * quota da faixa nos votos da unidade, a mesma quota no ano de comparação e a
 * participação da faixa (votos / recenseados). Unidades com poucos votos ficam
 * marcadas, porque as quotas variam muito ao acaso.
 */

import type { LinhaGeografia, LinhaHistoricoGeografia } from "@intercalares/contratos";

export const FAIXAS_LARGAS = ["18-29", "30-49", "50-64", "65+"] as const;
export type FaixaLarga = (typeof FAIXAS_LARGAS)[number];
export type NivelGeografico = LinhaGeografia["nivel"];

/** Abaixo destes votos numa unidade (em qualquer dos dois anos), a quota é pouco fiável. */
export const MINIMO_VOTOS_UNIDADE = 100;

/** Faixas do momento do voto por unidade: as largas e o total. */
export const FAIXAS_MOMENTO = [...FAIXAS_LARGAS, "total"] as const;
export type FaixaMomento = (typeof FAIXAS_MOMENTO)[number];

/** Votos de habituais, de quem antecipou o voto e de eleitores novos. */
export type GruposMomento = [habituais: number, antecipacao: number, novos: number];

/** Contagens de um ano numa unidade: por faixa larga, pela ordem de FAIXAS_LARGAS, e o total. */
export interface AnoUnidade {
  ano: number;
  votos: number[];
  registados: number[];
  votosTotal: number;
  registadosTotal: number;
  /**
   * Momento do voto (linhas `historico_geografia`), pela ordem de FAIXAS_MOMENTO, face à
   * eleição de referência `anoReferencia`; `null` sem histórico individual nesse ano.
   */
  momento: { anoReferencia: number; grupos: GruposMomento[] } | null;
}

export interface UnidadeGeografica {
  nivel: NivelGeografico;
  codigo: string;
  nome: string;
  anos: AnoUnidade[];
}

const GRUPO: Partial<Record<LinhaHistoricoGeografia["grupo"], 0 | 1 | 2>> = {
  antecipado_na_referencia: 0,
  dia_eleicao_na_referencia: 1,
  absteve_se_na_referencia: 2,
  recenseado_apos_referencia: 2,
};

/**
 * Agrupa as linhas por unidade e ano. Faixas em falta contam zero; "desconhecida" fica
 * fora. O histórico por unidade junta-se às unidades e anos que já existem; como no
 * momento do estado, "sem_historico" fica fora e quem se absteve ou se recenseou depois
 * da referência conta como eleitor novo.
 */
export function agruparGeografia(
  linhas: readonly LinhaGeografia[],
  historico: readonly LinhaHistoricoGeografia[] = [],
): UnidadeGeografica[] {
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
        momento: null,
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
  for (const l of historico) {
    const g = GRUPO[l.grupo];
    const i = FAIXAS_MOMENTO.indexOf(l.faixa as FaixaMomento);
    const ano = unidades.get(`${l.nivel}:${l.codigo}`)?.anos.find((a) => a.ano === l.ano);
    if (g === undefined || i < 0 || !ano) continue;
    ano.momento ??= {
      anoReferencia: l.ano_referencia,
      grupos: FAIXAS_MOMENTO.map((): GruposMomento => [0, 0, 0]),
    };
    const grupos = ano.momento.grupos[i];
    if (grupos) grupos[g] += l.votos;
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

export interface LinhaMomentoUnidade {
  codigo: string;
  nome: string;
  /** Votos da faixa com histórico (os três grupos). */
  votos: number;
  /** Partes dos votos da faixa: habituais, antecipação e novos. */
  habituais: number | null;
  antecipacao: number | null;
  novos: number | null;
  novosBase: number | null;
  /** novos − novosBase, em fração. */
  diferenca: number | null;
  poucosVotos: boolean;
}

/** Momento do voto de uma faixa em cada unidade, por ordem da subida dos eleitores novos. */
export function linhasMomento(
  unidades: readonly UnidadeGeografica[],
  nivel: NivelGeografico,
  faixa: FaixaMomento,
  ano: number,
  anoBase: number,
): LinhaMomentoUnidade[] {
  const i = FAIXAS_MOMENTO.indexOf(faixa);
  return unidades
    .filter((u) => u.nivel === nivel)
    .flatMap((u) => {
      const atual = u.anos.find((a) => a.ano === ano)?.momento?.grupos[i];
      if (!atual) return [];
      const base = u.anos.find((a) => a.ano === anoBase)?.momento?.grupos[i];
      const votos = atual[0] + atual[1] + atual[2];
      if (votos === 0) return [];
      const votosBase = base ? base[0] + base[1] + base[2] : 0;
      const novos = razao(atual[2], votos);
      const novosBase = base ? razao(base[2], votosBase) : null;
      return [
        {
          codigo: u.codigo,
          nome: u.nome,
          votos,
          habituais: razao(atual[0], votos),
          antecipacao: razao(atual[1], votos),
          novos,
          novosBase,
          diferenca: novos !== null && novosBase !== null ? novos - novosBase : null,
          poucosVotos:
            votos < MINIMO_VOTOS_UNIDADE ||
            (base !== undefined && votosBase < MINIMO_VOTOS_UNIDADE),
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

/** Níveis com unidades, distritos primeiro. */
export const NIVEIS: readonly NivelGeografico[] = ["distrito", "condado"];

/**
 * Nível mostrado ao abrir o painel: o primeiro com dados do ano de comparação
 * (na Pensilvânia de 2022, por exemplo, só há condados). Sem nenhum, o
 * primeiro nível com unidades; `null` sem unidades.
 */
export function nivelPorOmissao(
  unidades: readonly UnidadeGeografica[],
  anoBase: number,
): NivelGeografico | null {
  const comUnidades = NIVEIS.filter((n) => unidades.some((u) => u.nivel === n));
  const comBase = comUnidades.find((n) =>
    unidades.some((u) => u.nivel === n && u.anos.some((a) => a.ano === anoBase)),
  );
  return comBase ?? comUnidades[0] ?? null;
}
