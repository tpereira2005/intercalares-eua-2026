import { readFileSync } from "node:fs";
import type { PrognosticosExternos } from "@intercalares/contratos";
import { describe, expect, it } from "vitest";
import { lerPrevisao, lerPrognosticos } from "./carregar.ts";
import {
  comparacaoDaCorrida,
  construirVistaPrognosticos,
  corDe,
  prognosticosBatemCerto,
} from "./prognosticos.ts";
import { construirVistaPrevisao, type VistaPrevisao } from "./vista.ts";

const FICHEIRO = "test/fixtures/previsao/prognosticos-2026.json";

function previsao(): VistaPrevisao {
  const dados = lerPrevisao("test/fixtures/previsao/2026.json");
  if (!dados) throw new Error("Falta a previsão de teste");
  return construirVistaPrevisao(dados);
}

function exemplo(): PrognosticosExternos {
  return JSON.parse(readFileSync(FICHEIRO, "utf-8")) as PrognosticosExternos;
}

describe("lerPrognosticos", () => {
  it("aceita o ficheiro de exemplo e devolve null sem ficheiro", () => {
    expect(lerPrognosticos(FICHEIRO)?.senado.length).toBe(4);
    expect(lerPrognosticos("nao-existe.json")).toBeNull();
  });
});

describe("construirVistaPrognosticos", () => {
  const vista = construirVistaPrognosticos(exemplo(), previsao());

  it("só compara com a previsão do mesmo ano", () => {
    expect(prognosticosBatemCerto(exemplo(), previsao())).toBe(true);
    expect(prognosticosBatemCerto({ ...exemplo(), ano: 2024 }, previsao())).toBe(false);
  });

  it("ignora corridas que a previsão não tem e cita a página de cada câmara", () => {
    expect(vista.senado.corridas.map((c) => c.corrida.id).sort()).toEqual(["IA-S", "TX-S", "WY-S"]);
    expect(vista.senado.fontes.map((f) => f.nome)).toEqual([
      "Wikipedia, 2026 United States Senate elections",
    ]);
    expect(vista.camara.fontes).toHaveLength(1);
  });

  it("põe o Tilt entre inclinada e renhida e usa a mediana como consenso", () => {
    const tx = comparacaoDaCorrida(vista, { id: "TX-S", camara: "senado" });
    expect(tx?.classificacoes.map((c) => c.posicao)).toEqual([5, 4, 3.5]);
    expect(tx?.consenso).toBe(4);
    expect(tx?.ladoConsenso).toBe("R");
    // O Escrutínio dá 69% D (inclinada D) e o consenso é inclinada R.
    expect(tx?.nossa).toBe("inclinadaD");
    expect(tx?.divergencia).toBe("favorito");
    expect(corDe(3.5)).toBe("inclinadaR");
    expect(corDe(2.5)).toBe("inclinadaD");
  });

  it("assinala duas categorias de distância com o mesmo favorito", () => {
    // AK-00: 34% D (inclinada R) contra provável R de todos: uma categoria, sem divergência.
    expect(comparacaoDaCorrida(vista, { id: "AK-00", camara: "camara" })?.divergencia).toBeNull();
    // NC-01: 79% D (inclinada D) contra um consenso renhido: uma categoria.
    const nc = comparacaoDaCorrida(vista, { id: "NC-01", camara: "camara" });
    expect(nc?.consenso).toBe(3);
    expect(nc?.ladoConsenso).toBeNull();
    expect(nc?.divergencia).toBeNull();
    expect(vista.senado.favoritoDiferente).toBe(1);
    expect(vista.senado.mesmoFavorito).toBe(2);
  });

  it("devolve null para uma corrida que ninguém classifica", () => {
    expect(comparacaoDaCorrida(vista, { id: "PA-07", camara: "camara" })).toBeNull();
  });
});
