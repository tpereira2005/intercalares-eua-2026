/**
 * Estados prioritários sem dados do voto antecipado, e porquê (campo `estados_sem_dados`
 * do resumo nacional VotoAntecipadoNacional, ficheiro `nacional.json` da mesma Release).
 *
 * Serve para o site dizer "fonte bloqueada" em vez de "ainda sem dados" quando a fonte
 * oficial recusa pedidos automáticos (não contornamos esses bloqueios).
 */

import { existsSync, readFileSync } from "node:fs";
import path from "node:path";
import type { EstadoSemDados, VotoAntecipadoNacional } from "@intercalares/contratos";
import { DadosInvalidos, obterValidador } from "../validacao.ts";
import { PASTA_POR_OMISSAO, VARIAVEL_PASTA } from "./carregar.ts";

export function lerNacional(caminho: string): VotoAntecipadoNacional | null {
  const absoluto = path.resolve(process.cwd(), caminho);
  if (!existsSync(absoluto)) return null;
  const dados: unknown = JSON.parse(readFileSync(absoluto, "utf-8"));
  const valido = obterValidador("VotoAntecipadoNacional");
  if (!valido(dados)) {
    throw new DadosInvalidos(caminho, "VotoAntecipadoNacional", valido.errors?.slice(0, 5));
  }
  return dados as VotoAntecipadoNacional;
}

/** Estados sem dados, pela ordem do ficheiro; lista vazia sem resumo nacional ou sem o campo. */
export function carregarSemDados(
  pasta: string = process.env[VARIAVEL_PASTA] ?? PASTA_POR_OMISSAO,
): EstadoSemDados[] {
  return [...(lerNacional(path.join(pasta, "nacional.json"))?.estados_sem_dados ?? [])];
}
