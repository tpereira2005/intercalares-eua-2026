import { mkdtempSync, readFileSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";
import type { HistoricoNoite, ProjecaoNoite } from "@intercalares/contratos";
import { describe, expect, it } from "vitest";
import { DadosInvalidos } from "../validacao.ts";
import { lerHistoricoNoite, lerProjecao } from "./carregar.ts";
import { construirVistaNoite } from "./vista.ts";

const PASTA = "test/fixtures/noite";

function projecao(): ProjecaoNoite {
  const p = lerProjecao(`${PASTA}/projecao.json`);
  if (!p) throw new Error("Falta a projeção de teste");
  return p;
}

function historico(): HistoricoNoite {
  const h = lerHistoricoNoite(`${PASTA}/historico.json`);
  if (!h) throw new Error("Falta o histórico de teste");
  return h;
}

describe("lerProjecao", () => {
  it("aceita os ficheiros de exemplo e devolve null sem ficheiro", () => {
    expect(projecao().corridas.length).toBeGreaterThan(0);
    expect(lerProjecao("nao-existe/projecao.json")).toBeNull();
  });

  it("rejeita uma probabilidade fora de [0, 1]", () => {
    const dados = JSON.parse(readFileSync(`${PASTA}/projecao.json`, "utf-8")) as ProjecaoNoite;
    dados.camara.prob_controlo_d = 1.5;
    const caminho = path.join(mkdtempSync(path.join(tmpdir(), "noite-")), "projecao.json");
    writeFileSync(caminho, JSON.stringify(dados));
    expect(() => lerProjecao(caminho)).toThrow(DadosInvalidos);
  });
});

describe("construirVistaNoite", () => {
  it("copia as probabilidades do modelo sem as alterar", () => {
    const p = projecao();
    const v = construirVistaNoite(p, historico());
    expect(v.camara.probD).toBe(p.camara.prob_controlo_d);
    expect(v.senado.probDPrior).toBe(p.senado.prob_controlo_d_prior);
    const primeira = p.corridas[0];
    if (!primeira) throw new Error("Sem corridas");
    expect(v.corridas.get(primeira.id)?.margem).toBe(primeira.margem_projetada);
  });

  it("marca como ensaio um ficheiro reconstruído ou sem previsão congelada", () => {
    const p = projecao();
    expect(
      construirVistaNoite({ ...p, prior_congelado: true, reconstruido: false }, null).ensaio,
    ).toBe(false);
    expect(construirVistaNoite({ ...p, prior_congelado: false }, null).ensaio).toBe(true);
    expect(
      construirVistaNoite({ ...p, prior_congelado: true, reconstruido: true }, null).ensaio,
    ).toBe(true);
  });

  it("usa o histórico só até ao instante da projeção e quando é compatível", () => {
    const p = projecao();
    const h = historico();
    const v = construirVistaNoite(p, h);
    expect(v.evolucao?.camara.length).toBe(h.pontos.length);
    expect(v.evolucao?.camara.at(-1)?.corte).toBe(p.instante);
    const [anterior] = h.pontos;
    expect(
      construirVistaNoite({ ...p, instante: anterior.instante }, h).evolucao?.camara,
    ).toHaveLength(1);
    expect(construirVistaNoite(p, { ...h, reconstruido: !h.reconstruido }).evolucao).toBeNull();
    expect(construirVistaNoite(p, { ...h, ano: 2024 }).evolucao).toBeNull();
  });
});
