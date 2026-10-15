import { readFileSync } from "node:fs";
import type { PrevisaoCongresso, SensibilidadePrevisao } from "@intercalares/contratos";
import { describe, expect, it } from "vitest";
import { lerPrevisao, lerSensibilidade } from "./carregar.ts";
import { construirVistaSensibilidade, sensibilidadeBateCerto } from "./sensibilidade.ts";

const FICHEIRO = "test/fixtures/previsao/sensibilidade-2026.json";

function previsao(): PrevisaoCongresso {
  const dados = lerPrevisao("test/fixtures/previsao/2026.json");
  if (!dados) throw new Error("Falta a previsão de teste");
  return dados;
}

function exemplo(): SensibilidadePrevisao {
  return JSON.parse(readFileSync(FICHEIRO, "utf-8")) as SensibilidadePrevisao;
}

describe("lerSensibilidade", () => {
  it("aceita o ficheiro de exemplo e devolve null sem ficheiro", () => {
    expect(lerSensibilidade(FICHEIRO)?.variantes.length).toBeGreaterThan(1);
    expect(lerSensibilidade("nao-existe.json")).toBeNull();
  });
});

describe("sensibilidadeBateCerto", () => {
  it("aceita a sensibilidade calculada sobre a previsão publicada", () => {
    expect(sensibilidadeBateCerto(exemplo(), previsao())).toBe(true);
  });

  it("recusa outro corte, outro commit ou uma primeira variante diferente", () => {
    expect(sensibilidadeBateCerto({ ...exemplo(), corte: "2026-10-12" }, previsao())).toBe(false);
    expect(sensibilidadeBateCerto({ ...exemplo(), codigo_commit: "abc" }, previsao())).toBe(false);
    const outra = exemplo();
    outra.variantes[0].senado.prob_controlo_d += 0.01;
    expect(sensibilidadeBateCerto(outra, previsao())).toBe(false);
  });
});

describe("construirVistaSensibilidade", () => {
  it("separa o modelo publicado e mede as outras variantes face a ele", () => {
    const dados = exemplo();
    const vista = construirVistaSensibilidade(dados);
    expect(vista.publicada.nome).toBe(dados.variantes[0].nome);
    expect(vista.publicada.camara.variacao).toBe(0);
    expect(vista.variantes).toHaveLength(dados.variantes.length - 1);
    const [primeira] = vista.variantes;
    const original = dados.variantes[1];
    if (!primeira || !original) throw new Error("Exemplo sem variantes");
    expect(primeira.senado.variacao).toBeCloseTo(
      original.senado.prob_controlo_d - dados.variantes[0].senado.prob_controlo_d,
    );
    expect(primeira.camara.lugaresMediana).toBe(original.camara.lugares_d_mediana);
  });
});
