import { describe, expect, it } from "vitest";
import type { ChamadaVista } from "../resultados/chamadas.ts";
import { avaliarPrevisao } from "./avaliacao.ts";

function chamada(corrida: string, vencedor: ChamadaVista["vencedor"]): ChamadaVista {
  return {
    corrida,
    vencedor,
    candidato: null,
    redacao: "Associated Press",
    url: "https://apnews.com/",
    hora: "2026-11-04T02:00:00Z",
  };
}

describe("avaliação da previsão", () => {
  it("conta acertos, surpresas e o Brier só nas corridas previstas", () => {
    const avaliacao = avaliarPrevisao(
      [
        chamada("NC-S", "D"),
        chamada("OH-S", "D"),
        chamada("ME-S", "R"),
        chamada("AK-S", "outro"),
        chamada("XX-01", "R"),
      ],
      { "NC-S": 0.8, "OH-S": 0.3, "ME-S": 0.5, "AK-S": 0.2 },
    );
    expect(avaliacao.avaliadas).toBe(3);
    expect(avaliacao.acertos).toBe(1);
    expect(avaliacao.surpresas.map((s) => s.corrida)).toEqual(["OH-S"]);
    expect(avaliacao.surpresas[0]?.probVencedor).toBeCloseTo(0.3);
    expect(avaliacao.brier).toBeCloseTo((0.04 + 0.49 + 0.25) / 3);
  });

  it("não dá Brier sem corridas avaliadas", () => {
    expect(avaliarPrevisao([], {}).brier).toBeNull();
  });
});
