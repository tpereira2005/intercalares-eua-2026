import type { VotoAntecipadoNacional } from "@intercalares/contratos";
import { describe, expect, it } from "vitest";
import { sinalCondados } from "./condados.ts";

function nacional(): VotoAntecipadoNacional {
  return {
    ano: 2026,
    estados: [
      {
        estado: "PA",
        ano_base: 2022,
        condados_presidenciais: [
          { ano: 2026, votos_trump: 300, votos_harris: 700, margem_ponderada: 12 },
          { ano: 2022, votos_trump: 250, votos_harris: 750, margem_ponderada: 15.5 },
        ],
      },
      {
        estado: "NC",
        ano_base: 2022,
        condados_presidenciais: [
          { ano: 2026, votos_trump: 1500, votos_harris: 1500, margem_ponderada: null },
        ],
      },
      { estado: "ME", ano_base: 2022 },
    ],
  } as unknown as VotoAntecipadoNacional;
}

describe("sinal dos condados de Trump e de Harris", () => {
  it("calcula a quota dos condados de Trump e a variação face ao ano de referência", () => {
    const [nc, pa] = sinalCondados(nacional());
    expect(nc?.estado).toBe("NC");
    expect(nc?.base).toBeNull();
    expect(nc?.variacaoQuota).toBeNull();
    expect(pa?.atual.quotaTrump).toBeCloseTo(0.3);
    expect(pa?.variacaoQuota).toBeCloseTo(0.05);
    expect(pa?.variacaoMargem).toBeCloseTo(-3.5);
  });

  it("deixa de fora os estados sem o sinal e não falha sem resumo", () => {
    expect(sinalCondados(nacional()).map((s) => s.estado)).not.toContain("ME");
    expect(sinalCondados(null)).toEqual([]);
  });
});
