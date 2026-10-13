import { mkdtempSync, readFileSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";
import { describe, expect, it } from "vitest";
import {
  DadosInvalidos,
  carregarTodas,
  carregarVistas,
  lerEstado,
  lerEstados,
} from "./carregar.ts";

const FIXTURE = "test/fixtures/voto-antecipado-sintetico.json";
const FIXTURE_AGREGADO = "test/fixtures/pa-agregado-sintetico.json";

function copiaAlterada(
  alterar: (dados: Record<string, unknown>) => void,
  origem: string = FIXTURE,
): string {
  const dados = JSON.parse(readFileSync(origem, "utf-8")) as Record<string, unknown>;
  alterar(dados);
  const destino = path.join(mkdtempSync(path.join(tmpdir(), "va-")), "nc.json");
  writeFileSync(destino, JSON.stringify(dados));
  return destino;
}

describe("lerEstado", () => {
  it("aceita um ficheiro que cumpre o contrato", () => {
    expect(lerEstado(FIXTURE)?.contrato).toBe("VotoAntecipadoEstado");
    expect(lerEstado(FIXTURE)?.dados.estado).toBe("NC");
  });

  it("reconhece e valida os estados agregados", () => {
    const pa = lerEstado(FIXTURE_AGREGADO);
    expect(pa?.contrato).toBe("VotoAntecipadoAgregado");
    expect(pa?.dados.estado).toBe("PA");
    const invalido = copiaAlterada((dados) => {
      dados.taxas = [];
    }, FIXTURE_AGREGADO);
    expect(() => lerEstado(invalido)).toThrow(/VotoAntecipadoAgregado/);
  });

  it("devolve null quando o ficheiro ainda não existe", () => {
    expect(lerEstado("dados/nao-existe.json")).toBeNull();
    expect(carregarVistas("dados/nao-existe")).toEqual([]);
  });

  it("lê todos os ficheiros de uma pasta e recusa estados repetidos", () => {
    const todas = carregarTodas("test/fixtures");
    expect(todas.individuais.map((v) => v.estado)).toEqual(["NC"]);
    expect(todas.agregados.map((v) => v.estado)).toEqual(["PA"]);
    const pasta = path.dirname(copiaAlterada(() => undefined));
    writeFileSync(path.join(pasta, "outro.json"), readFileSync(FIXTURE));
    expect(() => lerEstados(pasta)).toThrow(/mais de um ficheiro/);
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
