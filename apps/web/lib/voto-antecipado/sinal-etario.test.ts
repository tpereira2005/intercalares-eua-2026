import { mkdtempSync, writeFileSync, readFileSync } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";
import { describe, expect, it } from "vitest";
import { DadosInvalidos } from "../validacao.ts";
import { carregarIdade } from "./idade.ts";

const PASTA = "test/fixtures/idade";

describe("sinal etário", () => {
  it("lê o ficheiro e soma as quotas de cada faixa pela ordem canónica", () => {
    const vista = carregarIdade("NC", PASTA);
    expect(vista).toBeTruthy();
    if (!vista) return;
    expect(vista.faixas.map((f) => f.faixa)).toEqual([
      "18-24",
      "25-29",
      "30-39",
      "40-49",
      "50-64",
      "65-74",
      "75+",
    ]);
    const total = vista.faixas.reduce((s, f) => s + f.quotaProjetada, 0);
    expect(total).toBeCloseTo(1, 2);
    expect(vista.faixas[0]?.partidos.map((p) => p.partido)).toEqual(["dem", "rep", "nao_afiliado"]);
    expect(vista.backtests.map((b) => b.ano)).toEqual([2022, 2018]);
  });

  it("distingue um estado sem modelo de um ficheiro ainda por publicar", () => {
    expect(carregarIdade("GA", PASTA)).toBeUndefined();
    expect(carregarIdade("NC", mkdtempSync(path.join(tmpdir(), "idade-")))).toBeNull();
  });

  it("rejeita um ficheiro com peso na previsão", () => {
    const pasta = mkdtempSync(path.join(tmpdir(), "idade-"));
    const dados = JSON.parse(readFileSync(`${PASTA}/nc.json`, "utf-8")) as Record<string, unknown>;
    writeFileSync(path.join(pasta, "nc.json"), JSON.stringify({ ...dados, peso_previsao: 1 }));
    expect(() => carregarIdade("NC", pasta)).toThrow(DadosInvalidos);
  });
});
