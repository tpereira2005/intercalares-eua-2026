/**
 * Dados ao vivo da noite eleitoral no browser (docs/api-ao-vivo.md).
 *
 * O HTML traz as vistas calculadas no build. Durante a noite, o browser consulta a API
 * do Worker (um só pedido, /api/ao-vivo) e reconstrói as vistas com as mesmas funções
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

/** Intervalo mínimo e máximo aceites quando o Worker sugere um (`intervaloS`). */
const INTERVALO_MIN_MS = 30_000;
const INTERVALO_MAX_MS = 10 * 60_000;
/** Teto do recuo exponencial depois de falhas seguidas. */
export const ESPERA_MAXIMA_RECUO_MS = 5 * 60_000;
/** Variação aleatória do intervalo, para os browsers não ficarem sincronizados. */
const VARIACAO = 0.1;

export const URL_AO_VIVO = "/api/ao-vivo";
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

export interface ConsultaAoVivo {
  resultados: Consulta<RespostaResultados>;
  noite: Consulta<RespostaNoite>;
  /** Intervalo sugerido pelo Worker, já limitado a 30 s-10 min; `null` se não veio. */
  intervaloMs: number | null;
}

type ApiAoVivo =
  | ({ tipo: "ok" } & ConsultaAoVivo)
  /** 404: ainda não há nada publicado. */
  | { tipo: "ausente" }
  | { tipo: "erro" };

function parte<T>(valor: unknown, forma: (corpo: unknown) => corpo is T): Consulta<T> | null {
  if (valor === null) return { tipo: "ausente" };
  return forma(valor) ? { tipo: "dados", dados: valor } : null;
}

function intervaloSugerido(valor: unknown): number | null {
  if (typeof valor !== "number" || !Number.isFinite(valor) || valor <= 0) return null;
  return Math.min(INTERVALO_MAX_MS, Math.max(INTERVALO_MIN_MS, valor * 1000));
}

async function consultarApi(buscar: typeof fetch): Promise<ApiAoVivo> {
  try {
    const resposta = await buscar(URL_AO_VIVO, { headers: { Accept: "application/json" } });
    if (resposta.status === 404) return { tipo: "ausente" };
    if (!resposta.ok) return { tipo: "erro" };
    const corpo: unknown = await resposta.json();
    if (!objeto(corpo)) return { tipo: "erro" };
    const resultados = parte(corpo.resultados, formaResultados);
    const noite = parte(corpo.noite, formaNoite);
    if (!resultados || !noite) return { tipo: "erro" };
    return { tipo: "ok", resultados, noite, intervaloMs: intervaloSugerido(corpo.intervaloS) };
  } catch {
    return { tipo: "erro" };
  }
}

/**
 * Um só pedido à API (`/api/ao-vivo`) com as duas partes. Se a API falhar (limite atingido,
 * erro, forma inesperada ou sem rede), lê o espelho (resultados.json e noite.json). Um `404`
 * quer dizer que ainda não há nada publicado: aí não se vai ao espelho.
 */
export async function consultarAoVivo(buscar: typeof fetch = fetch): Promise<ConsultaAoVivo> {
  const api = await consultarApi(buscar);
  if (api.tipo === "ok") return api;
  if (api.tipo === "ausente") {
    return { resultados: { tipo: "ausente" }, noite: { tipo: "ausente" }, intervaloMs: null };
  }
  const [resultados, noite] = await Promise.all([
    consultar(`${URL_ESPELHO}/resultados.json`, formaResultados, buscar),
    consultar(`${URL_ESPELHO}/noite.json`, formaNoite, buscar),
  ]);
  return { resultados, noite, intervaloMs: null };
}

/**
 * A consulta falhou: nada chegou (só erros) ou os dados vieram do espelho. Conta para o
 * recuo exponencial; uma resposta da API (mesmo `404`) repõe o intervalo normal.
 */
export function consultaFalhou(
  resultados: Consulta<RespostaResultados>,
  noite: Consulta<RespostaNoite>,
): boolean {
  const consultas = [resultados, noite];
  if (consultas.some((c) => c.tipo === "dados" && c.dados.origem === "espelho")) return true;
  return consultas.some((c) => c.tipo === "erro") && consultas.every((c) => c.tipo !== "dados");
}

/**
 * Espera até à próxima consulta: `base` com recuo exponencial (duplica a cada falha
 * seguida, até 5 minutos; nunca abaixo de `base`) e variação de ±10 %. `aleatorio` é um
 * número em [0, 1), como `Math.random()`.
 */
export function proximaEspera({
  base,
  falhasSeguidas,
  aleatorio,
}: {
  base: number;
  falhasSeguidas: number;
  aleatorio: number;
}): number {
  const comRecuo =
    falhasSeguidas > 0
      ? Math.min(base * 2 ** falhasSeguidas, Math.max(base, ESPERA_MAXIMA_RECUO_MS))
      : base;
  return comRecuo * (1 - VARIACAO + 2 * VARIACAO * aleatorio);
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
