import { readFileSync } from "node:fs";
import type { VotoAntecipadoAgregado } from "@intercalares/contratos";
import { describe, expect, it } from "vitest";
import { construirVistaAgregada } from "./agregado.ts";
import { linhasUnidades } from "./geografia.ts";

const BASE = JSON.parse(
  readFileSync("test/fixtures/pa-agregado-sintetico.json", "utf-8"),
) as VotoAntecipadoAgregado;

type Linha = VotoAntecipadoAgregado["geografia"][number];

function linha(
  ano: number,
  faixa: NonNullable<Linha["faixa"]>,
  votos: number,
  partido: Linha["partido"] = "total",
): Linha {
  return { ano, nivel: "condado", codigo: "42001", nome: "Adams", partido, faixa, votos };
}

describe("geografia dos estados agregados", () => {
  it("fica vazia quando a fonte não dá a idade por condado", () => {
    expect(construirVistaAgregada(BASE).geografia).toEqual([]);
  });

  it("usa as linhas por faixa, sem recenseados nem participação", () => {
    const dados: VotoAntecipadoAgregado = {
      ...BASE,
      geografia: [
        linha(2026, "total", 1000),
        linha(2026, "65+", 500),
        linha(2026, "total", 400, "dem"),
        linha(2022, "total", 800),
        linha(2022, "65+", 320),
      ],
    };
    const { geografia } = construirVistaAgregada(dados);
    expect(geografia).toHaveLength(1);
    const [adams] = linhasUnidades(geografia, "condado", "65+", 2026, 2022);
    expect(adams?.quota).toBeCloseTo(0.5);
    expect(adams?.quotaBase).toBeCloseTo(0.4);
    expect(adams?.diferenca).toBeCloseTo(0.1);
    expect(adams?.taxa).toBeNull();
    // A linha por partido não entra: o total da unidade é o da linha total/total.
    expect(adams?.votos).toBe(1000);
  });
});
