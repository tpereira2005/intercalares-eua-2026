import { readFileSync } from "node:fs";
import type { HistoricoPrevisao, PrevisaoCongresso } from "@intercalares/contratos";
import { describe, expect, it } from "vitest";
import {
  caminhoPaginaCorrida,
  encontrarCorrida,
  evolucaoCorrida,
  fechoDoEstado,
  limitesMargem,
  todasCorridas,
  tituloCorrida,
} from "./corridas.ts";
import { construirEvolucao, construirVistaPrevisao } from "./previsao/vista.ts";

const vista = construirVistaPrevisao(
  JSON.parse(readFileSync("test/fixtures/previsao/2026.json", "utf-8")) as PrevisaoCongresso,
);
const historico = JSON.parse(
  readFileSync("test/fixtures/previsao/historico-2026.json", "utf-8"),
) as HistoricoPrevisao;

describe("páginas das corridas", () => {
  it("dá um endereço em minúsculas a cada corrida, Senado primeiro", () => {
    const corridas = todasCorridas(vista);
    expect(corridas).toHaveLength(10);
    expect(corridas[0]?.camara).toBe("senado");
    expect(caminhoPaginaCorrida("FL-S-especial")).toBe("/corridas/fl-s-especial/");
  });

  it("encontra a corrida pelo endereço, sem distinguir maiúsculas", () => {
    expect(encontrarCorrida(vista, "fl-s-especial")?.id).toBe("FL-S-especial");
    expect(encontrarCorrida(vista, "nc-01")?.id).toBe("NC-01");
    expect(encontrarCorrida(vista, "zz-s")).toBeNull();
  });

  it("dá títulos com o estado e a câmara", () => {
    const titulo = (id: string) => {
      const c = encontrarCorrida(vista, id);
      return c ? tituloCorrida(c) : null;
    };
    expect(titulo("NC-01")).toBe("NC-01 · Carolina do Norte");
    expect(titulo("TX-S")).toBe("Texas · Senado");
    expect(titulo("FL-S-especial")).toBe("Flórida · Senado (eleição especial)");
  });

  it("guarda a evolução de cada corrida e completa a probabilidade republicana", () => {
    const pontos = construirEvolucao(historico, "2026-10-13").corridas.get("TX-S") ?? [];
    expect(pontos.map((p) => p.corte)).toEqual(["2026-09-29", "2026-10-06", "2026-10-13"]);
    expect(pontos[1]?.probD).toBe(0.7101);
    const [primeiro] = evolucaoCorrida(pontos);
    expect((primeiro?.probD ?? 0) + (primeiro?.probR ?? 0)).toBeCloseTo(1);
  });

  it("encontra o fecho das urnas do estado", () => {
    expect(fechoDoEstado("NC")?.primeiro).toBe("2026-11-04T00:30:00Z");
  });

  it("alarga o eixo da margem a múltiplos de 10 que incluem o empate", () => {
    expect(limitesMargem([3.2, 8.9, -4.1])).toEqual([-10, 10]);
    expect(limitesMargem([12, 31])).toEqual([0, 40]);
    expect(limitesMargem([-22, -5])).toEqual([-30, 0]);
    expect(limitesMargem([0])).toEqual([-10, 10]);
  });
});
