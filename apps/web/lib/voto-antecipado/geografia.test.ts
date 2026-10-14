import type {
  LinhaGeografia,
  LinhaGeografiaAgregada,
  LinhaHistoricoGeografia,
} from "@intercalares/contratos";
import { describe, expect, it } from "vitest";
import {
  agruparGeografia,
  juntarHistorico,
  linhasPorFaixa,
  linhasUnidades,
  MINIMO_VOTOS_UNIDADE,
} from "./geografia.ts";

function linha(
  ano: number,
  codigo: string,
  faixa: LinhaGeografia["faixa"],
  votos: number,
  registados: number,
  nivel: LinhaGeografia["nivel"] = "condado",
): LinhaGeografia {
  return { ano, nivel, codigo, nome: `Unidade ${codigo}`, faixa, votos, registados };
}

const LINHAS: LinhaGeografia[] = [
  // Condado A: os 65+ pesam 50% em 2026 e 40% em 2022.
  linha(2026, "37001", "total", 400, 4000),
  linha(2026, "37001", "65+", 200, 1000),
  linha(2026, "37001", "18-29", 40, 800),
  linha(2022, "37001", "total", 500, 3800),
  linha(2022, "37001", "65+", 200, 900),
  // Condado B: poucos votos em 2026.
  linha(2026, "37003", "total", MINIMO_VOTOS_UNIDADE - 1, 1000),
  linha(2026, "37003", "65+", 60, 300),
  linha(2022, "37003", "total", 300, 1000),
  linha(2022, "37003", "65+", 60, 300),
  // Distritos, para confirmar a separação por nível.
  linha(2026, "2", "total", 1000, 9000, "distrito"),
  linha(2026, "10", "total", 1000, 9000, "distrito"),
  linha(2026, "1", "desconhecida", 5, 0, "distrito"),
];

describe("agruparGeografia", () => {
  it("agrupa por unidade e ano, distritos primeiro e por número", () => {
    const unidades = agruparGeografia(LINHAS);
    expect(unidades.map((u) => `${u.nivel}:${u.codigo}`)).toEqual([
      "distrito:1",
      "distrito:2",
      "distrito:10",
      "condado:37001",
      "condado:37003",
    ]);
    const a = unidades.find((u) => u.codigo === "37001");
    expect(a?.anos.map((x) => x.ano)).toEqual([2026, 2022]);
    expect(a?.anos[0]?.votos).toEqual([40, 0, 0, 200]);
  });
});

describe("linhasUnidades", () => {
  const unidades = agruparGeografia(LINHAS);

  it("calcula quota, diferença e participação da faixa", () => {
    const [a] = linhasUnidades(unidades, "condado", "65+", 2026, 2022);
    expect(a?.codigo).toBe("37001");
    expect(a?.quota).toBeCloseTo(0.5);
    expect(a?.quotaBase).toBeCloseTo(0.4);
    expect(a?.diferenca).toBeCloseTo(0.1);
    expect(a?.taxa).toBeCloseTo(0.2);
    expect(a?.taxaBase).toBeCloseTo(200 / 900);
    expect(a?.poucosVotos).toBe(false);
  });

  it("marca e põe no fim as unidades com poucos votos", () => {
    const linhas = linhasUnidades(unidades, "condado", "65+", 2026, 2022);
    expect(linhas.map((l) => l.codigo)).toEqual(["37001", "37003"]);
    expect(linhas[1]?.poucosVotos).toBe(true);
  });

  it("sem o ano de comparação, não inventa a diferença", () => {
    const [a] = linhasUnidades(unidades, "condado", "65+", 2026, 2018);
    expect(a?.quotaBase).toBeNull();
    expect(a?.diferenca).toBeNull();
  });

  it("filtra pelo nível; uma unidade sem total fica no fim, marcada", () => {
    const linhas = linhasUnidades(unidades, "distrito", "18-29", 2026, 2022);
    expect(linhas.map((l) => l.codigo)).toEqual(["2", "10", "1"]);
    expect(linhas[2]?.quota).toBeNull();
    expect(linhas[2]?.poucosVotos).toBe(true);
  });
});

describe("juntarHistorico", () => {
  function historico(
    ano: number,
    grupo: LinhaHistoricoGeografia["grupo"],
    votos: number,
  ): LinhaHistoricoGeografia {
    return {
      ano,
      ano_referencia: ano - 4,
      nivel: "condado",
      codigo: "37001",
      nome: "Unidade 37001",
      faixa: "65+",
      grupo,
      votos,
      registados: 1000,
      contributo: votos / 1000,
    };
  }

  it("calcula a quota de voto novo como no momento do voto, sem quem não tem histórico", () => {
    const unidades = juntarHistorico(agruparGeografia(LINHAS), [
      historico(2026, "antecipado_na_referencia", 120),
      historico(2026, "dia_eleicao_na_referencia", 40),
      historico(2026, "absteve_se_na_referencia", 30),
      historico(2026, "recenseado_apos_referencia", 10),
      historico(2026, "sem_historico", 500),
      historico(2022, "antecipado_na_referencia", 180),
      historico(2022, "absteve_se_na_referencia", 20),
    ]);
    const [a] = linhasUnidades(unidades, "condado", "65+", 2026, 2022);
    expect(a?.novos).toBeCloseTo(40 / 200);
    expect(a?.novosBase).toBeCloseTo(20 / 200);
  });

  it("sem histórico, a quota de voto novo fica por calcular", () => {
    const [a] = linhasUnidades(
      juntarHistorico(agruparGeografia(LINHAS), []),
      "condado",
      "65+",
      2026,
      2022,
    );
    expect(a?.novos).toBeNull();
  });
});

describe("linhasPorFaixa", () => {
  it("usa só as linhas por faixa (partido total) dos estados agregados", () => {
    const linha = (
      partido: LinhaGeografiaAgregada["partido"],
      faixa: NonNullable<LinhaGeografiaAgregada["faixa"]>,
      votos: number,
    ): LinhaGeografiaAgregada => ({
      ano: 2026,
      nivel: "condado",
      codigo: "42101",
      nome: "Philadelphia",
      partido,
      faixa,
      votos,
    });
    const linhas = linhasPorFaixa([
      linha("total", "total", 1000),
      linha("total", "65+", 600),
      linha("dem", "total", 700),
      linha("rep", "total", 200),
    ]);
    expect(linhas.map((l) => [l.faixa, l.votos])).toEqual([
      ["total", 1000],
      ["65+", 600],
    ]);
    const [u] = linhasUnidades(agruparGeografia(linhas), "condado", "65+", 2026, 2022);
    expect(u?.quota).toBeCloseTo(0.6);
    expect(u?.taxa).toBeNull();
  });
});
