import { describe, expect, it } from "vitest";
import { COLUNAS_GRELHA, ESTADOS, LINHAS_GRELHA, nomeEstado } from "./estados.ts";

describe("estados", () => {
  it("tem os 50 estados e o Distrito de Colúmbia, cada um numa casa diferente", () => {
    expect(ESTADOS).toHaveLength(51);
    expect(new Set(ESTADOS.map((e) => e.codigo)).size).toBe(51);
    expect(new Set(ESTADOS.map((e) => `${e.coluna},${e.linha}`)).size).toBe(51);
    for (const e of ESTADOS) {
      expect(e.coluna).toBeLessThan(COLUNAS_GRELHA);
      expect(e.linha).toBeLessThan(LINHAS_GRELHA);
    }
  });

  it("dá o nome em português", () => {
    expect(nomeEstado("NC")).toBe("Carolina do Norte");
  });
});
