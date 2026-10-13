/**
 * Lê e valida, no build, os ficheiros do voto antecipado publicados pelo
 * pipeline, um por estado (`nc.json`, `ga.json`...).
 *
 * Os ficheiros não estão no repositório: `pnpm --filter @intercalares/web dados:obter`
 * descarrega-os da Release pública antes do build. Sem ficheiros, as páginas mostram
 * "em preparação"; com um ficheiro que não cumpre o contrato, o build falha,
 * porque dados que falham a validação nunca são publicados.
 */

import { existsSync, readFileSync, readdirSync } from "node:fs";
import path from "node:path";
import type { VotoAntecipadoAgregado, VotoAntecipadoEstado } from "@intercalares/contratos";
import { DadosInvalidos, obterValidador, type NomeContrato } from "../validacao.ts";
import { construirVistaAgregada, type VistaAgregada } from "./agregado.ts";
import { construirVista, type VistaVotoAntecipado } from "./vista.ts";

export { DadosInvalidos } from "../validacao.ts";

/** Pasta dos ficheiros, relativa a apps/web; a variável de ambiente substitui-a. */
export const PASTA_POR_OMISSAO = "dados/voto-antecipado";
export const VARIAVEL_PASTA = "DADOS_VOTO_ANTECIPADO";

/** Resumo nacional publicado ao lado dos estados; o site calcula o seu a partir dos estados. */
const IGNORADOS = new Set(["nacional.json"]);

type Contrato = Extract<NomeContrato, "VotoAntecipadoEstado" | "VotoAntecipadoAgregado">;

export type FicheiroEstado =
  | { contrato: "VotoAntecipadoEstado"; dados: VotoAntecipadoEstado }
  | { contrato: "VotoAntecipadoAgregado"; dados: VotoAntecipadoAgregado };

/**
 * Lê e valida um ficheiro; `null` quando não existe. O contrato decide-se pela
 * forma: só os estados agregados têm `granularidade`. Depois valida-se contra
 * esse contrato, que rejeita campos a mais ou a menos.
 */
export function lerEstado(caminho: string): FicheiroEstado | null {
  const absoluto = path.resolve(process.cwd(), caminho);
  if (!existsSync(absoluto)) return null;
  const dados: unknown = JSON.parse(readFileSync(absoluto, "utf-8"));
  const contrato: Contrato =
    typeof dados === "object" && dados !== null && "granularidade" in dados
      ? "VotoAntecipadoAgregado"
      : "VotoAntecipadoEstado";
  const valido = obterValidador(contrato);
  if (!valido(dados)) {
    throw new DadosInvalidos(caminho, contrato, valido.errors?.slice(0, 5));
  }
  return contrato === "VotoAntecipadoAgregado"
    ? { contrato, dados: dados as VotoAntecipadoAgregado }
    : { contrato, dados: dados as VotoAntecipadoEstado };
}

/** Lê e valida todos os ficheiros `.json` de uma pasta; lista vazia sem pasta. */
export function lerEstados(
  pasta: string = process.env[VARIAVEL_PASTA] ?? PASTA_POR_OMISSAO,
): FicheiroEstado[] {
  const absoluta = path.resolve(process.cwd(), pasta);
  if (!existsSync(absoluta)) return [];
  const estados = readdirSync(absoluta)
    .filter((nome) => nome.endsWith(".json") && !IGNORADOS.has(nome))
    .sort()
    .flatMap((nome) => {
      const estado = lerEstado(path.join(pasta, nome));
      return estado ? [estado] : [];
    });
  const codigos = estados.map((e) => e.dados.estado);
  const repetido = codigos.find((c, i) => codigos.indexOf(c) !== i);
  if (repetido) throw new Error(`Há mais de um ficheiro para o estado ${repetido} em ${pasta}`);
  return estados;
}

export interface VistasEstados {
  /** Estados com ficheiro de eleitores (taxas de participação por grupo). */
  individuais: VistaVotoAntecipado[];
  /** Estados só com boletins ou totais por condado (votos face a votos). */
  agregados: VistaAgregada[];
}

const cache = new Map<string, VistasEstados>();

function porVotos<V extends { votos: number; estado: string }>(a: V, b: V): number {
  return b.votos - a.votos || a.estado.localeCompare(b.estado);
}

/**
 * Vistas de todos os estados com dados, do que tem mais votos para o que tem
 * menos. Guardadas em memória: várias páginas leem-nas no mesmo build.
 */
export function carregarTodas(pasta?: string): VistasEstados {
  const chave = pasta ?? process.env[VARIAVEL_PASTA] ?? PASTA_POR_OMISSAO;
  let vistas = cache.get(chave);
  if (!vistas) {
    const ficheiros = lerEstados(chave);
    vistas = {
      individuais: ficheiros
        .flatMap((f) => (f.contrato === "VotoAntecipadoEstado" ? [construirVista(f.dados)] : []))
        .sort(porVotos),
      agregados: ficheiros
        .flatMap((f) =>
          f.contrato === "VotoAntecipadoAgregado" ? [construirVistaAgregada(f.dados)] : [],
        )
        .sort(porVotos),
    };
    cache.set(chave, vistas);
  }
  return vistas;
}

/** Só os estados com ficheiro de eleitores. */
export function carregarVistas(pasta?: string): VistaVotoAntecipado[] {
  return carregarTodas(pasta).individuais;
}
