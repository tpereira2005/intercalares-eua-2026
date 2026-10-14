import { describe, expect, it } from "vitest";
import { caminhoMaioria, lugaresNecessarios, ordemDoLado } from "./cenarios.ts";
import type { CorridaVista, ResumoVista, VistaPrevisao } from "./vista.ts";

function corrida(id: string, probD: number, margem: number): CorridaVista {
  return { id, probD, margem, camara: "senado" } as CorridaVista;
}

/** Senado de 10 lugares, maioria 6, com 2 lugares D e 3 R fora de jogo e 5 corridas. */
function vistaTeste(limiar: number | null): VistaPrevisao {
  const resumo = {
    total: 10,
    maioria: 6,
    probD: 0.55,
    probR: 0.45,
    foraDeJogo: { D: 2, R: 3 },
    limiar,
  } as ResumoVista;
  return {
    ambiente: { margem: 2, desvio: 3, p10: -2, p90: 6, fonte: "agregadores", agregadores: [] },
    senado: resumo,
    camara: resumo,
    corridasSenado: [
      corrida("C", 0.5, 0.1),
      corrida("A", 0.9, 8),
      corrida("E", 0.1, -9),
      corrida("B", 0.7, 3),
      corrida("D", 0.3, -2),
    ],
    corridasCamara: [],
  } as unknown as VistaPrevisao;
}

describe("caminho para a maioria", () => {
  it("dá aos republicanos o desempate de um Senado dividido", () => {
    expect(lugaresNecessarios(100, 51, "D")).toBe(51);
    expect(lugaresNecessarios(100, 51, "R")).toBe(50);
    expect(lugaresNecessarios(435, 218, "R")).toBe(218);
  });

  it("ordena as corridas pela probabilidade de cada lado", () => {
    const corridas = vistaTeste(1).corridasSenado;
    expect(ordemDoLado(corridas, "D").map((c) => c.id)).toEqual(["A", "B", "C", "D", "E"]);
    expect(ordemDoLado(corridas, "R").map((c) => c.id)).toEqual(["E", "D", "C", "B", "A"]);
  });

  it("encontra a corrida decisiva de cada lado com a mesma regra", () => {
    const d = caminhoMaioria(vistaTeste(1), "senado", "D", 1);
    expect(d?.vitoriasNecessarias).toBe(4);
    expect(d?.corridas.map((c) => [c.corrida.id, c.posicao, c.decisiva])).toEqual([
      ["C", 3, false],
      ["D", 4, true],
      ["E", 5, false],
    ]);
    const r = caminhoMaioria(vistaTeste(1), "senado", "R", 1);
    expect(r?.precisa).toBe(5);
    expect(r?.vitoriasNecessarias).toBe(2);
    expect(r?.corridas.find((c) => c.decisiva)?.corrida.id).toBe("D");
    expect(r?.corridas[0]?.prob).toBeCloseTo(0.9);
  });

  it("mede a folga de cada lado face ao limiar com sinais opostos", () => {
    expect(caminhoMaioria(vistaTeste(1), "senado", "D")?.folga).toBe(1);
    expect(caminhoMaioria(vistaTeste(1), "senado", "R")?.folga).toBe(-1);
    expect(caminhoMaioria(vistaTeste(null), "senado", "R")?.folga).toBeNull();
  });

  it("não inventa caminho quando o lado não precisa de corridas", () => {
    const vista = vistaTeste(1);
    vista.senado.foraDeJogo.D = 6;
    expect(caminhoMaioria(vista, "senado", "D")).toBeNull();
  });
});
