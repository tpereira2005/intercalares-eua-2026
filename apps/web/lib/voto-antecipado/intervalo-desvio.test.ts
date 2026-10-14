import { describe, expect, it } from "vitest";
import { intervalosDesvio, type ComparacaoAno, type LinhaFaixa } from "./vista.ts";

function faixa(desvio: number | null, min: number | null, max: number | null): LinhaFaixa {
  return { faixa: "18-24", desvio, desvioMin: min, desvioMax: max } as LinhaFaixa;
}

function comparacao(
  anoBase: number,
  tipo: ComparacaoAno["tipo"],
  linha: LinhaFaixa,
): ComparacaoAno {
  return { anoBase, tipo, faixas: [linha] } as ComparacaoAno;
}

describe("intervalo do desvio", () => {
  it("é o envelope das referências intercalares e ignora as presidenciais", () => {
    const intervalos = intervalosDesvio([
      comparacao(2022, "intercalar", faixa(0.1, 0.05, 0.12)),
      comparacao(2018, "intercalar", faixa(-0.02, -0.04, 0.01)),
      comparacao(2024, "presidencial", faixa(-0.3, -0.4, -0.2)),
    ]);
    expect(intervalos["18-24"]).toEqual({ min: -0.04, max: 0.12, anos: [2018, 2022] });
    expect(intervalos["65-74"]).toBeUndefined();
  });

  it("fica vazio enquanto o ficheiro não traz os limites", () => {
    expect(intervalosDesvio([comparacao(2022, "intercalar", faixa(0.1, null, null))])).toEqual({});
  });
});
