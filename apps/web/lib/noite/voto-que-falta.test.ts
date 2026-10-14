import { describe, expect, it } from "vitest";
import type { ContagemCorrida, LinhaResultados } from "../resultados/vista.ts";
import { contarCorridas } from "../resultados/vista.ts";
import { corridasComFalta, votoQueFalta } from "./falta.ts";
import type { CorridaNoite } from "./vista.ts";

function contagem(d: number, r: number, porModo: ContagemCorrida["porModo"] = []) {
  return {
    id: "NC-01",
    estado: "NC",
    votosD: d,
    votosR: r,
    votosOutros: 0,
    total: d + r,
    margem: d + r > 0 ? (d - r) / (d + r) : null,
    seccoes: null,
    soTotal: false,
    atualizadoEm: null,
    porModo,
  } satisfies ContagemCorrida;
}

function projecao(esperados: number | null, decidida = false): CorridaNoite {
  return {
    id: "NC-01",
    camara: "camara",
    probD: 0.6,
    probDPrior: 0.55,
    margem: 2,
    margemPrior: 1,
    margemP10: -3,
    margemP90: 7,
    margemContada: 10,
    fracaoContada: 0.5,
    votosContados: 1000,
    votosEsperados: esperados,
    decidida,
    evolucao: [],
  };
}

function linha(c: ContagemCorrida | null, p: CorridaNoite | null): LinhaResultados {
  return {
    id: "NC-01",
    estado: "NC",
    senado: false,
    contagem: c,
    previsao: null,
    projecao: p,
    chamada: null,
  };
}

describe("votoQueFalta", () => {
  it("calcula o que falta, as modalidades e a margem necessária", () => {
    const c = contagem(550, 450, [
      { modo: "correio", votosD: 300, votosR: 100, votosOutros: 0, total: 400 },
      { modo: "dia_eleicao", votosD: 200, votosR: 300, votosOutros: 0, total: 500 },
    ]);
    const v = votoQueFalta(linha(c, projecao(2000)));
    expect(v).not.toBeNull();
    expect(v?.falta).toBe(1000);
    expect(v?.fracaoContada).toBe(0.5);
    expect(v?.semModo).toBe(100);
    expect(v?.modos.map((m) => [m.modo, m.fracao, m.margem])).toEqual([
      ["correio", 0.2, 50],
      ["dia_eleicao", 0.25, -20],
    ]);
    expect(v?.lider).toBe("D");
    // Vantagem de 100 votos em 1000 por contar: R precisa de 10 pontos.
    expect(v?.precisa).toBeCloseTo(10);
    expect(v?.margemContada).toBeCloseTo(10);
  });

  it("nunca põe o esperado abaixo do contado", () => {
    const v = votoQueFalta(linha(contagem(700, 600), projecao(1000)));
    expect(v?.esperados).toBe(1300);
    expect(v?.falta).toBe(0);
    expect(v?.precisa).toBeNull();
  });

  it("deixa de fora corridas decididas, sem voto esperado ou sem contagem", () => {
    const c = contagem(10, 5);
    expect(votoQueFalta(linha(c, projecao(100, true)))).toBeNull();
    expect(votoQueFalta(linha(c, projecao(null)))).toBeNull();
    expect(votoQueFalta(linha(null, projecao(100)))).toBeNull();
    expect(votoQueFalta(linha(contagem(0, 0), projecao(100)))).toBeNull();
    expect(corridasComFalta([linha(c, projecao(100)), linha(c, null)])).toHaveLength(1);
  });
});

describe("contarCorridas por modalidade", () => {
  it("soma as modalidades das unidades pela ordem de chegada habitual", () => {
    const [corrida] = contarCorridas({
      metadados: { versao_esquema: "0.1.0", gerado_em: "2026-11-04T02:00:00Z", fontes: [] },
      ano: 2026,
      instante: "2026-11-04T02:00:00Z",
      reconstruido: false,
      cobertura_parcial: [],
      unidades: [
        {
          corrida: "NC-01",
          unidade: "37001",
          votos_d: 30,
          votos_r: 20,
          votos_outros: 0,
          por_modo: [
            { modo: "dia_eleicao", votos_d: 10, votos_r: 15, votos_outros: 0 },
            { modo: "correio", votos_d: 20, votos_r: 5, votos_outros: 0 },
          ],
          percentagem_contada: null,
          seccoes_reportadas: null,
          seccoes_totais: null,
          atualizado_em: null,
        },
        {
          corrida: "NC-01",
          unidade: "37183",
          votos_d: 5,
          votos_r: 5,
          votos_outros: 0,
          por_modo: [{ modo: "correio", votos_d: 5, votos_r: 5, votos_outros: 0 }],
          percentagem_contada: null,
          seccoes_reportadas: null,
          seccoes_totais: null,
          atualizado_em: null,
        },
      ],
    } as never);
    expect(corrida?.porModo).toEqual([
      { modo: "correio", votosD: 25, votosR: 10, votosOutros: 0, total: 35 },
      { modo: "dia_eleicao", votosD: 10, votosR: 15, votosOutros: 0, total: 25 },
    ]);
  });
});
