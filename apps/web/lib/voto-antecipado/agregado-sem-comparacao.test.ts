import { readFileSync } from "node:fs";
import type { VotoAntecipadoAgregado } from "@intercalares/contratos";
import { describe, expect, it } from "vitest";
import { construirVistaAgregada } from "./agregado.ts";

const BASE = JSON.parse(
  readFileSync("test/fixtures/pa-agregado-sintetico.json", "utf-8"),
) as VotoAntecipadoAgregado;

type Ponto = VotoAntecipadoAgregado["serie"][number];

function ponto(partido: Ponto["partido"], modalidade: Ponto["modalidade"], votos: number): Ponto {
  return { ano: 2026, dias_antes: 18, faixa: "total", partido, modalidade, votos };
}

/** Um estado como o Nevada: só totais do dia, de uma fonte não oficial, sem anos de comparação. */
function semComparacao(): VotoAntecipadoAgregado {
  return {
    ...BASE,
    ano: 2026,
    dias_antes: 18,
    dimensoes: ["modalidade", "partido"],
    comparacao: [],
    geografia: [],
    serie: [
      ponto("total", "total", 1000),
      ponto("total", "correio", 900),
      ponto("total", "presencial", 100),
      ponto("dem", "total", 400),
      ponto("rep", "total", 350),
      ponto("nao_afiliado", "total", 250),
      // Outro dia não entra na composição do dia do ficheiro.
      { ...ponto("dem", "total", 5000), dias_antes: 19 },
    ],
  };
}

describe("estado agregado sem anos de comparação", () => {
  it("dá as quotas de 2026 por partido e modalidade, sem base nem ritmo", () => {
    const vista = construirVistaAgregada(semComparacao());
    expect(vista.comparacoes).toEqual([]);
    expect(vista.composicao.partidos.map((p) => [p.categoria, p.quota])).toEqual([
      ["dem", 0.4],
      ["rep", 0.35],
      ["nao_afiliado", 0.25],
    ]);
    expect(vista.composicao.modalidades.map((m) => [m.categoria, m.quota])).toEqual([
      ["correio", 0.9],
      ["presencial", 0.1],
    ]);
    expect(vista.composicao.partidos.every((p) => p.quotaBase === null && p.ritmo === null)).toBe(
      true,
    );
  });

  it("fica vazia quando a fonte não dá partido", () => {
    const dados = semComparacao();
    const vista = construirVistaAgregada({
      ...dados,
      serie: dados.serie.filter((p) => p.partido === "total"),
    });
    expect(vista.composicao.partidos).toEqual([]);
  });
});
