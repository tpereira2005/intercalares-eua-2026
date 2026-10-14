import { readFileSync } from "node:fs";
import type { ChamadasRedacoes, ResultadosParciais } from "@intercalares/contratos";
import { describe, expect, it } from "vitest";
import { construirChamadas } from "./chamadas.ts";
import { ChamadaInvalida, registarChamada, type PedidoChamada } from "./registo-chamada.ts";
import { construirVistaResultados } from "./vista.ts";

const CORRIDAS = new Set(["NC-01", "PA-07", "OH-S-especial"]);
const AGORA = new Date("2026-11-04T03:00:00Z");

function pedido(extra: Partial<PedidoChamada> = {}): PedidoChamada {
  return {
    corrida: "pa-07",
    vencedor: "R",
    redacao: "Associated Press",
    url: "https://apnews.com/projects/election-results-2026/",
    hora: "2026-11-04T02:50:00Z",
    candidato: "",
    retirar: false,
    ...extra,
  };
}

describe("registarChamada", () => {
  it("acrescenta, substitui e retira uma chamada por corrida", () => {
    const primeira = registarChamada(null, pedido(), CORRIDAS, 2026, AGORA);
    expect(primeira.chamadas).toEqual([
      expect.objectContaining({ corrida: "PA-07", vencedor: "R", candidato: null }),
    ]);
    const corrigida = registarChamada(primeira, pedido({ vencedor: "D" }), CORRIDAS, 2026, AGORA);
    expect(corrigida.chamadas.map((c) => c.vencedor)).toEqual(["D"]);
    const retirada = registarChamada(corrigida, pedido({ retirar: true }), CORRIDAS, 2026, AGORA);
    expect(retirada.chamadas).toEqual([]);
  });

  it("usa a hora do registo sem hora e recusa corridas, lados e horas inválidos", () => {
    const sem = registarChamada(null, pedido({ hora: "" }), CORRIDAS, 2026, AGORA);
    expect(sem.chamadas[0]?.hora).toBe("2026-11-04T03:00:00.000Z");
    expect(() =>
      registarChamada(null, pedido({ corrida: "PA-99" }), CORRIDAS, 2026, AGORA),
    ).toThrow(ChamadaInvalida);
    expect(() => registarChamada(null, pedido({ vencedor: "X" }), CORRIDAS, 2026, AGORA)).toThrow(
      ChamadaInvalida,
    );
    expect(() =>
      registarChamada(null, pedido({ hora: "2026-11-04 02:50" }), CORRIDAS, 2026, AGORA),
    ).toThrow(ChamadaInvalida);
    expect(() => registarChamada(null, pedido({ url: "apnews" }), CORRIDAS, 2026, AGORA)).toThrow(
      ChamadaInvalida,
    );
  });
});

describe("chamadas na vista da noite", () => {
  it("junta a chamada à corrida e ignora chamadas de outro ano", () => {
    const parciais = JSON.parse(
      readFileSync("test/fixtures/resultados/parciais.json", "utf-8"),
    ) as ResultadosParciais;
    const chamadas = JSON.parse(
      readFileSync("test/fixtures/resultados/chamadas.json", "utf-8"),
    ) as ChamadasRedacoes;
    const vista = construirVistaResultados(parciais, null, null, chamadas);
    expect(vista.aoVivo.find((l) => l.id === "NC-01")?.chamada?.vencedor).toBe("D");
    expect(vista.chamadas).toHaveLength(1);
    expect(construirChamadas({ ...chamadas, ano: 2024 }, 2026)).toEqual([]);
  });
});
