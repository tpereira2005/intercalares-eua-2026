import { describe, expect, it } from "vitest";
import type { Fonte, Metadados } from "../src/index.ts";

describe("contratos gerados", () => {
  it("descrevem os metadados publicados pelo pipeline", () => {
    const fonte = {
      nome: "North Carolina State Board of Elections",
      url: "https://www.ncsbe.gov/results-data",
      licenca: null,
      obtida_em: "2026-10-13T12:00:00Z",
    } satisfies Fonte;
    const metadados = {
      versao_esquema: "0.1.0",
      gerado_em: "2026-10-13T12:05:00Z",
      fontes: [fonte],
    } satisfies Metadados;

    expect(metadados.fontes).toHaveLength(1);
  });
});
