import { mkdtempSync, readFileSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";
import { describe, expect, it } from "vitest";
import { DadosInvalidos, carregarVista, lerEstado } from "./carregar.ts";

const FIXTURE = "test/fixtures/voto-antecipado-sintetico.json";

function copiaAlterada(alterar: (dados: Record<string, unknown>) => void): string {
  const dados = JSON.parse(readFileSync(FIXTURE, "utf-8")) as Record<string, unknown>;
  alterar(dados);
  const destino = path.join(mkdtempSync(path.join(tmpdir(), "va-")), "nc.json");
  writeFileSync(destino, JSON.stringify(dados));
  return destino;
}

describe("lerEstado", () => {
  it("aceita um ficheiro que cumpre o contrato", () => {
    expect(lerEstado(FIXTURE)?.estado).toBe("NC");
  });

  it("devolve null quando o ficheiro ainda não existe", () => {
    expect(lerEstado("dados/nao-existe.json")).toBeNull();
    expect(carregarVista("dados/nao-existe.json")).toBeNull();
  });

  it("recusa um ficheiro sem um campo obrigatório", () => {
    const caminho = copiaAlterada((dados) => {
      delete dados.serie;
    });
    expect(() => lerEstado(caminho)).toThrow(DadosInvalidos);
  });

  it("recusa campos desconhecidos e valores fora do contrato", () => {
    const extra = copiaAlterada((dados) => {
      dados.nomes = ["não devia estar aqui"];
    });
    expect(() => lerEstado(extra)).toThrow(DadosInvalidos);
    const estado = copiaAlterada((dados) => {
      dados.estado = "XX";
    });
    expect(() => lerEstado(estado)).toThrow(DadosInvalidos);
  });
});
