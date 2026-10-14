/**
 * Dados ao vivo da noite eleitoral no browser (docs/api-ao-vivo.md).
 *
 * O HTML traz as vistas calculadas no build. Durante a noite, o browser consulta a API
 * do Worker (/api/resultados e /api/noite) e reconstrói as vistas com as mesmas funções
 * puras do build. Os ficheiros já chegam validados pelo Worker; aqui só se confirma a
 * forma mínima antes de os usar. Se a API falhar, o browser lê o espelho de emergência no
 * GitHub Pages (espelho.ts); se também falhar, fica o que já está no ecrã.
 */

import type {
  ChamadasRedacoes,
  HistoricoNoite,
  ProjecaoNoite,
  ResultadosParciais,
} from "@intercalares/contratos";
import { construirVistaNoite } from "../noite/vista.ts";
import type { DadosNoiteEleitoral } from "../resultados/carregar.ts";
import { construirVistaResultados, type PrevisaoResultados } from "../resultados/vista.ts";

/** Intervalo entre consultas com a página visível. */
export const INTERVALO_MS = 60_000;
/** Intervalo quando a API diz que ainda não há nada publicado (antes da noite). */
export const INTERVALO_SEM_DADOS_MS = 10 * 60_000;

export const URL_RESULTADOS = "/api/resultados";
export const URL_NOITE = "/api/noite";

/** Espelho de emergência no GitHub Pages; `URL_ESPELHO` no build substitui-o. */
export const URL_ESPELHO = (
  process.env.NEXT_PUBLIC_URL_ESPELHO ??
  "https://tpereira2005.github.io/intercalares-eua-2026/espelho"
).replace(/\/$/, "");

/**
 * Origem declarada pelo Worker (`copia-antiga` quando a fonte falhou) ou `espelho`
 * quando a resposta veio da cópia de emergência.
 */
type OrigemApi = "memoria" | "fonte" | "copia-antiga" | "espelho";

export interface RespostaResultados {
  origem: OrigemApi;
  confirmadoEm: string;
  parciais: ResultadosParciais;
  /** Ausente nas respostas anteriores às chamadas; `null` sem chamadas registadas. */
  chamadas?: ChamadasRedacoes | null;
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
  /**
   * `antiga`: a fonte ou uma das consultas falhou e há dados mais antigos à vista.
   * `espelho`: a API não respondeu e os dados vêm da cópia de emergência.
   */
  | { tipo: "aoVivo"; confirmadoEm: string; antiga: boolean; espelho: boolean }
  /** A API diz que ainda não há ficheiros publicados. */
  | { tipo: "semDados" }
  /** A API não respondeu: fica o que está no ecrã. */
  | { tipo: "falha" };

export interface EstadoAoVivo {
  dados: DadosNoiteEleitoral | null;
  /** Última contagem recebida da API, para recalcular a vista quando só a projeção muda. */
  parciais: ResultadosParciais | null;
  /** Últimas chamadas das redações recebidas, para as manter quando só a projeção muda. */
  chamadas: ChamadasRedacoes | null;
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

/**
 * Consulta a API e, se ela falhar (limite atingido, erro ou sem rede), o espelho. Um
 * `404` da API quer dizer que ainda não há nada publicado: aí não se vai ao espelho.
 */
async function consultarComEspelho<T>(
  url: string,
  urlEspelho: string,
  forma: (corpo: unknown) => corpo is T,
  buscar: typeof fetch,
): Promise<Consulta<T>> {
  const api = await consultar(url, forma, buscar);
  if (api.tipo !== "erro") return api;
  const espelho = await consultar(urlEspelho, forma, buscar);
  return espelho.tipo === "dados" ? espelho : api;
}

export function consultarResultados(buscar: typeof fetch = fetch) {
  return consultarComEspelho(
    URL_RESULTADOS,
    `${URL_ESPELHO}/resultados.json`,
    formaResultados,
    buscar,
  );
}

export function consultarNoite(buscar: typeof fetch = fetch) {
  return consultarComEspelho(URL_NOITE, `${URL_ESPELHO}/noite.json`, formaNoite, buscar);
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
  const chamadas =
    resultados.tipo === "dados" ? (resultados.dados.chamadas ?? null) : atual.chamadas;
  const vistaResultados = parciais
    ? construirVistaResultados(parciais, previsao, vistaNoite, chamadas)
    : (atual.dados?.resultados ?? null);
  const confirmadoEm = respostas
    .map((r) => r.confirmadoEm)
    .reduce((min, h) => (Date.parse(h) < Date.parse(min) ? h : min));
  return {
    dados: { resultados: vistaResultados, noite: vistaNoite },
    parciais,
    chamadas,
    ligacao: {
      tipo: "aoVivo",
      confirmadoEm,
      antiga: erro || respostas.some((r) => r.origem === "copia-antiga"),
      espelho: respostas.some((r) => r.origem === "espelho"),
    },
  };
}
