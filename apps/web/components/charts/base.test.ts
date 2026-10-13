import { describe, expect, it } from "vitest";
import { afastarRotulos, escala } from "./base.tsx";

describe("escala", () => {
  it("arredonda o máximo a um passo redondo", () => {
    expect(escala(0.0203)).toEqual({ maximo: 0.025, marcas: [0, 0.005, 0.01, 0.015, 0.02, 0.025] });
    expect(escala(0.342)).toEqual({ maximo: 0.4, marcas: [0, 0.1, 0.2, 0.3, 0.4] });
    expect(escala(0.0085).maximo).toBe(0.01);
  });
});

describe("afastarRotulos", () => {
  it("afasta rótulos sobrepostos sem mudar a ordem", () => {
    expect(afastarRotulos([100, 104, 50])).toEqual([100, 112, 50]);
  });
});
