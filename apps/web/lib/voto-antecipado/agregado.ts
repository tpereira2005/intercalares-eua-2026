/**
 * Vista dos estados sem ficheiro de eleitores gratuito (contrato
 * VotoAntecipadoAgregado): só se comparam votos com votos no mesmo dia do
 * ciclo, nunca taxas de participação (docs/metodologia/voto-antecipado-estados.md).
 *
 * Como em vista.ts, não há aqui metodologia nova: quotas e ritmos vêm do
 * pipeline; esta camada só seleciona, agrupa e ordena.
 */

import type {
  LinhaGeografia,
  PontoSerieAgregado,
  VotoAntecipadoAgregado,
} from "@intercalares/contratos";
import { agruparGeografia, type UnidadeGeografica } from "./geografia.ts";
import { PARTIDOS, type CruzamentoFaixa, type PartidoRegisto } from "./vista.ts";

export type Modalidade = "correio" | "presencial";

/**
 * Faixa etária de um estado agregado: a canónica, ou as faixas de dez anos que a fonte
 * publica (Colorado). Nunca se misturam no mesmo estado.
 */
export type FaixaAgregada = Exclude<PontoSerieAgregado["faixa"], "total" | "desconhecida">;

/** Todas as faixas possíveis, por idade; cada estado usa as que o seu ficheiro traz. */
export const FAIXAS_AGREGADAS: readonly FaixaAgregada[] = [
  "18-24",
  "25-29",
  "25-34",
  "30-39",
  "35-44",
  "40-49",
  "45-54",
  "50-64",
  "55-64",
  "65-74",
  "75+",
];

/** Faixas de dez anos da fonte, que só existem em estados como o Colorado. */
const FAIXAS_DEZ_ANOS = new Set<FaixaAgregada>(["25-34", "35-44", "45-54", "55-64"]);

export interface LinhaCategoria<C extends string> {
  categoria: C;
  votos: number;
  votosBase: number;
  quota: number | null;
  quotaBase: number | null;
  ritmo: number | null;
}

export interface ComparacaoAgregada {
  anoBase: number;
  tipo: "intercalar" | "presidencial";
  votos: number;
  /** Votos do ano de referência até ao mesmo dia do ciclo. */
  votosBase: number;
  ritmo: number | null;
  /** As faixas do ficheiro, por idade (canónicas ou de dez anos). */
  faixas: LinhaCategoria<FaixaAgregada>[];
  partidos: LinhaCategoria<PartidoRegisto>[];
  modalidades: LinhaCategoria<Modalidade>[];
}

export interface PedidosPartido {
  partido: PartidoRegisto;
  pedidos: number;
  devolvidos: number;
  pendentes: number;
  /** Fração dos pedidos já devolvida, em 2026 e no mesmo dia do ano de referência. */
  devolucao: number | null;
  devolucaoBase: number | null;
}

export interface VistaAgregada {
  tipo: "agregado";
  estado: VotoAntecipadoAgregado["estado"];
  ano: number;
  dadosAte: string;
  diasAntes: number;
  geradoEm: string;
  granularidade: VotoAntecipadoAgregado["granularidade"];
  dimensoes: VotoAntecipadoAgregado["dimensoes"];
  modalidadesFonte: Modalidade[];
  fontes: { nome: string; url: string }[];
  avisos: string[];
  /**
   * A fonte usa faixas de dez anos: os jovens (18–29) não se isolam, só os 18–24, e só
   * 18–24, 65–74 e 75+ se comparam com os outros estados.
   */
  faixasDezAnos: boolean;
  votos: number;
  ciclos: { ano: number; tipo: "intercalar" | "presidencial"; notas: string[] }[];
  /** Intercalares primeiro, da mais recente para a mais antiga; depois presidenciais. */
  comparacoes: ComparacaoAgregada[];
  /** Votos acumulados por dia do ciclo, um traço por ano (o campo chama-se taxa nos gráficos). */
  curvas: { ano: number; pontos: { dias: number; taxa: number }[] }[];
  pedidos: { anoBase: number | null; partidos: PedidosPartido[] };
  /**
   * Idade por condado e distrito, nos estados cuja fonte a dá (Pensilvânia); vazio nos
   * outros. Sem recenseados por faixa: só quotas nos votos, nunca participação.
   */
  geografia: UnidadeGeografica[];
  /**
   * Idade × partido nos votos de 2026 no dia do ficheiro, nos estados cuja série os
   * cruza (Pensilvânia, Colorado); vazio nos outros. A variação D − R é face ao mesmo
   * dia do ano de referência principal.
   */
  cruzamentos: CruzamentoFaixa<FaixaAgregada>[];
  anoCruzamentos: number | null;
}

