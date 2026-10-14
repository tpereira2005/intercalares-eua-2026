import type { LinhaGeografia, LinhaHistoricoGeografia } from "@intercalares/contratos";
import { describe, expect, it } from "vitest";
import {
  agruparGeografia,
  linhasMomento,
  linhasUnidades,
  MINIMO_VOTOS_UNIDADE,
  nivelPorOmissao,
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

describe("nivelPorOmissao", () => {
  const unidades = agruparGeografia(LINHAS);

  it("escolhe o primeiro nível com dados do ano de comparação", () => {
    // Os distritos só têm 2026; os condados têm 2022.
    expect(nivelPorOmissao(unidades, 2022)).toBe("condado");
  });

  it("fica nos distritos quando nenhum nível tem o ano de comparação", () => {
    expect(nivelPorOmissao(unidades, 2018)).toBe("distrito");
  });

  it("devolve null sem unidades", () => {
    expect(nivelPorOmissao([], 2022)).toBeNull();
  });
});

describe("linhasMomento", () => {
  function historico(
    ano: number,
    codigo: string,
    faixa: LinhaHistoricoGeografia["faixa"],
    grupo: LinhaHistoricoGeografia["grupo"],
    votos: number,
  ): LinhaHistoricoGeografia {
    return {
      ano,
      ano_referencia: ano - 4,
      nivel: "condado",
      codigo,
      nome: `Unidade ${codigo}`,
      faixa,
      grupo,
      votos,
      registados: 1000,
      contributo: null,
    };
  }
  const HISTORICO = [
    // 2026: 100 habituais, 100 antecipação, 150 + 50 novos, e 999 sem histórico (fica fora).
    historico(2026, "37001", "18-29", "antecipado_na_referencia", 100),
    historico(2026, "37001", "18-29", "dia_eleicao_na_referencia", 100),
    historico(2026, "37001", "18-29", "absteve_se_na_referencia", 150),
    historico(2026, "37001", "18-29", "recenseado_apos_referencia", 50),
    historico(2026, "37001", "18-29", "sem_historico", 999),
    // 2022: 25% de voto novo.
    historico(2022, "37001", "18-29", "antecipado_na_referencia", 200),
    historico(2022, "37001", "18-29", "dia_eleicao_na_referencia", 100),
    historico(2022, "37001", "18-29", "absteve_se_na_referencia", 100),
    // Unidade sem linha de geografia: ignorada.
    historico(2026, "99999", "18-29", "antecipado_na_referencia", 500),
  ];
  const unidades = agruparGeografia(LINHAS, HISTORICO);

  it("junta o histórico às unidades e calcula as partes de cada grupo", () => {
    const [a] = linhasMomento(unidades, "condado", "18-29", 2026, 2022);
    expect(a?.codigo).toBe("37001");
    expect(a?.votos).toBe(400);
    expect(a?.habituais).toBeCloseTo(0.25);
    expect(a?.antecipacao).toBeCloseTo(0.25);
    expect(a?.novos).toBeCloseTo(0.5);
    expect(a?.novosBase).toBeCloseTo(0.25);
    expect(a?.diferenca).toBeCloseTo(0.25);
    expect(unidades.some((u) => u.codigo === "99999")).toBe(false);
  });

  it("guarda o ano de referência e deixa sem momento os anos sem histórico", () => {
    const a = unidades.find((u) => u.codigo === "37001");
    expect(a?.anos.find((x) => x.ano === 2026)?.momento?.anoReferencia).toBe(2022);
    expect(unidades.find((u) => u.codigo === "37003")?.anos[0]?.momento).toBeNull();
    expect(linhasMomento(unidades, "condado", "65+", 2026, 2022)).toEqual([]);
  });
});
