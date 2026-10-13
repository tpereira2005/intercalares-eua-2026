/**
 * Fases do painel principal (plano, secção 9.4): antes da eleição, noite
 * eleitoral e contagem depois da noite.
 */

export type Fase = "antes" | "noite" | "depois";

/** Primeiras urnas fecham às 18h00 de Indiana e Kentucky (23h00 UTC). */
export const INICIO_NOITE = new Date("2026-11-03T23:00:00Z");
/** A noite termina às 7h00 de Washington do dia seguinte. */
export const FIM_NOITE = new Date("2026-11-04T12:00:00Z");

export function faseEm(agora: Date): Fase {
  if (agora < INICIO_NOITE) return "antes";
  if (agora < FIM_NOITE) return "noite";
  return "depois";
}
