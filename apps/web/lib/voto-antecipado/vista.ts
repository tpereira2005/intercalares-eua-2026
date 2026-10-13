/**
 * Transforma o ficheiro publicado pelo pipeline (VotoAntecipadoEstado) na vista
 * compacta que a página do voto antecipado usa. Corre no build: o browser só
 * recebe o que os gráficos mostram, não o ficheiro inteiro.
 *
 * Não há aqui metodologia nova: taxas, quotas, desvios e efeitos vêm já
 * calculados pelo pipeline (docs/metodologia/voto-antecipado.md). Esta camada
 * só seleciona, agrupa e ordena.
 */

import { agruparGeografia, type UnidadeGeografica } from "./geografia.ts";
import type {
  LinhaComparacao,
  LinhaCruzamento,
  LinhaHistorico,
  LinhaReserva,
  PontoSerie,
  VotoAntecipadoEstado,
} from "@intercalares/contratos";

export type FaixaEtaria = Exclude<LinhaComparacao["faixa"], "total" | "desconhecida">;
export type PartidoRegisto = Exclude<LinhaReserva["partido"], "total">;

export const FAIXAS: readonly FaixaEtaria[] = [
  "18-24",
  "25-29",
  "30-39",
  "40-49",
  "50-64",
  "65-74",
  "75+",
];
export const PARTIDOS: readonly PartidoRegisto[] = ["dem", "rep", "nao_afiliado", "outro"];

export interface LinhaFaixa {
  faixa: FaixaEtaria;
  votos: number;
  /** Votos esperados ao ritmo do ano de referência no mesmo dia. */
  esperado: number;
  quota: number;
  quotaBase: number;
  taxa: number | null;
  taxaBase: number | null;
  desvio: number | null;
  efeitoRecenseamento: number;
  efeitoParticipacao: number;
}

export interface ComparacaoAno {
  anoBase: number;
  tipo: "intercalar" | "presidencial";
  votos: number;
  votosBase: number;
  registados: number;
  registadosBase: number;
  /** Variação dos votos face ao mesmo dia do ano de referência. */
  variacaoVotos: number | null;
  faixas: LinhaFaixa[];
}

export interface MomentoFaixa {
  faixa: FaixaEtaria | "total";
  /** Quotas dos votos de 2026 de cada grupo; somam 1. */
  habituais: number;
  antecipacao: number;
  novos: number;
  votos: number;
}

export interface MomentoAno {
  ano: number;
  /** Eleição usada para classificar cada eleitor (ex.: 2022 para 2026). */
  anoReferencia: number | null;
  faixas: MomentoFaixa[];
}

export interface PontoCurva {
  dias: number;
  taxa: number;
}

export interface CurvaAno {
  ano: number;
  pontos: PontoCurva[];
}

export interface CruzamentoFaixa {
  faixa: FaixaEtaria;
  /** Quota de cada partido nos votos da faixa em 2026. */
  partidos: Record<PartidoRegisto, number>;
  /** Diferença D − R (em quota) em 2026 menos a mesma diferença no ano de referência. */
  variacaoDemRep: number | null;
  /** Quota do correio nos votos da faixa em 2026. */
  correio: number | null;
}

export interface ReservaPartido {
  partido: PartidoRegisto;
  habituais: number;
  jaVotaram: number;
  restantes: number;
  /** Fração dos habituais que já votou em 2026 e no mesmo dia do ano de referência. */
  mobilizacao: number | null;
  mobilizacaoBase: number | null;
}

export interface Ciclo {
  ano: number;
  tipo: "intercalar" | "presidencial";
  notas: string[];
}

export interface VistaVotoAntecipado {
  estado: VotoAntecipadoEstado["estado"];
  ano: number;
  dadosAte: string;
  diasAntes: number;
  geradoEm: string;
  fontes: { nome: string; url: string }[];
  avisos: string[];
  votos: number;
  registados: number;
  inicioPresencialDiasAntes: number | null;
  ciclos: Ciclo[];
  comparacoes: ComparacaoAno[];
  /** Ano de referência do histórico individual (ex.: 2022), quando existe. */
  anoReferenciaHistorico: number | null;
  /** Momento do voto em 2026 e nos anos de referência com histórico, no mesmo dia do ciclo. */
  momento: MomentoAno[];
  /** Curvas de participação acumulada por faixa (e "total"), um traço por ano. */
  curvas: Record<FaixaEtaria | "total", CurvaAno[]>;
  cruzamentos: CruzamentoFaixa[];
  /** Ano de referência da variação D − R nos cruzamentos. */
  anoCruzamentos: number | null;
  reserva: { anoBase: number | null; partidos: ReservaPartido[] };
  /** Votos e recenseados por faixa larga em cada condado e distrito, no mesmo dia do ciclo. */
  geografia: UnidadeGeografica[];
}

