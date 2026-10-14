/**
 * Lê e valida, no build, o retrato da contagem publicado pela recolha da noite
 * eleitoral (Release `resultados-2026`, asset `parciais.json`, contrato
 * ResultadosParciais).
 *
 * `pnpm --filter @intercalares/web dados:obter` descarrega-o para
 * dados/resultados/parciais.json. Sem ficheiro, a página mostra "em preparação";
 * um ficheiro que não cumpre o contrato faz falhar o build.
 */

import { existsSync, readFileSync } from "node:fs";
import path from "node:path";
import type { ChamadasRedacoes, ResultadosParciais } from "@intercalares/contratos";
import { carregarNoite } from "../noite/carregar.ts";
import type { VistaNoite } from "../noite/vista.ts";
import { carregarPrevisao } from "../previsao/carregar.ts";
import { DadosInvalidos, obterValidador } from "../validacao.ts";
import { construirVistaResultados, type VistaResultados } from "./vista.ts";

export const CAMINHO_POR_OMISSAO = "dados/resultados/parciais.json";
export const VARIAVEL_CAMINHO = "DADOS_RESULTADOS";
/** Chamadas das redações, na mesma pasta do retrato. */
export const FICHEIRO_CHAMADAS = "chamadas.json";

/** Lê e valida o retrato; `null` quando não existe. */
export function lerParciais(caminho: string): ResultadosParciais | null {
  const absoluto = path.resolve(process.cwd(), caminho);
  if (!existsSync(absoluto)) return null;
  const dados: unknown = JSON.parse(readFileSync(absoluto, "utf-8"));
  const valido = obterValidador("ResultadosParciais");
  if (!valido(dados)) {
    throw new DadosInvalidos(caminho, "ResultadosParciais", valido.errors?.slice(0, 5));
  }
  return dados as ResultadosParciais;
}

/** Lê e valida as chamadas das redações; `null` quando não existem. */
export function lerChamadas(caminho: string): ChamadasRedacoes | null {
  const absoluto = path.resolve(process.cwd(), caminho);
  if (!existsSync(absoluto)) return null;
  const dados: unknown = JSON.parse(readFileSync(absoluto, "utf-8"));
  const valido = obterValidador("ChamadasRedacoes");
  if (!valido(dados)) {
    throw new DadosInvalidos(caminho, "ChamadasRedacoes", valido.errors?.slice(0, 5));
  }
  return dados as ChamadasRedacoes;
}

export interface DadosNoiteEleitoral {
  /** Contagem por corrida; `null` sem parciais.json. */
  resultados: VistaResultados | null;
  /** Projeção do modelo; `null` sem projeção publicada. */
  noite: VistaNoite | null;
}

/** Contagem e projeção da noite eleitoral; `null` quando não há nenhuma das duas. */
export function carregarResultados(caminho?: string): DadosNoiteEleitoral | null {
  const ficheiro = caminho ?? process.env[VARIAVEL_CAMINHO] ?? CAMINHO_POR_OMISSAO;
  const parciais = lerParciais(ficheiro);
  const chamadas = parciais
    ? lerChamadas(path.join(path.dirname(ficheiro), FICHEIRO_CHAMADAS))
    : null;
  const noite = carregarNoite();
  if (!parciais && !noite) return null;
  return {
    resultados: parciais
      ? construirVistaResultados(parciais, carregarPrevisao()?.previsao ?? null, noite, chamadas)
      : null,
    noite,
  };
}
