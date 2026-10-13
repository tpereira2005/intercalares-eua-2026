import { readFileSync } from "node:fs";
import type { VotoAntecipadoAgregado, VotoAntecipadoEstado } from "@intercalares/contratos";
import { describe, expect, it } from "vitest";
import { construirVistaAgregada } from "./agregado.ts";
import { resumirAgregado, resumirEstado } from "./resumo.ts";
import { construirVista } from "./vista.ts";

const dados = JSON.parse(
  readFileSync("test/fixtures/voto-antecipado-sintetico.json", "utf-8"),
) as VotoAntecipadoEstado;

describe("resumirEstado", () => {
  const vista = construirVista(dados);
  const resumo = resumirEstado(vista);

  it("compara com a intercalar mais recente", () => {
    expect(resumo.anoBase).toBe(2022);
    expect(resumo.qualidade).toBe("individual");
  });

  it("calcula o desvio como votos observados sobre esperados", () => {
    const faixas = vista.comparacoes[0]?.faixas ?? [];
    const esperado = faixas.reduce((s, f) => s + f.esperado, 0);
    const votos = faixas.reduce((s, f) => s + f.votos, 0);
    expect(resumo.desvio.todos).toBeCloseTo(votos / esperado - 1, 12);
  });

  it("baixa a qualidade quando falta o histórico ou a comparação", () => {
    expect(resumirEstado(construirVista({ ...dados, historico: [] })).qualidade).toBe("parcial");
    const semNada = resumirEstado(construirVista({ ...dados, historico: [], comparacao: [] }));
    expect(semNada.qualidade).toBe("agregado");
    expect(semNada.desvio.todos).toBeNull();
  });
});

describe("resumirAgregado", () => {
  const pa = JSON.parse(
    readFileSync("test/fixtures/pa-agregado-sintetico.json", "utf-8"),
  ) as VotoAntecipadoAgregado;
  const vista = construirVistaAgregada(pa);
  const resumo = resumirAgregado(vista);

  it("usa o ritmo face à intercalar mais recente, sem desvios", () => {
    const total = pa.comparacao.find((l) => l.ano_base === 2022 && l.categoria === "total");
    expect(resumo.anoBase).toBe(2022);
    expect(resumo.variacaoVotos).toBe(total?.ritmo);
    expect(resumo.votosBase).toBe(total?.votos_base);
    expect(resumo.desvio).toEqual({ todos: null, mais65: null, jovens: null });
    expect(resumo.qualidade).toBe("parcial");
  });

  it("soma os boletins por devolver de todos os partidos", () => {
    const total = pa.pedidos.find(
      (l) => l.ano === 2026 && l.faixa === "total" && l.partido === "total",
    );
    expect(resumo.pendentes).toBe(total?.pendentes);
  });

  it("baixa a qualidade sem idade", () => {
    const semIdade = { ...pa, dimensoes: pa.dimensoes.filter((d) => d !== "faixa") };
    expect(resumirAgregado(construirVistaAgregada(semIdade)).qualidade).toBe("agregado");
  });
});
