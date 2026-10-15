import { describe, expect, it } from "vitest";
import type {
  AlteracoesPrevisao,
  CenariosPrevisao,
  PrevisaoCongresso,
} from "@intercalares/contratos";
import {
  cenariosBatemCerto,
  cenarioPublicado,
  construirAlteracoes,
  construirVistaCenarios,
  obterCenario,
  viragem,
} from "./explorador.ts";

function resumo(probD: number) {
  return {
    prob_controlo_d: probD,
    prob_controlo_r: 1 - probD,
    lugares_d_mediana: 200,
    lugares_d_p10: 190,
    lugares_d_p90: 210,
  };
}

/** Grelha pequena: a Câmara vira com 2 pontos a favor dos republicanos; o Senado nunca. */
function grelha(): CenariosPrevisao {
  const desvios = [-4, -2, 0, 2];
  const fatores = [1, 0.5];
  return {
    metadados: { versao_esquema: "0.1.0", gerado_em: "2026-10-14T00:00:00Z", fontes: [] },
    ano: 2026,
    corte: "2026-10-14",
    congelada: false,
    simulacoes: 1000,
    semente: 1,
    ambiente_base: 3,
    desvio_padrao_ambiente: 3,
    desvios_ambiente: desvios,
    fatores_erro_sondagens: fatores,
    cenarios: fatores.flatMap((f) =>
      desvios.map((d) => ({
        desvio_ambiente: d,
        ambiente: 3 + d,
        fator_erro_sondagens: f,
        camara: resumo(d <= -2 ? 0.4 : 0.7),
        senado: resumo(0.2),
        corridas_senado: [{ id: "OH-S-especial", prob_d: 0.5 + d / 10 }],
      })),
    ),
    codigo_commit: "abc1234",
  } as unknown as CenariosPrevisao;
}

describe("cenários", () => {
  it("ordena a grelha e encontra cada cenário", () => {
    const vista = construirVistaCenarios(grelha());
    expect(vista.fatores).toEqual([0.5, 1]);
    expect(vista.commit).toBe("abc1234");
    expect(obterCenario(vista, 2, 1)?.corridasSenado["OH-S-especial"]).toBeCloseTo(0.7);
    expect(obterCenario(vista, 3, 1)).toBeNull();
    expect(cenarioPublicado(vista)?.ambiente).toBe(3);
  });

  it("dá a deslocação mais pequena que muda o favorito", () => {
    const vista = construirVistaCenarios(grelha());
    expect(viragem(vista, "camara", 1)).toBe(-2);
    expect(viragem(vista, "senado", 1)).toBeNull();
  });
});

describe("registo de alterações", () => {
  it("põe a mais recente primeiro, mantendo a ordem no mesmo dia", () => {
    const alteracao = (data: string, pr: number) => ({
      data,
      descricao: `PR ${String(pr)}`,
      pr_url: `https://github.com/x/y/pull/${String(pr)}`,
      camara: { antes: null, depois: 0.9 },
      senado: { antes: 0.7, depois: 0.72 },
    });
    const dados = {
      metadados: { versao_esquema: "0.1.0", gerado_em: "2026-10-14T00:00:00Z", fontes: [] },
      ano: 2026,
      alteracoes: [
        alteracao("2026-10-13", 11),
        alteracao("2026-10-13", 16),
        alteracao("2026-10-14", 43),
      ],
    } as unknown as AlteracoesPrevisao;
    expect(construirAlteracoes(dados).lista.map((a) => a.descricao)).toEqual([
      "PR 43",
      "PR 16",
      "PR 11",
    ]);
  });
});

describe("cenários face à previsão publicada", () => {
  const previsao = {
    ano: 2026,
    corte: "2026-10-14",
    codigo_commit: "abc1234",
    ambiente: { margem: 3 },
    camara: { prob_controlo_d: 0.7 },
    senado: { prob_controlo_d: 0.2 },
  } as unknown as PrevisaoCongresso;

  it("aceita a grelha cujo cenário central dá a previsão publicada", () => {
    expect(cenariosBatemCerto(grelha(), previsao)).toBe(true);
  });

  it("recusa a grelha de outra corrida do modelo", () => {
    const outra = { ...previsao, senado: { prob_controlo_d: 0.25 } } as PrevisaoCongresso;
    expect(cenariosBatemCerto(grelha(), outra)).toBe(false);
    expect(cenariosBatemCerto(grelha(), { ...previsao, codigo_commit: "def5678" })).toBe(false);
    expect(cenariosBatemCerto(grelha(), { ...previsao, corte: "2026-10-15" })).toBe(false);
  });
});