/** Janela das curvas: o voto antecipado relevante cabe nos últimos 45 dias. */
export const DIAS_CURVA = 45;

function razao(numerador: number, denominador: number): number | null {
  return denominador > 0 ? numerador / denominador : null;
}

function somar<T>(linhas: readonly T[], campo: (linha: T) => number): number {
  return linhas.reduce((total, linha) => total + campo(linha), 0);
}

function eFaixa(faixa: string): faixa is FaixaEtaria {
  return (FAIXAS as readonly string[]).includes(faixa);
}

function comparacoes(dados: VotoAntecipadoEstado): ComparacaoAno[] {
  const porAno = new Map<number, LinhaComparacao[]>();
  for (const linha of dados.comparacao) {
    porAno.set(linha.ano_base, [...(porAno.get(linha.ano_base) ?? []), linha]);
  }
  return [...porAno.entries()].map(([anoBase, linhas]) => {
    const faixas = linhas.filter((linha) => eFaixa(linha.faixa));
    const votos = somar(faixas, (l) => l.votos);
    const votosBase = somar(faixas, (l) => l.votos_base);
    const ciclo = dados.ciclos.find((c) => c.ano === anoBase);
    return {
      anoBase,
      tipo: ciclo?.tipo ?? "intercalar",
      votos,
      votosBase,
      registados: somar(faixas, (l) => l.registados),
      registadosBase: somar(faixas, (l) => l.registados_base),
      variacaoVotos: votosBase > 0 ? votos / votosBase - 1 : null,
      faixas: FAIXAS.flatMap((faixa) => {
        const linha = faixas.find((l) => l.faixa === faixa);
        return linha
          ? [
              {
                faixa,
                votos: linha.votos,
                esperado: linha.esperado,
                quota: linha.quota,
                quotaBase: linha.quota_base,
                taxa: linha.taxa,
                taxaBase: linha.taxa_base,
                desvio: linha.desvio,
                efeitoRecenseamento: linha.efeito_recenseamento,
                efeitoParticipacao: linha.efeito_participacao,
              },
            ]
          : [];
      }),
    };
  });
}

function momentoAno(linhas: readonly LinhaHistorico[], ano: number): MomentoFaixa[] {
  const doAno = linhas.filter((linha) => linha.ano === ano);
  const grupos = (faixa: string) => {
    const daFaixa = doAno.filter((l) => faixa === "total" || l.faixa === faixa);
    const habituais = somar(
      daFaixa.filter((l) => l.grupo === "antecipado_na_referencia"),
      (l) => l.votos,
    );
    const antecipacao = somar(
      daFaixa.filter((l) => l.grupo === "dia_eleicao_na_referencia"),
      (l) => l.votos,
    );
    const novos = somar(
      daFaixa.filter(
        (l) => l.grupo === "absteve_se_na_referencia" || l.grupo === "recenseado_apos_referencia",
      ),
      (l) => l.votos,
    );
    return { habituais, antecipacao, novos };
  };
  const faixas: (FaixaEtaria | "total")[] = [...FAIXAS, "total"];
  return faixas.flatMap((faixa) => {
    const g = grupos(faixa);
    const votos = g.habituais + g.antecipacao + g.novos;
    if (votos === 0) return [];
    return [
      {
        faixa,
        habituais: g.habituais / votos,
        antecipacao: g.antecipacao / votos,
        novos: g.novos / votos,
        votos,
      },
    ];
  });
}

function curvas(serie: readonly PontoSerie[]): VistaVotoAntecipado["curvas"] {
  const totais = serie.filter(
    (p) =>
      p.partido === "total" &&
      p.modalidade === "total" &&
      p.dias_antes >= 0 &&
      p.dias_antes <= DIAS_CURVA,
  );
  const anos = [...new Set(totais.map((p) => p.ano))].sort((a, b) => b - a);
  const curvaDe = (faixa: FaixaEtaria | "total"): CurvaAno[] =>
    anos.map((ano) => ({
      ano,
      pontos: totais
        .filter((p) => p.ano === ano && p.faixa === faixa)
        .flatMap((p) => {
          const taxa = razao(p.votos, p.registados);
          return taxa === null ? [] : [{ dias: p.dias_antes, taxa }];
        })
        .sort((a, b) => b.dias - a.dias),
    }));
  const porFaixa = Object.fromEntries(FAIXAS.map((faixa) => [faixa, curvaDe(faixa)])) as Record<
    FaixaEtaria,
    CurvaAno[]
  >;
  return { ...porFaixa, total: curvaDe("total") };
}

