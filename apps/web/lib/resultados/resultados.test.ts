import { mkdtempSync, readFileSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";
import type { ResultadosParciais } from "@intercalares/contratos";
import { describe, expect, it } from "vitest";
import { lerProjecao } from "../noite/carregar.ts";
import { construirVistaNoite } from "../noite/vista.ts";
import { lerPrevisao } from "../previsao/carregar.ts";
import { construirVistaPrevisao } from "../previsao/vista.ts";
import { DadosInvalidos } from "../validacao.ts";
import { lerParciais } from "./carregar.ts";
import { construirVistaResultados, contarCorridas, previsaoParaResultados } from "./vista.ts";

const PARCIAIS = "test/fixtures/resultados/parciais.json";

function exemplo(): ResultadosParciais {
  return JSON.parse(readFileSync(PARCIAIS, "utf-8")) as ResultadosParciais;
}

function previsao() {
  const dados = lerPrevisao("test/fixtures/previsao/2026.json");
  if (!dados) throw new Error("Falta a previsão de teste");
  return construirVistaPrevisao(dados);
}

function gravar(dados: unknown): string {
  const caminho = path.join(mkdtempSync(path.join(tmpdir(), "resultados-")), "parciais.json");
  writeFileSync(caminho, JSON.stringify(dados));
  return caminho;
}

describe("lerParciais", () => {
  it("aceita um ficheiro que cumpre o contrato", () => {
    expect(lerParciais(PARCIAIS)?.unidades).toHaveLength(4);
  });

  it("devolve null quando o ficheiro não existe", () => {
    expect(lerParciais("nao-existe/parciais.json")).toBeNull();
  });

  it("rejeita votos negativos", () => {
    const dados = exemplo();
    const primeira = dados.unidades[0];
    if (!primeira) throw new Error("Exemplo vazio");
    primeira.votos_d = -1;
    expect(() => lerParciais(gravar(dados))).toThrow(DadosInvalidos);
  });
});

describe("contarCorridas", () => {
  it("soma as unidades de cada corrida e calcula a margem contada", () => {
    const nc = contarCorridas(exemplo()).find((c) => c.id === "NC-01");
    expect(nc).toMatchObject({
      estado: "NC",
      votosD: 2000,
      votosR: 2500,
      votosOutros: 100,
      total: 4600,
      seccoes: { reportadas: 15, totais: 50 },
      soTotal: false,
      atualizadoEm: "2026-11-04T02:25:00Z",
    });
    expect(nc?.margem).toBeCloseTo(-500 / 4600);
  });

  it("não inventa o apuramento quando a fonte não dá secções", () => {
    const ia = contarCorridas(exemplo()).find((c) => c.id === "IA-S");
    expect(ia?.seccoes).toBeNull();
    expect(ia?.atualizadoEm).toBeNull();
  });

  it("sem votos, a margem fica por calcular", () => {
    const ga = contarCorridas(exemplo()).find((c) => c.id === "GA-S");
    expect(ga?.margem).toBeNull();
    expect(ga?.soTotal).toBe(true);
    expect(ga?.seccoes).toEqual({ reportadas: 0, totais: 159 });
  });

  it("trocar os rótulos dos partidos troca a margem e nada mais", () => {
    const original = exemplo();
    const trocado: ResultadosParciais = {
      ...original,
      unidades: original.unidades.map((u) => ({ ...u, votos_d: u.votos_r, votos_r: u.votos_d })),
    };
    const a = contarCorridas(original);
    const b = contarCorridas(trocado);
    for (const [i, c] of a.entries()) {
      const d = b[i];
      expect(d?.total).toBe(c.total);
      expect(d?.seccoes).toEqual(c.seccoes);
      expect(d?.margem ?? 0).toBeCloseTo(-(c.margem ?? 0));
    }
  });
});

describe("construirVistaResultados", () => {
  it("põe o Senado primeiro e liga cada corrida à previsão congelada", () => {
    const vista = construirVistaResultados(exemplo(), previsao());
    expect(vista.ensaio).toBe(false);
    expect(vista.aoVivo.map((l) => l.id)).toEqual(["IA-S", "GA-S", "NC-01"]);
    expect(vista.aoVivo.find((l) => l.id === "IA-S")?.previsao?.probD).toBeCloseTo(0.55, 2);
    expect(vista.aoVivo.find((l) => l.id === "GA-S")?.previsao).toBeNull();
  });

  it("lista sem dados ao vivo o Senado e os distritos não sólidos que faltam", () => {
    const vista = construirVistaResultados(exemplo(), previsao());
    const ids = vista.semDados.map((l) => l.id);
    expect(ids).toContain("TX-S");
    expect(ids).toContain("PA-07");
    expect(ids).not.toContain("IA-S");
    expect(ids).not.toContain("NC-01");
    // Distritos sólidos (probabilidade acima de 95% para um lado) ficam de fora.
    expect(ids).not.toContain("CA-11");
    expect(vista.semDados.every((l) => l.contagem === null)).toBe(true);
  });

  it("resume a cobertura por estado", () => {
    const vista = construirVistaResultados(exemplo(), previsao());
    expect(vista.cobertura.map((c) => [c.estado, c.corridas])).toEqual([
      ["NC", 1],
      ["FL", 0],
      ["GA", 1],
      ["AK", 0],
      ["TX", 0],
      ["VA", 0],
      ["NE", 0],
      ["AZ", 0],
      ["CA", 0],
      ["IA", 1],
    ]);
    expect(vista.cobertura.find((c) => c.estado === "GA")?.soTotal).toBe(true);
    expect(vista.cobertura.find((c) => c.estado === "NE")?.soTotal).toBe(true);
    expect(vista.cobertura.find((c) => c.estado === "VA")?.soTotal).toBe(false);
    expect(vista.cobertura.find((c) => c.estado === "AZ")?.parcial).toBe(true);
    expect(vista.cobertura.find((c) => c.estado === "CA")?.soTotal).toBe(true);
    expect(vista.cobertura.find((c) => c.estado === "TX")?.parcial).toBe(true);
  });

  it("mostra a nota da fonte sobre os estados com só alguns condados", () => {
    const nota = "Só o condado de Harris.";
    const vista = construirVistaResultados(
      { ...exemplo(), cobertura_parcial: [{ estado: "TX", condados: ["48201"], nota }] },
      previsao(),
    );
    expect(vista.cobertura.find((c) => c.estado === "TX")?.nota).toBe(nota);
  });

  it("a previsão reduzida para o browser dá a mesma vista que a completa", () => {
    // Um distrito sólido num estado sem contagem ao vivo: é o que a redução deixa cair.
    const base = previsao();
    const solido = base.corridasCamara.find((c) => c.id === "CA-11");
    if (!solido) throw new Error("falta CA-11 no ficheiro de exemplo");
    const completa = {
      ...base,
      corridasCamara: [...base.corridasCamara, { ...solido, id: "WY-00", estado: "WY" as const }],
    };
    const reduzida = previsaoParaResultados(completa);
    expect(reduzida.corridasCamara.map((c) => c.id)).not.toContain("WY-00");
    expect(reduzida.corridasCamara.length).toBeLessThan(completa.corridasCamara.length);
    expect(construirVistaResultados(exemplo(), reduzida)).toEqual(
      construirVistaResultados(exemplo(), completa),
    );
  });

  it("um ensaio reconstruído não se cruza com a previsão de 2026", () => {
    const vista = construirVistaResultados({ ...exemplo(), reconstruido: true }, previsao());
    expect(vista.ensaio).toBe(true);
    expect(vista.aoVivo.every((l) => l.previsao === null)).toBe(true);
  });

  it("um ficheiro de outro ano é tratado como ensaio", () => {
    const vista = construirVistaResultados({ ...exemplo(), ano: 2022 }, previsao());
    expect(vista.ensaio).toBe(true);
  });

  it("junta a projeção do mesmo ano a cada corrida, e nunca a de um ensaio", () => {
    const projecao = lerProjecao("test/fixtures/noite/projecao.json");
    if (!projecao) throw new Error("Falta a projeção de teste");
    const noite = construirVistaNoite(projecao, null);
    const vista = construirVistaResultados(exemplo(), previsao(), noite);
    expect(vista.aoVivo.find((l) => l.id === "IA-S")?.projecao?.probD).toBe(
      noite.corridas.get("IA-S")?.probD,
    );
    expect(vista.semDados.find((l) => l.id === "TX-S")?.projecao).not.toBeNull();
    const outroAno = construirVistaResultados(exemplo(), previsao(), { ...noite, ano: 2024 });
    expect(outroAno.aoVivo.every((l) => l.projecao === null)).toBe(true);
  });

  it("funciona sem previsão", () => {
    const vista = construirVistaResultados(exemplo(), null);
    expect(vista.aoVivo).toHaveLength(3);
    expect(vista.semDados).toEqual([]);
    expect(vista.previsaoCongelada).toBeNull();
  });
});
