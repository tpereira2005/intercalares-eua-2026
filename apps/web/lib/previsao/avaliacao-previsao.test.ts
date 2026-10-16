import { describe, expect, it } from "vitest";
import type { ChamadaVista } from "../resultados/chamadas.ts";
import { avaliarPrevisao } from "./avaliacao.ts";
import type { VistaPrognosticos } from "./prognosticos.ts";
import type { CorridaVista, VistaPrevisao } from "./vista.ts";

function corrida(id: string, probD: number, decidida: "D" | "R" | null = null): CorridaVista {
  return { id, probD, camara: "camara", estado: id.slice(0, 2), decidida } as CorridaVista;
}

function previsao(corridas: CorridaVista[]): VistaPrevisao {
  return {
    congelada: true,
    corridasSenado: [],
    corridasCamara: corridas,
  } as unknown as VistaPrevisao;
}

function chamada(corrida: string, vencedor: "D" | "R" | "outro"): ChamadaVista {
  return {
    corrida,
    vencedor,
    candidato: null,
    redacao: "Associated Press",
    url: "https://apnews.com/",
    hora: "2026-11-04T03:00:00Z",
  };
}

const CORRIDAS = [
  corrida("AA-01", 0.9),
  corrida("BB-01", 0.3),
  corrida("CC-01", 0.55),
  corrida("DD-01", 0.02),
  corrida("EE-01", 1, "D"),
  corrida("FF-01", 0.5),
];

describe("avaliação da previsão", () => {
  it("conta acertos, Brier e pendentes só nas corridas em jogo chamadas", () => {
    const a = avaliarPrevisao(
      previsao(CORRIDAS),
      [
        chamada("AA-01", "D"),
        chamada("BB-01", "D"),
        chamada("EE-01", "D"),
        chamada("FF-01", "outro"),
      ],
      null,
    );
    expect(a.emJogo).toBe(5);
    expect(a.avaliadas.map((c) => c.corrida.id)).toEqual(["AA-01", "BB-01"]);
    expect(a.acertos).toBe(1);
    expect(a.brier).toBeCloseTo((0.1 ** 2 + 0.7 ** 2) / 2);
    expect(a.outro).toEqual(["FF-01"]);
    // AA-01 (90%) no grupo de 90% a 95%; BB-01 (favorito R a 70%) no de 70% a 80%.
    expect(a.calibracao.map((g) => [g.n, g.acertos])).toEqual([
      [0, 0],
      [0, 0],
      [1, 0],
      [0, 0],
      [1, 1],
      [0, 0],
    ]);
    expect(a.calibracao[2]?.esperado).toBeCloseTo(0.7);
  });

  it("sem chamadas não avalia nada", () => {
    const a = avaliarPrevisao(previsao(CORRIDAS), [], null);
    expect(a.avaliadas).toEqual([]);
    expect(a.brier).toBeNull();
  });

  it("avalia os outros prognosticadores nas mesmas corridas e conta os empates à parte", () => {
    const classificacao = (chave: string, posicao: number) => ({ chave, nome: chave, posicao });
    const prognosticos = {
      congelado: true,
      senado: { corridas: [] },
      camara: {
        corridas: [
          {
            corrida: { id: "BB-01" },
            consenso: 3,
            classificacoes: [classificacao("x", 2), classificacao("y", 3)],
          },
          { corrida: { id: "CC-01" }, consenso: 4, classificacoes: [classificacao("x", 4)] },
        ],
      },
    } as unknown as VistaPrognosticos;
    const a = avaliarPrevisao(
      previsao(CORRIDAS),
      [chamada("BB-01", "D"), chamada("CC-01", "R")],
      prognosticos,
    );
    expect(a.prognosticadores).toEqual([
      { chave: "x", nome: "x", classificadas: 2, acertos: 2, empates: 0, acertosEscrutinio: 0 },
      { chave: "y", nome: "y", classificadas: 1, acertos: 0, empates: 1, acertosEscrutinio: 0 },
    ]);
    expect(a.avaliadas.map((c) => c.consenso)).toEqual([3, 4]);
  });

  it("trocar os partidos dá a mesma avaliação", () => {
    const trocadas = CORRIDAS.map((c) => ({ ...c, probD: 1 - c.probD }));
    const chamadas = [chamada("AA-01", "D"), chamada("BB-01", "D"), chamada("DD-01", "R")];
    const trocar = (c: ChamadaVista): ChamadaVista => ({
      ...c,
      vencedor: c.vencedor === "D" ? "R" : "D",
    });
    const a = avaliarPrevisao(previsao(CORRIDAS), chamadas, null);
    const b = avaliarPrevisao(previsao(trocadas), chamadas.map(trocar), null);
    expect(b.acertos).toBe(a.acertos);
    expect(b.brier).toBeCloseTo(a.brier ?? Number.NaN);
    expect(b.calibracao).toEqual(a.calibracao);
  });
});
