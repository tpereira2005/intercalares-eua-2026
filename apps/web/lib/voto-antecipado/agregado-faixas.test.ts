import { readFileSync } from "node:fs";
import type { VotoAntecipadoAgregado } from "@intercalares/contratos";
import { describe, expect, it } from "vitest";
import { construirVistaAgregada } from "./agregado.ts";
import { resumirAgregado } from "./resumo.ts";

const BASE = JSON.parse(
  readFileSync("test/fixtures/pa-agregado-sintetico.json", "utf-8"),
) as VotoAntecipadoAgregado;

/** As faixas canónicas da Pensilvânia trocadas pelas de dez anos do Colorado. */
const DEZ_ANOS: Record<string, string> = {
  "25-29": "25-34",
  "30-39": "35-44",
  "40-49": "45-54",
  "50-64": "55-64",
};

function comoColorado(): VotoAntecipadoAgregado {
  return {
    ...BASE,
    estado: "CO",
    comparacao: BASE.comparacao.map((l) =>
      l.dimensao === "faixa" ? { ...l, categoria: DEZ_ANOS[l.categoria] ?? l.categoria } : l,
    ),
  };
}

describe("faixas etárias do próprio ficheiro", () => {
  it("usa as faixas canónicas quando o ficheiro as traz", () => {
    const vista = construirVistaAgregada(BASE);
    expect(vista.comparacoes[0]?.faixas.map((f) => f.categoria)).toEqual([
      "18-24",
      "25-29",
      "30-39",
      "40-49",
      "50-64",
      "65-74",
      "75+",
    ]);
    expect(vista.faixasDezAnos).toBe(false);
  });

  it("mostra as faixas de dez anos do Colorado, por idade, e assinala-as", () => {
    const vista = construirVistaAgregada(comoColorado());
    expect(vista.comparacoes[0]?.faixas.map((f) => f.categoria)).toEqual([
      "18-24",
      "25-34",
      "35-44",
      "45-54",
      "55-64",
      "65-74",
      "75+",
    ]);
    expect(vista.faixasDezAnos).toBe(true);
  });

  it("a quota dos 65+ soma as faixas comuns, que têm os mesmos limites", () => {
    const pa = resumirAgregado(construirVistaAgregada(BASE));
    const co = resumirAgregado(construirVistaAgregada(comoColorado()));
    expect(co.quota65).not.toBeNull();
    expect(co.quota65).toBeCloseTo(pa.quota65 ?? Number.NaN);
  });
});
