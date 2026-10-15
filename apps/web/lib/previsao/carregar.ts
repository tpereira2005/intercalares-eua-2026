/**
 * Lê e valida, no build, o ficheiro da previsão publicado pelo pipeline
 * e do seu histórico diário (Release `dados-previsao`, assets `previsao-2026.json`
 * e `historico-previsao-2026.json`).
 *
 * `pnpm --filter @intercalares/web dados:obter` descarrega-os para dados/previsao/.
 * Sem previsão, a página mostra "em preparação"; sem histórico, só a evolução
 * fica em preparação. Um ficheiro que não cumpre o contrato faz falhar o build.
 */

import { existsSync, readFileSync } from "node:fs";
import path from "node:path";
import type {
  AlteracoesPrevisao,
  CenariosPrevisao,
  HistoricoPrevisao,
  PrevisaoCongresso,
} from "@intercalares/contratos";
import { DadosInvalidos, obterValidador, type NomeContrato } from "../validacao.ts";
import {
  construirAlteracoes,
  cenariosBatemCerto,
  construirVistaCenarios,
  type VistaAlteracoes,
  type VistaCenarios,
} from "./explorador.ts";
import {
  construirEvolucao,
  construirVistaPrevisao,
  type VistaEvolucao,
  type VistaPrevisao,
} from "./vista.ts";

/** Pasta dos ficheiros, relativa a apps/web; a variável de ambiente substitui-a. */
export const PASTA_POR_OMISSAO = "dados/previsao";
export const VARIAVEL_PASTA = "DADOS_PREVISAO";
export const FICHEIRO_PREVISAO = "2026.json";
export const FICHEIRO_HISTORICO = "historico-2026.json";
export const FICHEIRO_CENARIOS = "cenarios-2026.json";
export const FICHEIRO_ALTERACOES = "alteracoes-2026.json";

function ler(caminho: string, contrato: NomeContrato): unknown {
  const absoluto = path.resolve(process.cwd(), caminho);
  if (!existsSync(absoluto)) return null;
  const dados: unknown = JSON.parse(readFileSync(absoluto, "utf-8"));
  const valido = obterValidador(contrato);
  if (!valido(dados)) throw new DadosInvalidos(caminho, contrato, valido.errors?.slice(0, 5));
  return dados;
}

/** Lê e valida a previsão; `null` quando não existe. */
export function lerPrevisao(caminho: string): PrevisaoCongresso | null {
  return ler(caminho, "PrevisaoCongresso") as PrevisaoCongresso | null;
}

/** Lê e valida o histórico diário; `null` quando não existe. */
export function lerHistorico(caminho: string): HistoricoPrevisao | null {
  return ler(caminho, "HistoricoPrevisao") as HistoricoPrevisao | null;
}

/** Lê e valida a grelha de cenários; `null` quando não existe. */
export function lerCenarios(caminho: string): CenariosPrevisao | null {
  return ler(caminho, "CenariosPrevisao") as CenariosPrevisao | null;
}

/** Lê e valida o registo de alterações do método; `null` quando não existe. */
export function lerAlteracoes(caminho: string): AlteracoesPrevisao | null {
  return ler(caminho, "AlteracoesPrevisao") as AlteracoesPrevisao | null;
}

export interface DadosPrevisao {
  previsao: VistaPrevisao;
  evolucao: VistaEvolucao | null;
  /** Cenários do mesmo ano e do mesmo corte da previsão; `null` sem eles. */
  cenarios: VistaCenarios | null;
  /** Registo de alterações do método; `null` sem ele. */
  alteracoes: VistaAlteracoes | null;
}

const cache = new Map<string, DadosPrevisao | null>();

/** Previsão e evolução, guardadas em memória durante o build; `null` sem previsão. */
export function carregarPrevisao(pasta?: string): DadosPrevisao | null {
  const chave = pasta ?? process.env[VARIAVEL_PASTA] ?? PASTA_POR_OMISSAO;
  if (!cache.has(chave)) {
    const dados = lerPrevisao(path.join(chave, FICHEIRO_PREVISAO));
    const historico = dados ? lerHistorico(path.join(chave, FICHEIRO_HISTORICO)) : null;
    if (historico && dados && historico.ano !== dados.ano) {
      throw new Error(`Histórico de ${String(historico.ano)} com previsão de ${String(dados.ano)}`);
    }
    // Cenários de outro corte ou de outra corrida do modelo dariam números diferentes dos
    // publicados: ficam de fora.
    const cenarios = dados ? lerCenarios(path.join(chave, FICHEIRO_CENARIOS)) : null;
    const alteracoes = dados ? lerAlteracoes(path.join(chave, FICHEIRO_ALTERACOES)) : null;
    cache.set(
      chave,
      dados
        ? {
            previsao: construirVistaPrevisao(dados),
            evolucao: historico ? construirEvolucao(historico, dados.corte) : null,
            cenarios:
              cenarios && cenariosBatemCerto(cenarios, dados)
                ? construirVistaCenarios(cenarios)
                : null,
            alteracoes: alteracoes?.ano === dados.ano ? construirAlteracoes(alteracoes) : null,
          }
        : null,
    );
  }
  return cache.get(chave) ?? null;
}
