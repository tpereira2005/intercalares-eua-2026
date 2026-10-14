/**
 * Sinal etário do voto antecipado (contrato DiagnosticoIdade, plano secção 6.4),
 * publicado pelo modelo na Release `dados-voto-antecipado` como `idade-<estado>.json`.
 *
 * É um diagnóstico mostrado, com peso zero na previsão. O modelo só o publica a partir de
 * 14 dias antes da eleição e com pelo menos 200 000 votos antecipados; até lá, a página
 * diz que ainda é cedo. Um ficheiro que não cumpre o contrato faz falhar o build.
 */

import { existsSync, readFileSync } from "node:fs";
import path from "node:path";
import type { CodigoEstado, DiagnosticoIdade, GrupoIdade } from "@intercalares/contratos";
import { DadosInvalidos, obterValidador } from "../validacao.ts";
import { FAIXAS, type FaixaEtaria } from "./vista.ts";

export const PASTA_IDADE = "dados/idade";
/** Estados para os quais o modelo calcula o sinal etário. */
export const ESTADOS_COM_SINAL: ReadonlySet<CodigoEstado> = new Set<CodigoEstado>(["NC"]);

export type PartidoIdade = GrupoIdade["partido"];
export const PARTIDOS_IDADE: readonly PartidoIdade[] = ["dem", "rep", "nao_afiliado"];

export interface FaixaIdadeVista {
  faixa: FaixaEtaria;
  /** Somas das quotas dos partidos da faixa. */
  quotaAntecipado: number;
  quotaProjetada: number;
  quotaReferencia: number;
  partidos: {
    partido: PartidoIdade;
    quotaProjetada: number;
    quotaReferencia: number;
    margem: number;
    margemMinima: number;
    margemMaxima: number;
  }[];
}

export interface VistaIdade {
  estado: CodigoEstado;
  ano: number;
  anoReferencia: number;
  dataDados: string;
  diasAntes: number;
  votos: number;
  /** Pontos de margem D − R face à referência; positivo puxa para os democratas. */
  efeito: number;
  efeitoP10: number;
  efeitoP90: number;
  inclinacaoProjetada: number;
  inclinacaoReferencia: number;
  erroBacktest: number;
  faixas: FaixaIdadeVista[];
  backtests: {
    ano: number;
    referencias: number[];
    real: number;
    projetada: number;
  }[];
  fontes: { nome: string; url: string }[];
  notas: string[];
}

/** Lê e valida o ficheiro; `null` quando não existe. */
export function lerIdade(caminho: string): DiagnosticoIdade | null {
  const absoluto = path.resolve(process.cwd(), caminho);
  if (!existsSync(absoluto)) return null;
  const dados: unknown = JSON.parse(readFileSync(absoluto, "utf-8"));
  const valido = obterValidador("DiagnosticoIdade");
  if (!valido(dados)) {
    throw new DadosInvalidos(caminho, "DiagnosticoIdade", valido.errors?.slice(0, 5));
  }
  return dados as DiagnosticoIdade;
}

export function construirVistaIdade(dados: DiagnosticoIdade): VistaIdade {
  const faixas = FAIXAS.flatMap((faixa) => {
    const grupos = dados.grupos.filter((g) => g.faixa === faixa);
    if (grupos.length === 0) return [];
    const soma = (campo: "quota_antecipado" | "quota_projetada" | "quota_final_referencia") =>
      grupos.reduce((s, g) => s + g[campo], 0);
    return [
      {
        faixa,
        quotaAntecipado: soma("quota_antecipado"),
        quotaProjetada: soma("quota_projetada"),
        quotaReferencia: soma("quota_final_referencia"),
        partidos: PARTIDOS_IDADE.flatMap((partido) => {
          const g = grupos.find((x) => x.partido === partido);
          return g
            ? [
                {
                  partido,
                  quotaProjetada: g.quota_projetada,
                  quotaReferencia: g.quota_final_referencia,
                  margem: g.margem,
                  margemMinima: g.margem_minima,
                  margemMaxima: g.margem_maxima,
                },
              ]
            : [];
        }),
      },
    ];
  });
  return {
    estado: dados.estado,
    ano: dados.ano,
    anoReferencia: dados.ano_referencia,
    dataDados: dados.data_dados,
    diasAntes: dados.dias_antes,
    votos: dados.votos_antecipados,
    efeito: dados.efeito,
    efeitoP10: dados.efeito_p10,
    efeitoP90: dados.efeito_p90,
    inclinacaoProjetada: dados.inclinacao_projetada,
    inclinacaoReferencia: dados.inclinacao_referencia,
    erroBacktest: dados.erro_backtest,
    faixas,
    backtests: [...dados.backtests]
      .sort((a, b) => b.ano - a.ano)
      .map((b) => ({
        ano: b.ano,
        referencias: [...b.referencias],
        real: b.inclinacao_real,
        projetada: b.inclinacao_projetada,
      })),
    fontes: dados.metadados.fontes
      .filter((f, i, todas) => todas.findIndex((g) => g.nome === f.nome) === i)
      .map((f) => ({ nome: f.nome, url: f.url })),
    notas: [...dados.notas],
  };
}

/**
 * Sinal etário de um estado: `undefined` quando o modelo não o calcula para o estado,
 * `null` quando ainda não foi publicado (é cedo) e a vista quando existe.
 */
export function carregarIdade(estado: CodigoEstado, pasta?: string): VistaIdade | null | undefined {
  if (!ESTADOS_COM_SINAL.has(estado)) return undefined;
  const base = pasta ?? process.env.DADOS_IDADE ?? PASTA_IDADE;
  const dados = lerIdade(path.join(base, `${estado.toLowerCase()}.json`));
  return dados ? construirVistaIdade(dados) : null;
}
