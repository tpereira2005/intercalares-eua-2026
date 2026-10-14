/**
 * Chamadas de vencedor feitas pelas redações (contrato ChamadasRedacoes), registadas à
 * mão na noite eleitoral pelo workflow `chamadas.yml`. O Escrutínio não chama corridas:
 * mostra quem chamou, quando e onde.
 */

import type { ChamadasRedacoes } from "@intercalares/contratos";

export interface ChamadaVista {
  corrida: string;
  vencedor: "D" | "R" | "outro";
  candidato: string | null;
  redacao: string;
  url: string;
  hora: string;
}

/** Chamadas do ano pedido, da mais recente para a mais antiga. */
export function construirChamadas(dados: ChamadasRedacoes | null, ano: number): ChamadaVista[] {
  if (dados?.ano !== ano) return [];
  return dados.chamadas
    .map((c) => ({
      corrida: c.corrida,
      vencedor: c.vencedor,
      candidato: c.candidato ?? null,
      redacao: c.redacao,
      url: c.url,
      hora: c.hora,
    }))
    .sort((a, b) => Date.parse(b.hora) - Date.parse(a.hora) || a.corrida.localeCompare(b.corrida));
}
