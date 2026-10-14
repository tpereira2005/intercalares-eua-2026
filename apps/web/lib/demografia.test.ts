import { readFileSync } from "node:fs";
import type { VotoAntecipadoAgregado, VotoAntecipadoEstado } from "@intercalares/contratos";
import { describe, expect, it } from "vitest";
import { demografiaAgregada, demografiaIndividual, juntarMomento } from "./demografia.ts";
import { construirVistaAgregada } from "./voto-antecipado/agregado.ts";
import { construirVista } from "./voto-antecipado/vista.ts";

const nc = construirVista(
  JSON.parse(
    readFileSync("test/fixtures/voto-antecipado-sintetico.json", "utf-8"),
  ) as VotoAntecipadoEstado,
);
const pa = construirVistaAgregada(
  JSON.parse(
    readFileSync("test/fixtures/pa-agregado-sintetico.json", "utf-8"),
  ) as VotoAntecipadoAgregado,
);

describe("demografia entre estados", () => {
  it("soma as quotas das faixas de cada grupo", () => {
    const e = demografiaIndividual(nc);
    const faixas = nc.comparacoes[0]?.faixas ?? [];
    const quota = (lista: string[]) =>
      faixas.filter((f) => lista.includes(f.faixa)).reduce((s, f) => s + f.quota, 0);
    expect(e.composicao.mais65?.quota).toBeCloseTo(quota(["65-74", "75+"]), 12);
    expect(e.composicao.jovens?.quota).toBeCloseTo(quota(["18-24", "25-29"]), 12);
    expect(e.anoBase).toBe(2022);
  });

  it("calcula o desvio do grupo como observados sobre esperados", () => {
    const e = demografiaIndividual(nc);
    const faixas = (nc.comparacoes[0]?.faixas ?? []).filter((f) =>
      ["65-74", "75+"].includes(f.faixa),
    );
    const esperado = faixas.reduce((s, f) => s + f.esperado, 0);
    const votos = faixas.reduce((s, f) => s + f.votos, 0);
    expect(e.desvio.mais65).toBeCloseTo(votos / esperado - 1, 12);
  });

  it("junta o momento pesado pelos votos de cada faixa", () => {
    const m = juntarMomento(
      [
        { faixa: "65-74", habituais: 0.6, antecipacao: 0.1, novos: 0.3, votos: 100 },
        { faixa: "75+", habituais: 0.9, antecipacao: 0.1, novos: 0, votos: 300 },
        { faixa: "18-24", habituais: 0, antecipacao: 0, novos: 1, votos: 999 },
      ],
      ["65-74", "75+"],
    );
    expect(m?.habituais).toBeCloseTo(0.825);
    expect(m?.novos).toBeCloseTo(0.075);
    expect(juntarMomento([], "todos")).toBeNull();
  });

  it("nos estados agregados não há participação nem momento", () => {
    const e = demografiaAgregada(pa);
    expect(e.qualidade).toBe("parcial");
    expect(e.desvio.mais65).toBeNull();
    expect(e.momento).toBeNull();
    expect(e.composicao.mais65).not.toBeNull();
  });
});
