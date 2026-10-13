import { readFileSync } from "node:fs";
import type { VotoAntecipadoEstado } from "@intercalares/contratos";
import { describe, expect, it } from "vitest";
import { resumirEstado } from "./resumo.ts";
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
