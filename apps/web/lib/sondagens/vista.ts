/**
 * Vista das sondagens (contrato SondagensCongresso): as sondagens que o modelo usa e
 * as médias calculadas pelo mesmo método da previsão (docs/metodologia/previsao.md,
 * secção 4). Não há aqui metodologia nova: só se seleciona e ordena.
 */

import type { SondagensCongresso, SondagensCorrida } from "@intercalares/contratos";
import { nomeEstado } from "../estados.ts";

export interface VistaSondagens {
  ano: number;
  corte: string;
  geradoEm: string;
  fontes: { nome: string; url: string }[];
  metodo: SondagensCongresso["metodo"];
  votoGenerico: SondagensCongresso["voto_generico"];
  /** Corridas por ordem de estado (com a eleição especial a seguir à regular). */
  corridas: SondagensCorrida[];
}

/** Endereço da página de sondagens de uma corrida (ex.: /sondagens/nc-s/). */
export function caminhoCorrida(id: string): string {
  return `/sondagens/${id.toLowerCase()}/`;
}

/** Nome legível da corrida: o estado, e "eleição especial" quando é o caso. */
export function nomeCorrida(c: Pick<SondagensCorrida, "id" | "estado">): string {
  const estado = nomeEstado(c.estado);
  return c.id.endsWith("-especial") ? `${estado} (especial)` : estado;
}

export function construirVistaSondagens(dados: SondagensCongresso): VistaSondagens {
  return {
    ano: dados.ano,
    corte: dados.corte,
    geradoEm: dados.metadados.gerado_em,
    fontes: dados.metadados.fontes
      .filter((f, i, todas) => todas.findIndex((g) => g.nome === f.nome) === i)
      .map((f) => ({ nome: f.nome, url: f.url })),
    metodo: dados.metodo,
    votoGenerico: [...dados.voto_generico].sort((a, b) => a.data.localeCompare(b.data)),
    corridas: [...dados.corridas]
      .filter((c) => c.camara === "senado")
      .sort(
        (a, b) =>
          nomeEstado(a.estado).localeCompare(nomeEstado(b.estado), "pt-PT") ||
          a.id.localeCompare(b.id),
      ),
  };
}
