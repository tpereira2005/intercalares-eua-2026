/**
 * Regista ou retira uma chamada de uma redação no ficheiro ChamadasRedacoes. Usado pelo
 * workflow `chamadas.yml` (scripts/registar-chamada.ts), que publica o resultado na
 * Release `resultados-2026`.
 */

import type { ChamadasRedacoes } from "@intercalares/contratos";
import { obterValidador } from "../validacao.ts";

export interface PedidoChamada {
  corrida: string;
  vencedor: string;
  redacao: string;
  url: string;
  /** Hora da chamada (ISO com fuso); vazia usa a hora do registo. */
  hora: string;
  candidato: string;
  retirar: boolean;
}

export class ChamadaInvalida extends Error {}

export function registarChamada(
  atual: ChamadasRedacoes | null,
  pedido: PedidoChamada,
  corridas: ReadonlySet<string>,
  ano: number,
  agora: Date,
): ChamadasRedacoes {
  const corrida = pedido.corrida.trim().toUpperCase();
  if (!corridas.has(corrida)) {
    throw new ChamadaInvalida(`A corrida ${corrida} não existe na previsão de ${String(ano)}.`);
  }
  const outras = (atual?.ano === ano ? atual.chamadas : []).filter((c) => c.corrida !== corrida);
  const registo = agora.toISOString();
  let chamadas = outras;
  if (!pedido.retirar) {
    if (!["D", "R", "outro"].includes(pedido.vencedor)) {
      throw new ChamadaInvalida(`Vencedor inválido: ${pedido.vencedor}.`);
    }
    const hora = pedido.hora.trim() === "" ? registo : pedido.hora.trim();
    if (Number.isNaN(Date.parse(hora)) || !/(Z|[+-]\d{2}:\d{2})$/.test(hora)) {
      throw new ChamadaInvalida(`Hora inválida (falta o fuso?): ${hora}.`);
    }
    chamadas = [
      ...outras,
      {
        corrida,
        vencedor: pedido.vencedor as "D" | "R" | "outro",
        candidato: pedido.candidato.trim() === "" ? null : pedido.candidato.trim(),
        redacao: pedido.redacao.trim(),
        url: pedido.url.trim(),
        hora: new Date(hora).toISOString(),
        registada_em: registo,
      },
    ];
  }
  const redacoes = [...new Map(chamadas.map((c) => [c.redacao, c.url])).entries()];
  const resultado = {
    metadados: {
      versao_esquema: "0.1.0",
      gerado_em: registo,
      fontes: (redacoes.length > 0
        ? redacoes.map(([nome, url]) => ({ nome, url }))
        : [
            {
              nome: "Escrutínio: registo de chamadas",
              url: "https://github.com/tpereira2005/intercalares-eua-2026",
            },
          ]
      ).map((f) => ({ ...f, licenca: null, obtida_em: registo })),
    },
    ano,
    chamadas,
  };
  const valido = obterValidador("ChamadasRedacoes");
  if (!valido(resultado)) {
    const [erro] = valido.errors ?? [];
    throw new ChamadaInvalida(
      `O registo não cumpre o contrato: ${erro?.instancePath ?? ""} ${erro?.message ?? ""}`.trim(),
    );
  }
  return resultado as ChamadasRedacoes;
}
