/**
 * Caminho de cada partido para a maioria numa câmara, lido da previsão publicada.
 *
 * Não há aqui simulação nova: as corridas ordenam-se pela probabilidade de vitória de
 * cada lado e conta-se quantas o partido precisa de ganhar, além dos lugares que não
 * vão a votos. A corrida nessa posição é a decisiva (o "ponto de viragem"). Os dois
 * lados leem-se com a mesma regra, para terem o mesmo destaque na página.
 */

import type { Camara, CorridaVista, Lado, VistaPrevisao } from "./vista.ts";

export interface CorridaCaminho {
  corrida: CorridaVista;
  /** Posição na ordem do partido (1 = a corrida que ele tem mais probabilidade de ganhar). */
  posicao: number;
  /** Probabilidade de vitória do partido nesta corrida. */
  prob: number;
  decisiva: boolean;
}

export interface CaminhoMaioria {
  lado: Lado;
  /** Lugares de que o partido precisa para controlar a câmara. */
  precisa: number;
  /** Lugares que já tem sem ir a votos. */
  foraDeJogo: number;
  /** Corridas que tem de ganhar entre as que vão a votos. */
  vitoriasNecessarias: number;
  /** Probabilidade de controlo, tal como o modelo a publica. */
  probControlo: number;
  /** Corridas à volta da decisiva, pela ordem do partido. */
  corridas: CorridaCaminho[];
  /**
   * Distância, em pontos, do ambiente nacional previsto ao limiar: positiva quando o
   * partido já é favorito, negativa quando precisa que o ambiente se desloque a seu favor.
   */
  folga: number | null;
}

/** Corridas mostradas de cada lado da decisiva. */
export const VIZINHAS = 2;

/** Probabilidade de o lado ganhar a corrida. */
export function probLado(c: CorridaVista, lado: Lado): number {
  return lado === "D" ? c.probD : 1 - c.probD;
}

/** Margem a favor do lado, em pontos. */
function margemLado(c: CorridaVista, lado: Lado): number {
  return lado === "D" ? c.margem : -c.margem;
}

/** Corridas pela ordem do lado: da mais provável para a menos provável. */
export function ordemDoLado(corridas: readonly CorridaVista[], lado: Lado): CorridaVista[] {
  return [...corridas].sort(
    (a, b) =>
      probLado(b, lado) - probLado(a, lado) ||
      margemLado(b, lado) - margemLado(a, lado) ||
      a.id.localeCompare(b.id),
  );
}

/**
 * Lugares de que cada lado precisa. Os democratas precisam da maioria; os republicanos
 * do resto mais um, o que no Senado (100 lugares, maioria 51) dá 50: o desempate fica
 * com o vice-presidente, que é republicano até 2029.
 */
export function lugaresNecessarios(total: number, maioria: number, lado: Lado): number {
  return lado === "D" ? maioria : total - maioria + 1;
}

export function caminhoMaioria(
  vista: VistaPrevisao,
  camara: Camara,
  lado: Lado,
  vizinhas: number = VIZINHAS,
): CaminhoMaioria | null {
  const resumo = vista[camara];
  const corridas = camara === "senado" ? vista.corridasSenado : vista.corridasCamara;
  const precisa = lugaresNecessarios(resumo.total, resumo.maioria, lado);
  const foraDeJogo = resumo.foraDeJogo[lado];
  const vitoriasNecessarias = precisa - foraDeJogo;
  if (vitoriasNecessarias < 1 || vitoriasNecessarias > corridas.length) return null;
  const ordem = ordemDoLado(corridas, lado);
  const inicio = Math.max(0, vitoriasNecessarias - 1 - vizinhas);
  const fim = Math.min(ordem.length, vitoriasNecessarias + vizinhas);
  const limiar = resumo.limiar;
  const distancia = limiar === null ? null : vista.ambiente.margem - limiar;
  return {
    lado,
    precisa,
    foraDeJogo,
    vitoriasNecessarias,
    probControlo: lado === "D" ? resumo.probD : resumo.probR,
    corridas: ordem.slice(inicio, fim).map((corrida, i) => ({
      corrida,
      posicao: inicio + i + 1,
      prob: probLado(corrida, lado),
      decisiva: inicio + i + 1 === vitoriasNecessarias,
    })),
    folga: distancia === null ? null : lado === "D" ? distancia : -distancia,
  };
}