/** Janela das curvas, igual à da Carolina do Norte. */
const DIAS_CURVA = 45;

function razao(numerador: number, denominador: number): number | null {
  return denominador > 0 ? numerador / denominador : null;
}

function linhas<C extends string>(
  dados: VotoAntecipadoAgregado,
  anoBase: number,
  dimensao: "faixa" | "partido" | "modalidade",
  ordem: readonly C[],
): LinhaCategoria<C>[] {
  return ordem.flatMap((categoria) => {
    const l = dados.comparacao.find(
      (x) => x.ano_base === anoBase && x.dimensao === dimensao && x.categoria === categoria,
    );
    return l
      ? [
          {
            categoria,
            votos: l.votos,
            votosBase: l.votos_base,
            quota: l.quota,
            quotaBase: l.quota_base,
            ritmo: l.ritmo,
          },
        ]
      : [];
  });
}

function comparacoes(dados: VotoAntecipadoAgregado): ComparacaoAgregada[] {
  const anos = [...new Set(dados.comparacao.map((l) => l.ano_base))];
  return anos
    .flatMap((anoBase) => {
      const ciclo = dados.ciclos.find((c) => c.ano === anoBase);
      // O total é a mesma linha em qualquer dimensão; usa a primeira que existir.
      const total = dados.comparacao.find((l) => l.ano_base === anoBase && l.categoria === "total");
      if (!ciclo || !total) return [];
      return [
        {
          anoBase,
          tipo: ciclo.tipo,
          votos: total.votos,
          votosBase: total.votos_base,
          ritmo: total.ritmo,
          faixas: linhas(dados, anoBase, "faixa", FAIXAS_AGREGADAS),
          partidos: linhas(dados, anoBase, "partido", PARTIDOS),
          modalidades: linhas(dados, anoBase, "modalidade", ["correio", "presencial"] as const),
        },
      ];
    })
    .sort((a, b) => (a.tipo === b.tipo ? b.anoBase - a.anoBase : a.tipo === "intercalar" ? -1 : 1));
}

function curvas(dados: VotoAntecipadoAgregado): VistaAgregada["curvas"] {
  const totais = dados.serie.filter(
    (p) =>
      p.faixa === "total" &&
      p.partido === "total" &&
      p.modalidade === "total" &&
      p.dias_antes <= DIAS_CURVA,
  );
  return [...new Set(totais.map((p) => p.ano))]
    .map((ano) => ({
      ano,
      pontos: totais
        .filter((p) => p.ano === ano)
        .map((p) => ({ dias: p.dias_antes, taxa: p.votos }))
        .sort((a, b) => b.dias - a.dias),
    }))
    .filter((c) => c.pontos.length > 1);
}

function pedidos(dados: VotoAntecipadoAgregado, anoBase: number | null): VistaAgregada["pedidos"] {
  const de = (ano: number, partido: PartidoRegisto) =>
    dados.pedidos.find((l) => l.ano === ano && l.faixa === "total" && l.partido === partido);
  const temBase = anoBase !== null && dados.pedidos.some((l) => l.ano === anoBase);
  return {
    anoBase: temBase ? anoBase : null,
    partidos: PARTIDOS.flatMap((partido) => {
      const atual = de(dados.ano, partido);
      if (!atual) return [];
      const base = temBase ? de(anoBase, partido) : undefined;
      return [
        {
          partido,
          pedidos: atual.pedidos,
          devolvidos: atual.devolvidos,
          pendentes: atual.pendentes,
          devolucao: razao(atual.devolvidos, atual.pedidos),
          devolucaoBase: base ? razao(base.devolvidos, base.pedidos) : null,
        },
      ];
    }),
  };
}

/**
 * Linhas de idade por unidade (as que têm `partido = "total"`) no formato das do
 * ficheiro de eleitores, com zero recenseados: a fonte não os dá por faixa.
 */
