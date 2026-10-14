import { readFileSync } from "node:fs";
import type {
  PontoSerie,
  VotoAntecipadoAgregado,
  VotoAntecipadoEstado,
} from "@intercalares/contratos";
import { describe, expect, it } from "vitest";
import { construirVistaAgregada } from "./agregado.ts";
import { composicaoEstado } from "./composicao.ts";
import { criteriosQuemVotou } from "./criterios.ts";
import { resumirAgregado, resumirEstado } from "./resumo.ts";
import { construirVista } from "./vista.ts";

const base = JSON.parse(
  readFileSync("test/fixtures/voto-antecipado-sintetico.json", "utf-8"),
) as VotoAntecipadoEstado;

/** O ficheiro sintético só tem totais: acrescentam-se partidos e modalidades no dia do ficheiro. */
function comPartidos(dados: VotoAntecipadoEstado): VotoAntecipadoEstado {
  const extra = [2026, 2022].flatMap((ano) => {
    const total =
      dados.serie.find(
        (p) =>
          p.ano === ano &&
          p.dias_antes === dados.dias_antes &&
          p.faixa === "total" &&
          p.partido === "total" &&
          p.modalidade === "total",
      )?.votos ?? 0;
    const dem = ano === 2026 ? 0.45 : 0.5;
    const correio = ano === 2026 ? 0.6 : 0.8;
    const linha = (
      partido: PontoSerie["partido"],
      modalidade: PontoSerie["modalidade"],
      votos: number,
    ) => ({ ...ponto(ano, partido, modalidade, votos, dados.dias_antes) });
    return [
      linha("dem", "total", total * dem),
      linha("rep", "total", total * 0.3),
      linha("nao_afiliado", "total", total * (0.7 - dem)),
      linha("outro", "total", 0),
      linha("total", "correio", total * correio),
      linha("total", "presencial", total * (1 - correio)),
    ];
  });
  return { ...dados, serie: [...dados.serie, ...extra] };
}

const pa = construirVistaAgregada(
  JSON.parse(
    readFileSync("test/fixtures/pa-agregado-sintetico.json", "utf-8"),
  ) as VotoAntecipadoAgregado,
);

function ponto(
  ano: number,
  partido: PontoSerie["partido"],
  modalidade: PontoSerie["modalidade"],
  votos: number,
  dias_antes = 20,
): PontoSerie {
  return {
    ano,
    dias_antes,
    faixa: "total",
    partido,
    modalidade,
    votos,
    registados: 0,
  };
}

const nc = construirVista(comPartidos(base));

describe("composição por partido e modalidade", () => {
  const serie = [
    ponto(2026, "dem", "total", 450),
    ponto(2026, "rep", "total", 300),
    ponto(2026, "nao_afiliado", "total", 250),
    ponto(2026, "outro", "total", 0),
    ponto(2026, "total", "correio", 600),
    ponto(2026, "total", "presencial", 400),
    ponto(2022, "dem", "total", 500),
    ponto(2022, "rep", "total", 250),
    ponto(2022, "nao_afiliado", "total", 250),
    ponto(2022, "outro", "total", 0),
    ponto(2022, "total", "correio", 800),
    ponto(2022, "total", "presencial", 200),
    // Outro dia do ciclo: não conta.
    ponto(2026, "dem", "total", 9999, 21),
  ];

  it("divide os votos de cada categoria no mesmo dia do ciclo", () => {
    const c = composicaoEstado(serie, 2026, 2022, 20);
    expect(c.partidos.map((p) => p.quota)).toEqual([0.45, 0.3, 0.25, 0]);
    expect(c.partidos.map((p) => p.quotaBase)).toEqual([0.5, 0.25, 0.25, 0]);
    expect(c.modalidades.map((m) => m.quota)).toEqual([0.6, 0.4]);
    expect(c.vantagemDemRep).toBeCloseTo(0.15);
    expect(c.vantagemDemRepBase).toBeCloseTo(0.25);
  });

  it("fica vazia sem votos nesse dia e sem comparação sem ano de referência", () => {
    expect(composicaoEstado(serie, 2026, 2022, 5).partidos).toEqual([]);
    const semBase = composicaoEstado(serie, 2026, null, 20);
    expect(semBase.partidos.every((p) => p.quotaBase === null)).toBe(true);
    expect(semBase.vantagemDemRepBase).toBeNull();
  });
});

describe("quem já votou por critério", () => {
  it("deixa de fora os critérios sem dados", () => {
    expect(criteriosQuemVotou(construirVista(base)).map((b) => b.criterio)).toEqual([
      "historico",
      "idade",
    ]);
  });

  it("põe partido, modalidade, histórico e idade pela mesma ordem, cada um a somar 1", () => {
    const blocos = criteriosQuemVotou(nc);
    expect(blocos.map((b) => b.criterio)).toEqual(["partido", "modalidade", "historico", "idade"]);
    for (const b of blocos) {
      expect(b.linhas.reduce((s, l) => s + l.quota, 0)).toBeCloseTo(1, 5);
    }
    expect(blocos[3]?.linhas.map((l) => l.categoria)).toEqual(["18-29", "30-49", "50-64", "65+"]);
  });

  it("leva a vantagem partidária e o correio ao resumo do estado", () => {
    const r = resumirEstado(nc);
    const partido = criteriosQuemVotou(nc)[0];
    const quota = (c: string) => partido?.linhas.find((l) => l.categoria === c)?.quota ?? NaN;
    expect(r.vantagemDemRep).toBeCloseTo(quota("dem") - quota("rep"), 10);
    expect(r.vantagemDemRep).toBeCloseTo(0.15, 10);
    expect(r.vantagemDemRepBase).toBeCloseTo(0.2, 10);
    expect(r.quotaCorreio).toBeCloseTo(0.6, 10);
  });

  it("não mostra o peso do correio antes de abrir o voto presencial", () => {
    const soCorreio = {
      ...base,
      serie: comPartidos(base).serie.filter((p) => p.modalidade !== "presencial"),
    };
    expect(resumirEstado(construirVista(soCorreio)).quotaCorreio).toBeNull();
  });

  it("não inventa o peso do correio quando a fonte só publica uma modalidade", () => {
    const r = resumirAgregado(pa);
    if (!pa.modalidadesFonte.includes("presencial")) expect(r.quotaCorreio).toBeNull();
  });
});
