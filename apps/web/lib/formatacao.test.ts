import { describe, expect, it } from "vitest";
import {
  diasAteEleicao,
  formatarCompacto,
  formatarData,
  formatarDataCurta,
  formatarDataHora,
  formatarDuracao,
  formatarHora,
  formatarDiaCiclo,
  formatarMargem,
  formatarMargemPontos,
  formatarNumero,
  formatarPercentagem,
  formatarPontos,
  formatarVariacao,
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
    expect(formatarPontos(0.032)).toBe("+3,2 pp");
    expect(formatarPontos(-0.015)).toBe("-1,5 pp");
    expect(formatarPontos(0)).toBe("0,0 pp");
  });

  it("escreve margens dadas em pontos", () => {
    expect(formatarMargemPontos(8.44)).toBe("D +8,4");
    expect(formatarMargemPontos(-2, 0)).toBe("R +2");
    expect(formatarMargemPontos(0.01)).toBe("Empate");
  });

  it("escreve datas curtas para eixos", () => {
    expect(formatarDataCurta(new Date("2026-10-13T12:00:00Z"))).toBe("13 out.");
  });

  it("escreve datas por extenso", () => {
    expect(formatarData(new Date("2026-11-03T15:00:00Z"))).toBe("3 de novembro de 2026");
  });

  it("conta os dias até à eleição", () => {
    expect(diasAteEleicao(new Date("2026-10-13T12:00:00Z"))).toBe(21);
    expect(diasAteEleicao(new Date("2026-11-10T12:00:00Z"))).toBe(0);
  });

  it("escreve margens com o partido à frente", () => {
    expect(formatarMargem(0.012)).toBe("D +1,2");
    expect(formatarMargem(-0.006)).toBe("R +0,6");
    expect(formatarMargem(0.0004)).toBe("Empate");
  });

  it("escreve o dia do ciclo com o sinal menos tipográfico", () => {
    expect(formatarDiaCiclo(21)).toBe("E\u221221");
    expect(formatarDiaCiclo(0)).toBe("Dia E");
    expect(formatarDiaCiclo(-2)).toBe("E+2");
  });

  it("escreve variações relativas com sinal", () => {
    expect(formatarVariacao(0.12)).toBe("+12%");
    expect(formatarVariacao(-0.374)).toBe("-37%");
    expect(formatarVariacao(0)).toBe("0%");
  });

  it("abrevia números grandes", () => {
    expect(formatarCompacto(1_119_646)).toMatch(/^1,12\sM$/);
    expect(formatarCompacto(29_743)).toMatch(/^29,7\smil$/);
    expect(formatarCompacto(950)).toBe("950");
  });

  it("escreve dia e hora na costa leste, em 24 horas", () => {
    // 02:34 UTC de 4 de novembro são 21:34 de 3 de novembro em Nova Iorque (EST).
    expect(formatarDataHora(new Date("2026-11-04T02:34:00Z"))).toBe("3 de novembro, 21:34");
  });

  it("escreve a hora na costa leste", () => {
    expect(formatarHora(new Date("2026-11-04T02:34:00Z"))).toBe("21:34");
  });

  it("escreve durações curtas", () => {
    const min = 60_000;
    expect(formatarDuracao(30_000)).toBe("menos de 1 min");
    expect(formatarDuracao(9 * min)).toBe("9 min");
    expect(formatarDuracao(134 * min)).toBe("2 h 14 min");
    expect(formatarDuracao(120 * min)).toBe("2 h");
    expect(formatarDuracao((3 * 1440 + 4 * 60 + 5) * min)).toBe("3 d 4 h");
  });
});
