import { readFileSync } from "node:fs";
import type { VotoAntecipadoAgregado } from "@intercalares/contratos";
import { describe, expect, it } from "vitest";
import { construirVistaAgregada } from "./agregado.ts";
import { resumirAgregado } from "./resumo.ts";

const BASE = JSON.parse(
  readFileSync("test/fixtures/pa-agregado-sintetico.json", "utf-8"),
) as VotoAntecipadoAgregado;

/** Um estado como o Arizona: totais por condado, sem partido, de uma fonte não oficial. */
function semPartido(): VotoAntecipadoAgregado {
  return {
    ...BASE,
    dimensoes: ["modalidade", "condado"],
    comparacao: [],
    metadados: {
      ...BASE.metadados,
      fontes: [{ ...BASE.metadados.fontes[0], oficial: false }],
    },
    pedidos: [
      {
        ano: BASE.ano,
        faixa: "total",
        partido: "total",
        pedidos: 1000,
        devolvidos: 250,
        pendentes: 750,
      },
    ],
    geografia: [
      {
        ano: BASE.ano,
        nivel: "condado",
        codigo: "04013",
        nome: "Maricopa",
        partido: "total",
        votos: 600,
        faixa: "total",
      },
      {
        ano: BASE.ano,
        nivel: "condado",
        codigo: "04019",
        nome: "Pima",
        partido: "total",
        votos: 150,
      },
      {
        ano: BASE.ano,
        nivel: "condado",
        codigo: "04001",
        nome: "Apache",
        partido: "total",
        votos: 250,
        faixa: "total",
      },
      {
        ano: 2022,
        nivel: "condado",
        codigo: "04001",
        nome: "Apache",
        partido: "total",
        votos: 999,
        faixa: "total",
      },
    ],
  };
}

describe("estado agregado sem partido nem fonte oficial", () => {
  const vista = construirVistaAgregada(semPartido());

  it("assinala a fonte não oficial e a falta de partido", () => {
    expect(vista.naoOficial).toBe(true);
    expect(vista.semPartido).toBe(true);
    expect(resumirAgregado(vista).naoOficial).toBe(true);
    expect(construirVistaAgregada(BASE).naoOficial).toBe(false);
  });

  it("soma os boletins emitidos e devolvidos sem partido", () => {
    expect(vista.pedidos.partidos).toEqual([]);
    expect(vista.pedidosTotal).toEqual({ pedidos: 1000, devolvidos: 250 });
  });

  it("ordena os condados de 2026 pelos votos, com a quota do estado", () => {
    expect(vista.condados.map((c) => [c.nome, c.quota])).toEqual([
      ["Maricopa", 0.6],
      ["Apache", 0.25],
      ["Pima", 0.15],
    ]);
  });
});
