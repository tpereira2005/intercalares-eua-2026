import { copyFileSync, mkdtempSync, readFileSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";
import { describe, expect, it } from "vitest";
import { DadosInvalidos } from "../validacao.ts";
import { carregarPrevisao, lerHistorico, lerPrevisao } from "./carregar.ts";

const PASTA = "test/fixtures/previsao";

function pastaCom(ficheiros: Record<string, (dados: Record<string, unknown>) => void>): string {
  const destino = mkdtempSync(path.join(tmpdir(), "previsao-"));
  for (const [nome, alterar] of Object.entries(ficheiros)) {
    const dados = JSON.parse(readFileSync(path.join(PASTA, nome), "utf-8")) as Record<
      string,
      unknown
    >;
    alterar(dados);
    writeFileSync(path.join(destino, nome), JSON.stringify(dados));
  }
  return destino;
}

describe("lerPrevisao", () => {
  it("aceita um ficheiro que cumpre o contrato", () => {
    const dados = lerPrevisao(path.join(PASTA, "2026.json"));
    expect(dados?.ano).toBe(2026);
    expect(dados?.corridas).toHaveLength(10);
  });

  it("devolve null quando o ficheiro não existe", () => {
    expect(lerPrevisao("nao-existe/2026.json")).toBeNull();
  });

  it("rejeita uma probabilidade fora de [0, 1]", () => {
    const pasta = pastaCom({
      "2026.json": (d) => {
        (d.camara as Record<string, unknown>).prob_controlo_d = 1.2;
      },
    });
    expect(() => lerPrevisao(path.join(pasta, "2026.json"))).toThrow(DadosInvalidos);
  });

  it("rejeita campos a mais", () => {
    const pasta = pastaCom({
      "2026.json": (d) => {
        d.extra = true;
      },
    });
    expect(() => lerPrevisao(path.join(pasta, "2026.json"))).toThrow(DadosInvalidos);
  });
});

describe("lerHistorico", () => {
  it("aceita o histórico diário", () => {
    expect(lerHistorico(path.join(PASTA, "historico-2026.json"))?.dias).toHaveLength(3);
  });

  it("rejeita um dia sem resumo do Senado", () => {
    const pasta = pastaCom({
      "historico-2026.json": (d) => {
        delete (d.dias as Record<string, unknown>[])[0]?.senado;
      },
    });
    expect(() => lerHistorico(path.join(pasta, "historico-2026.json"))).toThrow(DadosInvalidos);
  });
});

describe("carregarPrevisao", () => {
  it("junta a previsão e a evolução", () => {
    const dados = carregarPrevisao(PASTA);
    expect(dados?.previsao.corte).toBe("2026-10-13");
    expect(dados?.evolucao?.cortes).toEqual(["2026-09-29", "2026-10-06", "2026-10-13"]);
  });

  it("mostra a previsão sem histórico", () => {
    const pasta = mkdtempSync(path.join(tmpdir(), "previsao-"));
    copyFileSync(path.join(PASTA, "2026.json"), path.join(pasta, "2026.json"));
    const dados = carregarPrevisao(pasta);
    expect(dados?.previsao.ano).toBe(2026);
    expect(dados?.evolucao).toBeNull();
  });

  it("devolve null sem previsão, mesmo com histórico", () => {
    const pasta = mkdtempSync(path.join(tmpdir(), "previsao-"));
    copyFileSync(path.join(PASTA, "historico-2026.json"), path.join(pasta, "historico-2026.json"));
    expect(carregarPrevisao(pasta)).toBeNull();
  });

  it("recusa um histórico de outro ano", () => {
    const pasta = pastaCom({
      "2026.json": () => undefined,
      "historico-2026.json": (d) => {
        d.ano = 2024;
      },
    });
    expect(() => carregarPrevisao(pasta)).toThrow(/Histórico de 2024/);
  });
});
