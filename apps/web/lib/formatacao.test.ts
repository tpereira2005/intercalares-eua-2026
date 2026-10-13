import { describe, expect, it } from "vitest";
import {
  diasAteEleicao,
  formatarData,
  formatarNumero,
  formatarPercentagem,
  formatarPontos,
} from "./formatacao.ts";

describe("formatação pt-PT", () => {
  it("usa vírgula decimal nas percentagens", () => {
    expect(formatarPercentagem(0.124)).toBe("12,4%");
    expect(formatarPercentagem(0.5, 0)).toBe("50%");
  });

  it("agrupa milhares com espaço", () => {
    expect(formatarNumero(1234567).replace(/\s/g, " ")).toBe("1 234 567");
  });

  it("mostra o sinal das diferenças em pontos percentuais", () => {
    expect(formatarPontos(0.032)).toBe("+3,2 p.p.");
    expect(formatarPontos(-0.015)).toBe("-1,5 p.p.");
    expect(formatarPontos(0)).toBe("0,0 p.p.");
  });

  it("escreve datas por extenso", () => {
    expect(formatarData(new Date("2026-11-03T15:00:00Z"))).toBe("3 de novembro de 2026");
  });

  it("conta os dias até à eleição", () => {
    expect(diasAteEleicao(new Date("2026-10-13T12:00:00Z"))).toBe(21);
    expect(diasAteEleicao(new Date("2026-11-10T12:00:00Z"))).toBe(0);
  });
});
