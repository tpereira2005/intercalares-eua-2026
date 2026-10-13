/**
 * Lê e valida, no build, o ficheiro do voto antecipado publicado pelo pipeline.
 *
 * O ficheiro não está no repositório: `pnpm --filter @intercalares/web dados:obter`
 * descarrega-o da Release pública antes do build. Sem ficheiro, a página mostra
 * "em preparação"; com um ficheiro que não cumpre o contrato, o build falha,
 * porque dados que falham a validação nunca são publicados.
 */

import { existsSync, readFileSync } from "node:fs";
import path from "node:path";
import type { VotoAntecipadoEstado } from "@intercalares/contratos";
import Ajv2020, { type ValidateFunction } from "ajv/dist/2020.js";
import adicionarFormatos from "ajv-formats";
import { construirVista, type VistaVotoAntecipado } from "./vista.ts";

/** Caminho do ficheiro, relativo a apps/web; a variável de ambiente substitui-o. */
export const CAMINHO_POR_OMISSAO = "dados/voto-antecipado/nc.json";
export const VARIAVEL_CAMINHO = "DADOS_VOTO_ANTECIPADO";

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

/** Lê e valida o ficheiro; `null` quando ainda não existe. */
export function lerEstado(
  caminho: string = process.env[VARIAVEL_CAMINHO] ?? CAMINHO_POR_OMISSAO,
): VotoAntecipadoEstado | null {
  const absoluto = path.resolve(process.cwd(), caminho);
  if (!existsSync(absoluto)) return null;
  const dados: unknown = JSON.parse(readFileSync(absoluto, "utf-8"));
  const valido = obterValidador();
  if (!valido(dados)) {
    throw new DadosInvalidos(caminho, valido.errors?.slice(0, 5));
  }
  return dados;
}

export function carregarVista(caminho?: string): VistaVotoAntecipado | null {
  const estado = caminho === undefined ? lerEstado() : lerEstado(caminho);
  return estado === null ? null : construirVista(estado);
}
