/**
 * Horários de fecho das urnas na eleição de 3 de novembro de 2026, por estado.
 *
 * Fonte: The Green Papers, "2026 General Election Polling Hours"
 * (https://www.thegreenpapers.com/G26/PollingHours.phtml), consultada a 13 de outubro
 * de 2026; os estados que a fonte marca como "reportedly" ficam com `confirmar: true`.
 * Em estados com dois fusos, `primeiro` é o fecho da maior parte do estado e `todas`
 * o das últimas urnas. Horas em UTC (Lisboa está em UTC+0 em novembro).
 */

import type { CodigoEstado } from "@intercalares/contratos";

export const FONTE_FECHO = {
  nome: "The Green Papers: 2026 General Election Polling Hours",
  url: "https://www.thegreenpapers.com/G26/PollingHours.phtml",
};

export interface FechoEstado {
  estado: CodigoEstado;
  /** Fecho da maior parte das urnas (ISO, UTC). */
  primeiro: string;
  /** Fecho das últimas urnas, quando o estado tem dois fusos. */
  todas?: string;
  /** A fonte dá o horário como não oficial ("reportedly"). */
  confirmar?: boolean;
}

const DIA3 = "2026-11-03T";
const DIA4 = "2026-11-04T";

function h(hora: string): string {
  return hora.startsWith("23") ? `${DIA3}${hora}:00Z` : `${DIA4}${hora}:00Z`;
}

export const FECHOS: readonly FechoEstado[] = [
  { estado: "IN", primeiro: h("23:00"), todas: h("00:00") },
  { estado: "KY", primeiro: h("23:00"), todas: h("00:00") },
  { estado: "FL", primeiro: h("00:00"), todas: h("01:00") },
  { estado: "GA", primeiro: h("00:00") },
  { estado: "NH", primeiro: h("00:00"), todas: h("01:00"), confirmar: true },
  { estado: "SC", primeiro: h("00:00") },
  { estado: "VT", primeiro: h("00:00") },
  { estado: "VA", primeiro: h("00:00") },
  { estado: "NC", primeiro: h("00:30") },
  { estado: "OH", primeiro: h("00:30") },
  { estado: "WV", primeiro: h("00:30"), confirmar: true },
  { estado: "AL", primeiro: h("01:00") },
  { estado: "CT", primeiro: h("01:00") },
  { estado: "DE", primeiro: h("01:00") },
  { estado: "DC", primeiro: h("01:00") },
  { estado: "IL", primeiro: h("01:00"), confirmar: true },
  { estado: "KS", primeiro: h("01:00"), todas: h("02:00") },
  { estado: "ME", primeiro: h("01:00") },
  { estado: "MD", primeiro: h("01:00") },
  { estado: "MA", primeiro: h("01:00") },
  { estado: "MI", primeiro: h("01:00"), todas: h("02:00"), confirmar: true },
  { estado: "MS", primeiro: h("01:00") },
  { estado: "MO", primeiro: h("01:00") },
  { estado: "NJ", primeiro: h("01:00") },
  { estado: "OK", primeiro: h("01:00") },
  { estado: "PA", primeiro: h("01:00") },
  { estado: "RI", primeiro: h("01:00") },
  { estado: "SD", primeiro: h("01:00"), todas: h("02:00") },
  { estado: "TN", primeiro: h("01:00"), confirmar: true },
  { estado: "TX", primeiro: h("01:00"), todas: h("02:00"), confirmar: true },
  { estado: "AR", primeiro: h("01:30") },
  { estado: "AZ", primeiro: h("02:00"), confirmar: true },
  { estado: "CO", primeiro: h("02:00") },
  { estado: "IA", primeiro: h("02:00") },
  { estado: "LA", primeiro: h("02:00") },
  { estado: "MN", primeiro: h("02:00") },
  { estado: "NE", primeiro: h("02:00") },
  { estado: "NM", primeiro: h("02:00") },
  { estado: "NY", primeiro: h("02:00") },
  { estado: "WI", primeiro: h("02:00") },
  { estado: "WY", primeiro: h("02:00") },
  { estado: "ID", primeiro: h("03:00"), todas: h("04:00") },
  { estado: "MT", primeiro: h("03:00") },
  { estado: "NV", primeiro: h("03:00") },
  { estado: "ND", primeiro: h("03:00"), todas: h("04:00"), confirmar: true },
  { estado: "OR", primeiro: h("03:00"), todas: h("04:00") },
  { estado: "UT", primeiro: h("03:00") },
  { estado: "CA", primeiro: h("04:00"), confirmar: true },
  { estado: "WA", primeiro: h("04:00"), confirmar: true },
  { estado: "AK", primeiro: h("05:00"), todas: h("06:00"), confirmar: true },
  { estado: "HI", primeiro: h("05:00") },
];

export interface GrupoFecho {
  /** Instante do fecho (ISO, UTC). */
  instante: string;
  estados: FechoEstado[];
}

/** Estados agrupados pela hora em que fecha a maior parte das urnas, por ordem. */
export function gruposFecho(fechos: readonly FechoEstado[] = FECHOS): GrupoFecho[] {
  const grupos = new Map<string, FechoEstado[]>();
  for (const f of fechos) {
    const lista = grupos.get(f.primeiro);
    if (lista) lista.push(f);
    else grupos.set(f.primeiro, [f]);
  }
  return [...grupos]
    .sort(([a], [b]) => Date.parse(a) - Date.parse(b))
    .map(([instante, estados]) => ({ instante, estados }));
}

/** Próximo fecho depois de `agora`, ou `null` quando todas as urnas já fecharam. */
export function proximoFecho(agora: Date, grupos: readonly GrupoFecho[]): GrupoFecho | null {
  return grupos.find((g) => Date.parse(g.instante) > agora.getTime()) ?? null;
}
