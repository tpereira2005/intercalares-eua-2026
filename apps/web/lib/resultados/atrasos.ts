/**
 * Fontes atrasadas na noite eleitoral, a partir da saúde da recolha (contrato
 * SaudeRecolha, publicado pela recolha de Dados em `resultados-2026/saude.json`).
 *
 * O site não mostra a mensagem técnica do erro (`ultimo_erro`, que também entra no texto
 * do `alerta`): diz só que a fonte não responde ou que não traz dados novos, e desde que
 * hora. Um estado com uma entrada manual em dia (`TX-manual` sem alerta) não está
 * atrasado: os totais copiados à mão sobrepõem-se à fonte automática.
 */

import type { SaudeEstado, SaudeRecolha } from "@intercalares/contratos";

export interface Atraso {
  /** `semResposta`: a fonte falha seguidamente; `parada`: responde, mas sem dados novos. */
  motivo: "semResposta" | "parada";
  /** Última vez que a fonte trouxe dados novos; `null` se nunca trouxe. */
  desde: string | null;
}

function maisRecente(horas: readonly (string | null)[]): string | null {
  return horas.reduce<string | null>(
    (max, h) => (h !== null && (max === null || Date.parse(h) > Date.parse(max)) ? h : max),
    null,
  );
}

/** Atraso por estado (`TX`); só entram os estados com todas as entradas em alerta. */
export function atrasosDosEstados(saude: SaudeRecolha | null, ano: number): Map<string, Atraso> {
  const atrasos = new Map<string, Atraso>();
  // Uma saúde de outra eleição (um ensaio de 2024 ao lado de 2026, por exemplo) não conta.
  if (!saude || Number(saude.data_eleicao.slice(0, 4)) !== ano) return atrasos;
  const porEstado = new Map<string, SaudeEstado[]>();
  for (const [chave, e] of Object.entries(saude.estados)) {
    if (!e) continue;
    const estado = chave.slice(0, 2);
    porEstado.set(estado, [...(porEstado.get(estado) ?? []), e]);
  }
  for (const [estado, entradas] of porEstado) {
    if (entradas.some((e) => e.alerta === null)) continue;
    atrasos.set(estado, {
      motivo: entradas.some((e) => e.falhas_seguidas > 0) ? "semResposta" : "parada",
      desde: maisRecente(entradas.map((e) => e.ultima_alteracao)),
    });
  }
  return atrasos;
}
