import { readFileSync } from "node:fs";
import type { HistoricoPrevisao, PrevisaoCongresso } from "@intercalares/contratos";
import { describe, expect, it } from "vitest";
import {
  Q90_T5_UNITARIO,
  aparar,
  categoria,
  construirEvolucao,
  construirVistaPrevisao,
} from "./vista.ts";

const dados = JSON.parse(
  readFileSync("test/fixtures/previsao/2026.json", "utf-8"),
) as PrevisaoCongresso;
const historico = JSON.parse(
  readFileSync("test/fixtures/previsao/historico-2026.json", "utf-8"),
) as HistoricoPrevisao;

describe("categoria", () => {
  it("é simétrica entre os dois lados", () => {
    for (const p of [0.97, 0.85, 0.7, 0.55]) {
      const d = categoria(p);
      const r = categoria(1 - p);
      expect(d.endsWith("D") || d === "renhida").toBe(true);
      expect(r.replace(/R$/, "D")).toBe(d);
    }
    expect(categoria(0.5)).toBe("renhida");
  });

  it("usa os limites de 95%, 80% e 60%", () => {
    expect(categoria(0.95)).toBe("solidaD");
    expect(categoria(0.05)).toBe("solidaR");
    expect(categoria(0.8)).toBe("provavelD");
    expect(categoria(0.2)).toBe("provavelR");
    expect(categoria(0.6)).toBe("renhida");
    expect(categoria(0.61)).toBe("inclinadaD");
  });
});

describe("aparar", () => {
  it("preenche buracos e corta as caudas", () => {
    const pontos = aparar([
      { lugares: 10, probabilidade: 0.0004 },
      { lugares: 12, probabilidade: 0.5 },
      { lugares: 14, probabilidade: 0.4996 },
      { lugares: 20, probabilidade: 0 },
    ]);
    expect(pontos.map((p) => p.lugares)).toEqual([12, 13, 14]);
    expect(pontos[1]?.probabilidade).toBe(0);
  });

  it("devolve uma lista vazia sem pontos", () => {
    expect(aparar([])).toEqual([]);
  });
});

describe("construirVistaPrevisao", () => {
  const vista = construirVistaPrevisao(dados);

  it("lê o controlo e os lugares de cada câmara", () => {
    expect(vista.camara.probD).toBe(dados.camara.prob_controlo_d);
    expect(vista.camara.favorito).toBe("D");
    expect(vista.senado.maioria).toBe(51);
    expect(vista.senado.foraDeJogo).toEqual({ D: 34, R: 31 });
    const soma = vista.camara.distribuicao.reduce((s, p) => s + p.probabilidade, 0);
    expect(soma).toBeGreaterThan(0.995);
  });

  it("dá ao ambiente o intervalo de 80% da t de Student usada no modelo", () => {
    expect(Q90_T5_UNITARIO).toBeCloseTo(1.1432, 3);
    const { margem, desvio, p10, p90 } = vista.ambiente;
    expect(p90 - margem).toBeCloseTo(margem - p10, 9);
    expect(p90 - p10).toBeCloseTo(2 * Q90_T5_UNITARIO * desvio, 9);
  });

  it("separa as câmaras e ordena da corrida mais renhida para a menos", () => {
    expect(vista.corridasSenado.map((c) => c.id)).toEqual([
      "IA-S",
      "TX-S",
      "FL-S-especial",
      "WY-S",
    ]);
    expect(vista.corridasCamara[0]?.id).toBe("PA-07");
    expect(vista.corridasCamara.every((c) => c.camara === "camara")).toBe(true);
  });

  it("lê distritos e eleições especiais a partir do identificador", () => {
    const fl = vista.corridasSenado.find((c) => c.id === "FL-S-especial");
    expect(fl?.especial).toBe(true);
    expect(fl?.distrito).toBeNull();
    expect(vista.corridasCamara.find((c) => c.id === "AK-00")?.distrito).toBe(0);
    expect(vista.corridasCamara.find((c) => c.id === "NC-01")?.distrito).toBe(1);
  });

  it("conta as corridas por categoria", () => {
    const total = Object.values(vista.categorias.camara).reduce((s, n) => s + n, 0);
    expect(total).toBe(vista.corridasCamara.length);
    expect(vista.categorias.senado.solidaR).toBe(1);
  });

  it("ordena os backtests do mais recente para o mais antigo, Câmara primeiro", () => {
    expect(vista.backtests.map((b) => `${String(b.ano)}-${b.camara}`).slice(0, 2)).toEqual([
      "2024-camara",
      "2024-senado",
    ]);
  });
});

describe("construirEvolucao", () => {
  it("segue a ordem cronológica e escolhe a entrada de há uma semana", () => {
    const evolucao = construirEvolucao(historico, "2026-10-13");
    expect(evolucao.cortes).toEqual(["2026-09-29", "2026-10-06", "2026-10-13"]);
    expect(evolucao.semanaAnterior?.corte).toBe("2026-10-06");
    expect(evolucao.semanaAnterior?.probD.get("TX-S")).toBe(0.7101);
    expect(evolucao.senado.at(-1)?.probD).toBe(historico.dias.at(-1)?.senado.prob_controlo_d);
  });

  it("ignora entradas posteriores ao corte mostrado", () => {
    const evolucao = construirEvolucao(historico, "2026-10-06");
    expect(evolucao.cortes.at(-1)).toBe("2026-10-06");
    expect(evolucao.semanaAnterior?.corte).toBe("2026-09-29");
  });

  it("não tem semana anterior com menos de sete dias de histórico", () => {
    expect(construirEvolucao(historico, "2026-09-29").semanaAnterior).toBeNull();
  });
});
