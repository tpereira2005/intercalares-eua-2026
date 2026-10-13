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
import type { VotoAntecipadoEstado } from "@intercalares/contratos";
import Ajv2020, { type ValidateFunction } from "ajv/dist/2020.js";
import adicionarFormatos from "ajv-formats";
import { construirVista, type VistaVotoAntecipado } from "./vista.ts";

/** Pasta dos ficheiros, relativa a apps/web; a variável de ambiente substitui-a. */
export const PASTA_POR_OMISSAO = "dados/voto-antecipado";
export const VARIAVEL_PASTA = "DADOS_VOTO_ANTECIPADO";

const ESQUEMA = "../../schemas/json/contratos.schema.json";

let validador: ValidateFunction<VotoAntecipadoEstado> | undefined;

function obterValidador(): ValidateFunction<VotoAntecipadoEstado> {
  if (!validador) {
    const esquema = JSON.parse(readFileSync(path.resolve(process.cwd(), ESQUEMA), "utf-8")) as {
      $id: string;
    };
    const ajv = new Ajv2020({ allErrors: true, strict: false });
    adicionarFormatos(ajv);
    ajv.addSchema(esquema);
    const id = esquema.$id;
    validador = ajv.compile<VotoAntecipadoEstado>({ $ref: `${id}#/$defs/VotoAntecipadoEstado` });
  }
  return validador;
}

export class DadosInvalidos extends Error {
  constructor(caminho: string, detalhe: unknown) {
    super(
      `O ficheiro ${caminho} não cumpre o contrato VotoAntecipadoEstado: ${JSON.stringify(detalhe)}`,
    );
    this.name = "DadosInvalidos";
  }
}

/** Lê e valida um ficheiro; `null` quando não existe. */
export function lerEstado(caminho: string): VotoAntecipadoEstado | null {
  const absoluto = path.resolve(process.cwd(), caminho);
  if (!existsSync(absoluto)) return null;
  const dados: unknown = JSON.parse(readFileSync(absoluto, "utf-8"));
  const valido = obterValidador();
  if (!valido(dados)) {
    throw new DadosInvalidos(caminho, valido.errors?.slice(0, 5));
  }
  return dados;
}

/** Lê e valida todos os ficheiros `.json` de uma pasta; lista vazia sem pasta. */
export function lerEstados(
  pasta: string = process.env[VARIAVEL_PASTA] ?? PASTA_POR_OMISSAO,
): VotoAntecipadoEstado[] {
  const absoluta = path.resolve(process.cwd(), pasta);
  if (!existsSync(absoluta)) return [];
  const estados = readdirSync(absoluta)
    .filter((nome) => nome.endsWith(".json"))
    .sort()
    .flatMap((nome) => {
      const estado = lerEstado(path.join(pasta, nome));
      return estado ? [estado] : [];
    });
  const codigos = estados.map((e) => e.estado);
  const repetido = codigos.find((c, i) => codigos.indexOf(c) !== i);
  if (repetido) throw new Error(`Há mais de um ficheiro para o estado ${repetido} em ${pasta}`);
  return estados;
}

const cache = new Map<string, VistaVotoAntecipado[]>();

/**
 * Vistas de todos os estados com dados, do que tem mais votos para o que tem
 * menos. Guardadas em memória: várias páginas leem-nas no mesmo build.
 */
export function carregarVistas(pasta?: string): VistaVotoAntecipado[] {
  const chave = pasta ?? process.env[VARIAVEL_PASTA] ?? PASTA_POR_OMISSAO;
  let vistas = cache.get(chave);
  if (!vistas) {
    vistas = lerEstados(chave)
      .map(construirVista)
      .sort((a, b) => b.votos - a.votos || a.estado.localeCompare(b.estado));
    cache.set(chave, vistas);
  }
  return vistas;
}
