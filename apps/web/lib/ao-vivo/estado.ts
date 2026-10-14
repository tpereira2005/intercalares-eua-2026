/**
 * Dados ao vivo da noite eleitoral no browser (docs/api-ao-vivo.md).
 *
 * O HTML traz as vistas calculadas no build. Durante a noite, o browser consulta a API
 * do Worker (/api/resultados e /api/noite) e reconstrói as vistas com as mesmas funções
 * puras do build. Os ficheiros já chegam validados pelo Worker; aqui só se confirma a
 * forma mínima antes de os usar. Se a API falhar, fica o que já está no ecrã.
 */

import type { HistoricoNoite, ProjecaoNoite, ResultadosParciais } from "@intercalares/contratos";
import { construirVistaNoite } from "../noite/vista.ts";
import type { DadosNoiteEleitoral } from "../resultados/carregar.ts";
import { construirVistaResultados, type PrevisaoResultados } from "../resultados/vista.ts";

/** Intervalo entre consultas com a página visível. */
export const INTERVALO_MS = 60_000;
/** Intervalo quando a API diz que ainda não há nada publicado (antes da noite). */
export const INTERVALO_SEM_DADOS_MS = 10 * 60_000;

export const URL_RESULTADOS = "/api/resultados";
export const URL_NOITE = "/api/noite";

/** Origem declarada pelo Worker: `copia-antiga` quando a fonte falhou. */
type OrigemApi = "memoria" | "fonte" | "copia-antiga";

export interface RespostaResultados {
  origem: OrigemApi;
  confirmadoEm: string;
  parciais: ResultadosParciais;
}

export interface RespostaNoite {
  origem: OrigemApi;
  confirmadoEm: string;
  projecao: ProjecaoNoite;
  historico: HistoricoNoite | null;
}

export type Consulta<T> = { tipo: "dados"; dados: T } | { tipo: "ausente" } | { tipo: "erro" };

export type Ligacao =
  /** Ainda não houve resposta: o ecrã mostra o que veio no build. */
  | { tipo: "build" }
  /** `antiga`: a fonte ou uma das consultas falhou e há dados mais antigos à vista. */
  | { tipo: "aoVivo"; confirmadoEm: string; antiga: boolean }
  /** A API diz que ainda não há ficheiros publicados. */
  | { tipo: "semDados" }
  /** A API não respondeu: fica o que está no ecrã. */
  | { tipo: "falha" };

export interface EstadoAoVivo {
  dados: DadosNoiteEleitoral | null;
  /** Última contagem recebida da API, para recalcular a vista quando só a projeção muda. */
  parciais: ResultadosParciais | null;
  ligacao: Ligacao;
}

function objeto(valor: unknown): valor is Record<string, unknown> {
  return typeof valor === "object" && valor !== null;
}

function formaResultados(corpo: unknown): corpo is RespostaResultados {
  return (
    objeto(corpo) &&
    typeof corpo.confirmadoEm === "string" &&
    objeto(corpo.parciais) &&
    Array.isArray(corpo.parciais.unidades)
  );
}

function formaNoite(corpo: unknown): corpo is RespostaNoite {
  return (
    objeto(corpo) &&
    typeof corpo.confirmadoEm === "string" &&
    objeto(corpo.projecao) &&
    Array.isArray(corpo.projecao.corridas)
  );
}

async function consultar<T>(
  url: string,
  forma: (corpo: unknown) => corpo is T,
  buscar: typeof fetch,
): Promise<Consulta<T>> {
  try {
    const resposta = await buscar(url, { headers: { Accept: "application/json" } });
    if (resposta.status === 404) return { tipo: "ausente" };
    if (!resposta.ok) return { tipo: "erro" };
    const corpo: unknown = await resposta.json();
    return forma(corpo) ? { tipo: "dados", dados: corpo } : { tipo: "erro" };
  } catch {
    return { tipo: "erro" };
  }
}

export function consultarResultados(buscar: typeof fetch = fetch) {
  return consultar(URL_RESULTADOS, formaResultados, buscar);
}

export function consultarNoite(buscar: typeof fetch = fetch) {
  return consultar(URL_NOITE, formaNoite, buscar);
}

/** Junta as respostas da API ao que está no ecrã. Função pura, testada à parte. */
export function atualizarEstado(
  atual: EstadoAoVivo,
  resultados: Consulta<RespostaResultados>,
  noite: Consulta<RespostaNoite>,
  previsao: PrevisaoResultados | null,
): EstadoAoVivo {
  const respostas = [resultados, noite].flatMap((c) => (c.tipo === "dados" ? [c.dados] : []));
  const erro = resultados.tipo === "erro" || noite.tipo === "erro";
  if (respostas.length === 0) {
    return { ...atual, ligacao: erro ? { tipo: "falha" } : { tipo: "semDados" } };
  }
  const vistaNoite =
    noite.tipo === "dados"
      ? construirVistaNoite(noite.dados.projecao, noite.dados.historico)
      : (atual.dados?.noite ?? null);
  const parciais = resultados.tipo === "dados" ? resultados.dados.parciais : atual.parciais;
  const vistaResultados = parciais
    ? construirVistaResultados(parciais, previsao, vistaNoite)
    : (atual.dados?.resultados ?? null);
  const confirmadoEm = respostas
    .map((r) => r.confirmadoEm)
    .reduce((min, h) => (Date.parse(h) < Date.parse(min) ? h : min));
  return {
    dados: { resultados: vistaResultados, noite: vistaNoite },
    parciais,
    ligacao: {
      tipo: "aoVivo",
      confirmadoEm,
      antiga: erro || respostas.some((r) => r.origem === "copia-antiga"),
    },
  };
}
