/**
 * Vista dos estados sem ficheiro de eleitores gratuito (contrato
 * VotoAntecipadoAgregado): só se comparam votos com votos no mesmo dia do
 * ciclo, nunca taxas de participação (docs/metodologia/voto-antecipado-estados.md).
 *
 * Como em vista.ts, não há aqui metodologia nova: quotas e ritmos vêm do
 * pipeline; esta camada só seleciona, agrupa e ordena.
 */

import type { VotoAntecipadoAgregado } from "@intercalares/contratos";
import { FAIXAS, PARTIDOS, type FaixaEtaria, type PartidoRegisto } from "./vista.ts";

export type Modalidade = "correio" | "presencial";

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
  faixas: LinhaCategoria<FaixaEtaria>[];
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
  votos: number;
  ciclos: { ano: number; tipo: "intercalar" | "presidencial"; notas: string[] }[];
  /** Intercalares primeiro, da mais recente para a mais antiga; depois presidenciais. */
  comparacoes: ComparacaoAgregada[];
  /** Votos acumulados por dia do ciclo, um traço por ano (o campo chama-se taxa nos gráficos). */
  curvas: { ano: number; pontos: { dias: number; taxa: number }[] }[];
  pedidos: { anoBase: number | null; partidos: PedidosPartido[] };
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
          faixas: linhas(dados, anoBase, "faixa", FAIXAS),
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

export function construirVistaAgregada(dados: VotoAntecipadoAgregado): VistaAgregada {
  const lista = comparacoes(dados);
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
    votos: dados.ciclos.find((c) => c.ano === dados.ano)?.votos ?? 0,
    ciclos: dados.ciclos.map((c) => ({ ano: c.ano, tipo: c.tipo, notas: [...c.notas] })),
    comparacoes: lista,
    curvas: curvas(dados),
    pedidos: pedidos(dados, lista[0]?.anoBase ?? null),
  };
}
