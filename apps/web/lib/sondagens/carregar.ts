/**
 * Lê e valida, no build, o ficheiro das sondagens (Release `dados-previsao`, asset
 * `sondagens-2026.json`, contrato SondagensCongresso).
 *
 * `pnpm --filter @intercalares/web dados:obter` descarrega-o para dados/sondagens/2026.json.
 * Sem ficheiro, as páginas mostram "em preparação"; um ficheiro inválido faz falhar o build.
 */

import { existsSync, readFileSync } from "node:fs";
import path from "node:path";
import type { SondagensCongresso } from "@intercalares/contratos";
import { DadosInvalidos, obterValidador } from "../validacao.ts";
import { construirVistaSondagens, type VistaSondagens } from "./vista.ts";

export const CAMINHO_POR_OMISSAO = "dados/sondagens/2026.json";
export const VARIAVEL_CAMINHO = "DADOS_SONDAGENS";

export function lerSondagens(caminho: string): SondagensCongresso | null {
  const absoluto = path.resolve(process.cwd(), caminho);
  if (!existsSync(absoluto)) return null;
  const dados: unknown = JSON.parse(readFileSync(absoluto, "utf-8"));
  const valido = obterValidador("SondagensCongresso");
  if (!valido(dados)) {
    throw new DadosInvalidos(caminho, "SondagensCongresso", valido.errors?.slice(0, 5));
  }
  return dados as SondagensCongresso;
}

const cache = new Map<string, VistaSondagens | null>();

/** Vista das sondagens, guardada em memória durante o build; `null` sem ficheiro. */
export function carregarSondagens(caminho?: string): VistaSondagens | null {
  const chave = caminho ?? process.env[VARIAVEL_CAMINHO] ?? CAMINHO_POR_OMISSAO;
  if (!cache.has(chave)) {
    const dados = lerSondagens(chave);
    cache.set(chave, dados ? construirVistaSondagens(dados) : null);
  }
  return cache.get(chave) ?? null;
}