function quotasPartido(
  linhas: readonly LinhaCruzamento[],
  ano: number,
  faixa: FaixaEtaria,
): Record<PartidoRegisto, number> | null {
  const daFaixa = linhas.filter(
    (l) => l.ano === ano && l.dimensao === "partido" && l.faixa === faixa,
  );
  const total = somar(daFaixa, (l) => l.votos);
  if (total === 0) return null;
  const quota = (partido: PartidoRegisto) =>
    somar(
      daFaixa.filter((l) => l.categoria === partido),
      (l) => l.votos,
    ) / total;
  return {
    dem: quota("dem"),
    rep: quota("rep"),
    nao_afiliado: quota("nao_afiliado"),
    outro: quota("outro"),
  };
}

function cruzamentos(
  linhas: readonly LinhaCruzamento[],
  ano: number,
  anoBase: number | null,
): CruzamentoFaixa[] {
  return FAIXAS.flatMap((faixa) => {
    const partidos = quotasPartido(linhas, ano, faixa);
    if (partidos === null) return [];
    const base = anoBase === null ? null : quotasPartido(linhas, anoBase, faixa);
    const modalidade = linhas.filter(
      (l) => l.ano === ano && l.dimensao === "modalidade" && l.faixa === faixa,
    );
    const votosModalidade = somar(modalidade, (l) => l.votos);
    return [
      {
        faixa,
        partidos,
        variacaoDemRep: base === null ? null : partidos.dem - partidos.rep - (base.dem - base.rep),
        correio: razao(
          somar(
            modalidade.filter((l) => l.categoria === "correio"),
            (l) => l.votos,
          ),
          votosModalidade,
        ),
      },
    ];
  });
}

function reserva(
  linhas: readonly LinhaReserva[],
  ano: number,
  anoBase: number | null,
): VistaVotoAntecipado["reserva"] {
  const linha = (a: number, partido: PartidoRegisto) =>
    linhas.find((l) => l.ano === a && l.faixa === "total" && l.partido === partido);
  return {
    anoBase,
    partidos: PARTIDOS.flatMap((partido) => {
      const atual = linha(ano, partido);
      if (!atual) return [];
      const base = anoBase === null ? undefined : linha(anoBase, partido);
      return [
        {
          partido,
          habituais: atual.habituais,
          jaVotaram: atual.ja_votaram,
          restantes: atual.restantes,
          mobilizacao: razao(atual.ja_votaram, atual.habituais),
          mobilizacaoBase: base ? razao(base.ja_votaram, base.habituais) : null,
        },
      ];
    }),
  };
}

export function construirVista(dados: VotoAntecipadoEstado): VistaVotoAntecipado {
  const cicloAtual = dados.ciclos.find((c) => c.ano === dados.ano);
  const lista = comparacoes(dados);
  // A comparação principal é a intercalar mais recente (ex.: 2022 para 2026).
  const principal =
    lista.filter((c) => c.tipo === "intercalar").sort((a, b) => b.anoBase - a.anoBase)[0]
      ?.anoBase ?? null;
  const anosReserva = new Set(dados.reserva.map((l) => l.ano));
  return {
    estado: dados.estado,
    ano: dados.ano,
    dadosAte: dados.dados_ate,
    diasAntes: dados.dias_antes,
    geradoEm: dados.metadados.gerado_em,
    fontes: dados.metadados.fontes.map((f) => ({ nome: f.nome, url: f.url })),
    avisos: [...dados.avisos],
    votos: cicloAtual?.votos_antecipados ?? 0,
    registados: cicloAtual?.registados ?? 0,
    inicioPresencialDiasAntes: cicloAtual?.inicio_presencial_dias_antes ?? null,
    ciclos: dados.ciclos.map((c) => ({ ano: c.ano, tipo: c.tipo, notas: [...c.notas] })),
    comparacoes: lista.sort((a, b) =>
      a.tipo === b.tipo ? b.anoBase - a.anoBase : a.tipo === "intercalar" ? -1 : 1,
    ),
    anoReferenciaHistorico: cicloAtual?.ano_referencia_historico ?? null,
    momento: [...new Set(dados.historico.map((l) => l.ano))]
      .sort((a, b) => (a === dados.ano ? -1 : b === dados.ano ? 1 : b - a))
      .map((ano) => ({
        ano,
        anoReferencia: dados.historico.find((l) => l.ano === ano)?.ano_referencia ?? null,
        faixas: momentoAno(dados.historico, ano),
      })),
    curvas: curvas(dados.serie),
    cruzamentos: cruzamentos(dados.cruzamentos, dados.ano, principal),
    anoCruzamentos: principal,
    reserva: reserva(
      dados.reserva,
      dados.ano,
      principal !== null && anosReserva.has(principal) ? principal : null,
    ),
    geografia: agruparGeografia(dados.geografia),
  };
}
