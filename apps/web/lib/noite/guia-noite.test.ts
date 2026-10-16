import { describe, expect, it } from "vitest";
import type { FechoEstado } from "../fecho.ts";
import type { VistaPrognosticos } from "../previsao/prognosticos.ts";
import type { CorridaVista, ResumoVista, VistaPrevisao } from "../previsao/vista.ts";
import { construirGuia, ordemContagem } from "./guia.ts";

function corrida(
  id: string,
  estado: string,
  probD: number,
  camara: "senado" | "camara" = "senado",
): CorridaVista {
  return {
    id,
    estado,
    probD,
    margem: (probD - 0.5) * 20,
    camara,
    decidida: null,
  } as unknown as CorridaVista;
}

/**
 * Senado de 13 lugares, maioria 7, com 1 lugar D e 2 R fora de jogo e 10 corridas: os
 * democratas precisam de 6 vitórias e os republicanos de 5. Câmara de 1 lugar.
 */
function vistaTeste(corridas: CorridaVista[], foraDeJogo = { D: 1, R: 2 }): VistaPrevisao {
  const resumo = { total: 13, maioria: 7, probD: 0.5, probR: 0.5, foraDeJogo, limiar: null };
  return {
    ambiente: { margem: 0, desvio: 3, p10: -4, p90: 4, fonte: "agregadores", agregadores: [] },
    senado: resumo as ResumoVista,
    camara: { ...resumo, total: 1, maioria: 1, foraDeJogo: { D: 0, R: 0 } } as ResumoVista,
    corridasSenado: corridas.filter((c) => c.camara === "senado"),
    corridasCamara: corridas.filter((c) => c.camara === "camara"),
  } as unknown as VistaPrevisao;
}

const FECHOS: FechoEstado[] = [
  { estado: "GA", primeiro: "2026-11-04T00:00:00Z" },
  { estado: "VT", primeiro: "2026-11-04T00:00:00Z" },
  { estado: "OH", primeiro: "2026-11-04T00:30:00Z" },
  { estado: "PA", primeiro: "2026-11-04T01:00:00Z" },
  { estado: "DE", primeiro: "2026-11-04T01:00:00Z" },
  { estado: "IL", primeiro: "2026-11-04T01:00:00Z" },
  { estado: "AL", primeiro: "2026-11-04T01:00:00Z" },
  { estado: "WY", primeiro: "2026-11-04T02:00:00Z" },
  { estado: "ID", primeiro: "2026-11-04T03:00:00Z", todas: "2026-11-04T04:00:00Z" },
  { estado: "UT", primeiro: "2026-11-04T03:00:00Z" },
];

// Pela ordem democrata, a decisiva é OH-S (6.ª); pela republicana também (5.ª). As duas
// janelas de vizinhas apanham GA, PA, OH, AL e ID.
const CORRIDAS = [
  corrida("VT-S", "VT", 0.99),
  corrida("DE-S", "DE", 0.98),
  corrida("IL-S", "IL", 0.97),
  corrida("GA-S", "GA", 0.55),
  corrida("PA-S", "PA", 0.48),
  corrida("OH-S", "OH", 0.3),
  corrida("AL-S", "AL", 0.04),
  corrida("ID-S", "ID", 0.02),
  corrida("UT-S", "UT", 0.015),
  corrida("WY-S", "WY", 0.01),
  corrida("PA-07", "PA", 0.51, "camara"),
];

function ids(vista: ReturnType<typeof construirGuia>): string[] {
  return vista.blocos.flatMap((b) => b.estados.flatMap((e) => e.corridas.map((c) => c.corrida.id)));
}

