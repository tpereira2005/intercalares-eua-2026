/**
 * Lê e valida, no build, a projeção da noite eleitoral e a sua evolução (Release
 * `dados-noite`, assets `projecao-noite-2026.json` e `historico-noite-2026.json`).
 *
 * `pnpm --filter @intercalares/web dados:obter` descarrega-os para dados/noite/.
 * Sem projeção, a página da noite mostra só a contagem e a previsão; sem histórico,
 * só a evolução fica de fora. Um ficheiro inválido faz falhar o build.
 */

import { existsSync, readFileSync } from "node:fs";
import path from "node:path";
import type { HistoricoNoite, ProjecaoNoite } from "@intercalares/contratos";
import { DadosInvalidos, obterValidador } from "../validacao.ts";
import { construirVistaNoite, type VistaNoite } from "./vista.ts";

export const PASTA_POR_OMISSAO = "dados/noite";
export const VARIAVEL_PASTA = "DADOS_NOITE";
export const FICHEIRO_PROJECAO = "projecao.json";
export const FICHEIRO_HISTORICO = "historico.json";

function ler(caminho: string, contrato: "ProjecaoNoite" | "HistoricoNoite"): unknown {
  const absoluto = path.resolve(process.cwd(), caminho);
  if (!existsSync(absoluto)) return null;
  const dados: unknown = JSON.parse(readFileSync(absoluto, "utf-8"));
  const valido = obterValidador(contrato);
  if (!valido(dados)) throw new DadosInvalidos(caminho, contrato, valido.errors?.slice(0, 5));
  return dados;
}

export function lerProjecao(caminho: string): ProjecaoNoite | null {
  return ler(caminho, "ProjecaoNoite") as ProjecaoNoite | null;
}

export function lerHistoricoNoite(caminho: string): HistoricoNoite | null {
  return ler(caminho, "HistoricoNoite") as HistoricoNoite | null;
}

const cache = new Map<string, VistaNoite | null>();

/** Vista da projeção, guardada em memória durante o build; `null` sem projeção. */
export function carregarNoite(pasta?: string): VistaNoite | null {
  const chave = pasta ?? process.env[VARIAVEL_PASTA] ?? PASTA_POR_OMISSAO;
  if (!cache.has(chave)) {
    const projecao = lerProjecao(path.join(chave, FICHEIRO_PROJECAO));
    cache.set(
      chave,
      projecao
        ? construirVistaNoite(projecao, lerHistoricoNoite(path.join(chave, FICHEIRO_HISTORICO)))
        : null,
    );
  }
  return cache.get(chave) ?? null;
}
