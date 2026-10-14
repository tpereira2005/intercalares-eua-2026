import { readFileSync } from "node:fs";
import type { PontoSerieAgregado, VotoAntecipadoAgregado } from "@intercalares/contratos";
import { describe, expect, it } from "vitest";
import { construirVistaAgregada } from "./agregado.ts";

const BASE = JSON.parse(
  readFileSync("test/fixtures/pa-agregado-sintetico.json", "utf-8"),
) as VotoAntecipadoAgregado;

function ponto(
  ano: number,
  faixa: PontoSerieAgregado["faixa"],
  partido: PontoSerieAgregado["partido"],
  votos: number,
  dias = BASE.dias_antes,
  modalidade: PontoSerieAgregado["modalidade"] = "total",
): PontoSerieAgregado {
  return { ano, dias_antes: dias, faixa, partido, modalidade, votos };
}

function comCruzamentos(): VotoAntecipadoAgregado {
  const anoBase = construirVistaAgregada(BASE).comparacoes[0]?.anoBase ?? 2022;
  return {
    ...BASE,
    serie: [
      ...BASE.serie,
      ponto(BASE.ano, "18-24", "dem", 60),
      ponto(BASE.ano, "18-24", "rep", 30),
      ponto(BASE.ano, "18-24", "outro", 10),
      ponto(anoBase, "18-24", "dem", 50),
      ponto(anoBase, "18-24", "rep", 40),
      ponto(anoBase, "18-24", "outro", 10),
      // Outro dia do ciclo: não entra.
      ponto(BASE.ano, "65-74", "dem", 99, BASE.dias_antes + 1),
      ponto(BASE.ano, "18-24", "total", 75, BASE.dias_antes, "correio"),
      ponto(BASE.ano, "18-24", "total", 25, BASE.dias_antes, "presencial"),
    ],
  };
}

describe("idade × partido nos estados agregados", () => {
  it("só usa as linhas do dia do ficheiro e compara com o ano de referência", () => {
    const vista = construirVistaAgregada(comCruzamentos());
    expect(vista.cruzamentos.map((l) => l.faixa)).toEqual(["18-24"]);
    const [jovens] = vista.cruzamentos;
    expect(jovens?.partidos.dem).toBeCloseTo(0.6);
    expect(jovens?.partidos.outro).toBeCloseTo(0.1);
    // (0,6 − 0,3) − (0,5 − 0,4) = 0,2
    expect(jovens?.variacaoDemRep).toBeCloseTo(0.2);
    expect(jovens?.correio).toBeCloseTo(0.75);
    expect(vista.anoCruzamentos).toBe(vista.comparacoes[0]?.anoBase);
  });

  it("fica vazio quando a série não cruza idade com partido", () => {
    const vista = construirVistaAgregada({
      ...BASE,
      serie: BASE.serie.filter((p) => p.faixa === "total" || p.partido === "total"),
    });
    expect(vista.cruzamentos).toEqual([]);
    expect(vista.anoCruzamentos).toBeNull();
  });
});
