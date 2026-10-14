/**
 * Espelho de emergência da noite eleitoral (plano, secção 8.4).
 *
 * Se a API do Worker deixar de responder (por exemplo, por chegar ao limite diário do
 * plano gratuito), o browser lê uma cópia publicada no GitHub Pages a cada 10 minutos
 * pelo workflow `espelho-noite.yml`. A cópia tem a mesma forma das respostas da API,
 * com `origem: "espelho"`, para o browser a tratar com o mesmo código. Só entram
 * ficheiros que cumprem o contrato.
 */

import type {
  ChamadasRedacoes,
  HistoricoNoite,
  ProjecaoNoite,
  ResultadosParciais,
} from "@intercalares/contratos";
import { obterValidador } from "../validacao.ts";
import type { RespostaNoite, RespostaResultados } from "./estado.ts";

export const FICHEIRO_RESULTADOS = "resultados.json";
export const FICHEIRO_NOITE = "noite.json";

export interface EntradaEspelho {
  parciais: unknown;
  projecao: unknown;
  historico: unknown;
  chamadas: unknown;
}

export interface Espelho {
  resultados: RespostaResultados | null;
  noite: RespostaNoite | null;
  /** Ficheiros que existiam mas não cumpriam o contrato e ficaram de fora. */
  rejeitados: string[];
}

export function montarEspelho(entrada: EntradaEspelho, agora: Date): Espelho {
  const confirmadoEm = agora.toISOString();
  const rejeitados: string[] = [];
  const valido = (valor: unknown, contrato: Parameters<typeof obterValidador>[0]): unknown => {
    if (valor === null || valor === undefined) return null;
    if (obterValidador(contrato)(valor)) return valor;
    rejeitados.push(contrato);
    return null;
  };
  const parciais = valido(entrada.parciais, "ResultadosParciais") as ResultadosParciais | null;
  const projecao = valido(entrada.projecao, "ProjecaoNoite") as ProjecaoNoite | null;
  const historico = valido(entrada.historico, "HistoricoNoite") as HistoricoNoite | null;
  const chamadas = valido(entrada.chamadas, "ChamadasRedacoes") as ChamadasRedacoes | null;
  return {
    resultados: parciais ? { origem: "espelho", confirmadoEm, parciais, chamadas } : null,
    noite: projecao ? { origem: "espelho", confirmadoEm, projecao, historico } : null,
    rejeitados,
  };
}
