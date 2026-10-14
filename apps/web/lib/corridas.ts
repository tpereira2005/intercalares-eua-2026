/**
 * Página de cada corrida (/corridas/<id>/): a previsão, de onde vem e como evoluiu,
 * com ligações para as sondagens, o voto antecipado do estado e a noite eleitoral.
 */

import { nomeEstado } from "./estados.ts";
import { FECHOS, type FechoEstado } from "./fecho.ts";
import { t } from "./mensagens.ts";
import type { CorridaVista, PontoCorrida, PontoEvolucao, VistaPrevisao } from "./previsao/vista.ts";

/** Endereço da página de uma corrida (ex.: /corridas/nc-s/, /corridas/oh-s-especial/). */
export function caminhoPaginaCorrida(id: string): string {
  return `/corridas/${id.toLowerCase()}/`;
}

/** "Carolina do Norte · Senado", "Ohio · Senado (eleição especial)" ou "NC-01 · Carolina do Norte". */
export function tituloCorrida(
  c: Pick<CorridaVista, "id" | "camara" | "estado" | "especial">,
): string {
  const estado = nomeEstado(c.estado);
  if (c.camara === "camara") return t("corrida.tituloCamara", { id: c.id, estado });
  return t(c.especial ? "corrida.tituloSenadoEspecial" : "corrida.tituloSenado", { estado });
}

/** Todas as corridas da previsão: o Senado primeiro, depois a Câmara. */
export function todasCorridas(previsao: VistaPrevisao): CorridaVista[] {
  return [...previsao.corridasSenado, ...previsao.corridasCamara];
}

export function encontrarCorrida(previsao: VistaPrevisao, id: string): CorridaVista | null {
  return todasCorridas(previsao).find((c) => c.id.toLowerCase() === id.toLowerCase()) ?? null;
}

/** Pontos para o gráfico de evolução (a probabilidade republicana é o complemento). */
export function evolucaoCorrida(pontos: readonly PontoCorrida[]): PontoEvolucao[] {
  return pontos.map((p) => ({
    corte: p.corte,
    probD: p.probD,
    probR: 1 - p.probD,
    mediana: 0,
    p10: 0,
    p90: 0,
  }));
}

export function fechoDoEstado(estado: CorridaVista["estado"]): FechoEstado | null {
  return FECHOS.find((f) => f.estado === estado) ?? null;
}

/**
 * Limites do eixo da margem (em pontos, múltiplos de 10) que cabem os valores dados e o
 * zero, para o empate ficar sempre à vista.
 */
export function limitesMargem(valores: readonly number[]): [number, number] {
  const finitos = valores.filter((v) => Number.isFinite(v));
  const minimo = Math.min(0, ...finitos);
  const maximo = Math.max(0, ...finitos);
  const de = Math.floor(minimo / 10) * 10;
  const ate = Math.ceil(maximo / 10) * 10;
  return [de === ate ? -10 : de, de === ate ? 10 : ate];
}
