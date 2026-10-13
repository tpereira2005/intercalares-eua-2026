/**
 * Validação, no build, dos ficheiros publicados pelo pipeline contra o esquema
 * JSON gerado a partir dos contratos pydantic (schemas/json/contratos.schema.json).
 */

import { readFileSync } from "node:fs";
import path from "node:path";
import Ajv2020, { type ValidateFunction } from "ajv/dist/2020.js";
import adicionarFormatos from "ajv-formats";

const ESQUEMA = "../../schemas/json/contratos.schema.json";

export type NomeContrato =
  | "VotoAntecipadoEstado"
  | "VotoAntecipadoAgregado"
  | "PrevisaoCongresso"
  | "HistoricoPrevisao"
  | "ResultadosParciais";

let ajv: Ajv2020 | undefined;
let id = "";
const validadores = new Map<NomeContrato, ValidateFunction>();

/** Validador de um contrato, compilado uma vez por build. */
export function obterValidador(contrato: NomeContrato): ValidateFunction {
  if (!ajv) {
    const esquema = JSON.parse(readFileSync(path.resolve(process.cwd(), ESQUEMA), "utf-8")) as {
      $id: string;
    };
    ajv = new Ajv2020({ allErrors: true, strict: false });
    adicionarFormatos(ajv);
    ajv.addSchema(esquema);
    id = esquema.$id;
  }
  let validador = validadores.get(contrato);
  if (!validador) {
    validador = ajv.compile({ $ref: `${id}#/$defs/${contrato}` });
    validadores.set(contrato, validador);
  }
  return validador;
}

export class DadosInvalidos extends Error {
  constructor(caminho: string, contrato: NomeContrato, detalhe: unknown) {
    super(`O ficheiro ${caminho} não cumpre o contrato ${contrato}: ${JSON.stringify(detalhe)}`);
    this.name = "DadosInvalidos";
  }
}