function geografia(dados: VotoAntecipadoAgregado): UnidadeGeografica[] {
  const linhas = dados.geografia.filter((l) => l.partido === "total");
  if (!linhas.some((l) => l.faixa !== undefined && l.faixa !== "total")) return [];
  return agruparGeografia(
    linhas.map((l): LinhaGeografia => ({
      ano: l.ano,
      nivel: l.nivel,
      codigo: l.codigo,
      nome: l.nome,
      faixa: l.faixa ?? "total",
      votos: l.votos,
      registados: 0,
    })),
  );
}

type PontoDia = PontoSerieAgregado;

function quotasPartido(
  pontos: readonly PontoDia[],
  ano: number,
  faixa: FaixaAgregada,
): Record<PartidoRegisto, number> | null {
  const daFaixa = pontos.filter(
    (p) => p.ano === ano && p.faixa === faixa && p.partido !== "total" && p.modalidade === "total",
  );
  const total = daFaixa.reduce((s, p) => s + p.votos, 0);
  if (total <= 0) return null;
  const quota = (partido: PartidoRegisto) =>
    daFaixa.filter((p) => p.partido === partido).reduce((s, p) => s + p.votos, 0) / total;
  return {
    dem: quota("dem"),
    rep: quota("rep"),
    nao_afiliado: quota("nao_afiliado"),
    outro: quota("outro"),
  };
}

/** Linhas do cruzamento de idade com partido e com modalidade, no dia do ficheiro. */
function cruzamentos(
  dados: VotoAntecipadoAgregado,
  anoBase: number | null,
): CruzamentoFaixa<FaixaAgregada>[] {
  const dia = dados.serie.filter((p) => p.dias_antes === dados.dias_antes);
  return FAIXAS_AGREGADAS.flatMap((faixa) => {
    const partidos = quotasPartido(dia, dados.ano, faixa);
    if (partidos === null) return [];
    const base = anoBase === null ? null : quotasPartido(dia, anoBase, faixa);
    const modalidades = dia.filter(
      (p) =>
        p.ano === dados.ano &&
        p.faixa === faixa &&
        p.partido === "total" &&
        p.modalidade !== "total",
    );
    const correio = modalidades
      .filter((p) => p.modalidade === "correio")
      .reduce((s, p) => s + p.votos, 0);
    return [
      {
        faixa,
        partidos,
        variacaoDemRep: base === null ? null : partidos.dem - partidos.rep - (base.dem - base.rep),
        correio: razao(
          correio,
          modalidades.reduce((s, p) => s + p.votos, 0),
        ),
      },
    ];
  });
}

export function construirVistaAgregada(dados: VotoAntecipadoAgregado): VistaAgregada {
  const lista = comparacoes(dados);
  // A variação D − R compara com o ano de referência principal, se a série o cruzar.
  const anoPrincipal = lista[0]?.anoBase ?? null;
  const anoCruzamentos =
    anoPrincipal !== null &&
    dados.serie.some(
      (p) =>
        p.ano === anoPrincipal &&
        p.dias_antes === dados.dias_antes &&
        p.faixa !== "total" &&
        p.partido !== "total",
    )
      ? anoPrincipal
      : null;
  return {
    tipo: "agregado",
    estado: dados.estado,
    ano: dados.ano,
    dadosAte: dados.dados_ate,
    diasAntes: dados.dias_antes,
    geradoEm: dados.metadados.gerado_em,
    granularidade: dados.granularidade,
    dimensoes: dados.dimensoes,
    modalidadesFonte: [...dados.modalidades],
    fontes: dados.metadados.fontes.map((f) => ({ nome: f.nome, url: f.url })),
    avisos: [...dados.avisos],
    faixasDezAnos: dados.comparacao.some(
      (l) => l.dimensao === "faixa" && FAIXAS_DEZ_ANOS.has(l.categoria as FaixaAgregada),
    ),
    votos: dados.ciclos.find((c) => c.ano === dados.ano)?.votos ?? 0,
    ciclos: dados.ciclos.map((c) => ({ ano: c.ano, tipo: c.tipo, notas: [...c.notas] })),
    comparacoes: lista,
    curvas: curvas(dados),
    pedidos: pedidos(dados, lista[0]?.anoBase ?? null),
    geografia: geografia(dados),
    cruzamentos: cruzamentos(dados, anoCruzamentos),
    anoCruzamentos,
  };
}