describe("guia da noite", () => {
  it("diz a ordem de contagem só nos estados em que é clara", () => {
    expect(ordemContagem("NC")).toBe("antecipadoPrimeiro");
    expect(ordemContagem("PA")).toBe("correioDepois");
    expect(ordemContagem("SC")).toBeNull();
  });

  it("agrupa pela hora de fecho e deixa de fora as sólidas longe da maioria", () => {
    const guia = construirGuia(vistaTeste(CORRIDAS), null, FECHOS);
    expect(guia.blocos.map((b) => b.instante)).toEqual([
      "2026-11-04T00:00:00Z",
      "2026-11-04T00:30:00Z",
      "2026-11-04T01:00:00Z",
      "2026-11-04T02:00:00Z",
      "2026-11-04T03:00:00Z",
    ]);
    expect(new Set(ids(guia))).toEqual(new Set(["GA-S", "PA-S", "OH-S", "AL-S", "ID-S", "PA-07"]));
    expect(guia.blocos[0]?.semCorridas).toEqual(["VT"]);
    expect(guia.blocos[2]?.semCorridas).toEqual(["DE", "IL"]);
    expect(guia.blocos[3]?.estados).toEqual([]);
    expect(guia.blocos[4]?.semCorridas).toEqual(["UT"]);
    expect(guia.total).toBe(6);
  });

  it("põe o Senado primeiro em cada estado e marca a decisiva de cada lado", () => {
    const guia = construirGuia(vistaTeste(CORRIDAS), null, FECHOS);
    const bloco = guia.blocos[2];
    // Na mesma hora, primeiro o estado com a corrida mais renhida.
    expect(bloco?.estados.map((e) => e.estado)).toEqual(["PA", "AL"]);
    expect(bloco?.estados[0]?.contagem).toBe("correioDepois");
    expect(bloco?.estados[0]?.corridas.map((c) => c.corrida.id)).toEqual(["PA-S", "PA-07"]);
    expect(guia.decisivas.map((d) => [d.camara, d.lado, d.corrida.id, d.fecho])).toEqual([
      ["senado", "D", "OH-S", "2026-11-04T00:30:00Z"],
      ["senado", "R", "OH-S", "2026-11-04T00:30:00Z"],
      ["camara", "D", "PA-07", "2026-11-04T01:00:00Z"],
      ["camara", "R", "PA-07", "2026-11-04T01:00:00Z"],
    ]);
    const oh = guia.blocos[1]?.estados[0];
    expect(oh?.contagem).toBe("antecipadoPrimeiro");
    expect(oh?.corridas[0]?.decisivaPara).toEqual(["D", "R"]);
  });

  it("segue uma sólida que os outros prognosticadores dão como inclinada", () => {
    const consenso = {
      senado: { corridas: [{ corrida: { id: "UT-S" }, consenso: 4 }] },
      camara: { corridas: [] },
    } as unknown as VistaPrognosticos;
    const guia = construirGuia(vistaTeste(CORRIDAS), consenso, FECHOS);
    const bloco = guia.blocos[4];
    expect(bloco?.estados.map((e) => e.estado)).toEqual(["ID", "UT"]);
    expect(bloco?.estados[0]?.todas).toBe("2026-11-04T04:00:00Z");
    expect(bloco?.estados[1]?.corridas[0]?.consenso).toBe(4);
    expect(bloco?.semCorridas).toEqual([]);
  });

  it("trocar os partidos troca as decisivas e mantém as corridas", () => {
    const trocadas = CORRIDAS.map((c) => ({ ...c, probD: 1 - c.probD, margem: -c.margem }));
    const a = construirGuia(vistaTeste(CORRIDAS), null, FECHOS);
    const b = construirGuia(vistaTeste(trocadas, { D: 2, R: 1 }), null, FECHOS);
    expect(new Set(ids(b))).toEqual(new Set(ids(a)));
    expect(b.decisivas.map((d) => `${d.camara}-${d.lado}-${d.corrida.id}`).sort()).toEqual(
      a.decisivas.map((d) => `${d.camara}-${d.lado === "D" ? "R" : "D"}-${d.corrida.id}`).sort(),
    );
  });
});
