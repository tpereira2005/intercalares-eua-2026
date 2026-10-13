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
import type { ResultadosParciais } from "@intercalares/contratos";
import { carregarPrevisao } from "../previsao/carregar.ts";
import { DadosInvalidos, obterValidador } from "../validacao.ts";
import { construirVistaResultados, type VistaResultados } from "./vista.ts";

export const CAMINHO_POR_OMISSAO = "dados/resultados/parciais.json";
export const VARIAVEL_CAMINHO = "DADOS_RESULTADOS";

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

/** Vista da noite eleitoral; `null` sem contagem publicada. */
export function carregarResultados(caminho?: string): VistaResultados | null {
  const parciais = lerParciais(caminho ?? process.env[VARIAVEL_CAMINHO] ?? CAMINHO_POR_OMISSAO);
  if (!parciais) return null;
  return construirVistaResultados(parciais, carregarPrevisao()?.previsao ?? null);
}
