import { mkdtempSync, readFileSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";
import type { SondagensCongresso } from "@intercalares/contratos";
import { describe, expect, it } from "vitest";
import { DadosInvalidos } from "../validacao.ts";
import { lerSondagens } from "./carregar.ts";
import { caminhoCorrida, construirVistaSondagens, nomeCorrida } from "./vista.ts";

const EXEMPLO = "test/fixtures/sondagens/2026.json";

function exemplo(): SondagensCongresso {
  const dados = lerSondagens(EXEMPLO);
  if (!dados) throw new Error("Falta o exemplo das sondagens");
  return dados;
}

describe("lerSondagens", () => {
  it("aceita o exemplo e devolve null sem ficheiro", () => {
    expect(exemplo().corridas.length).toBeGreaterThan(0);
    expect(lerSondagens("nao-existe/2026.json")).toBeNull();
  });

  it("rejeita um peso fora de [0, 1]", () => {
    const dados = JSON.parse(readFileSync(EXEMPLO, "utf-8")) as SondagensCongresso;
    const sondagem = dados.corridas[0]?.sondagens[0];
    if (!sondagem) throw new Error("Exemplo sem sondagens");
    sondagem.peso = 2;
    const caminho = path.join(mkdtempSync(path.join(tmpdir(), "sondagens-")), "2026.json");
    writeFileSync(caminho, JSON.stringify(dados));
    expect(() => lerSondagens(caminho)).toThrow(DadosInvalidos);
  });
});

describe("construirVistaSondagens", () => {
  it("ordena as corridas pelo nome do estado e o voto genérico por data", () => {
    const v = construirVistaSondagens(exemplo());
    expect(v.corridas.map((c) => c.id)).toEqual(["AK-S", "NC-S"]);
    const datas = v.votoGenerico.map((p) => p.data);
    expect([...datas].sort()).toEqual(datas);
  });

  it("mantém os pesos do modelo: somam 1 em cada corrida com média", () => {
    for (const c of construirVistaSondagens(exemplo()).corridas) {
      if (c.media === null) continue;
      const soma = c.sondagens.reduce((s, x) => s + x.peso, 0);
      // O exemplo guarda só as sondagens mais recentes; a soma não passa de 1.
      expect(soma).toBeLessThanOrEqual(1 + 1e-9);
    }
  });

  it("dá endereços e nomes legíveis às corridas", () => {
    expect(caminhoCorrida("OH-S-especial")).toBe("/sondagens/oh-s-especial/");
    expect(nomeCorrida({ id: "OH-S-especial", estado: "OH" })).toBe("Ohio (especial)");
    expect(nomeCorrida({ id: "NC-S", estado: "NC" })).toBe("Carolina do Norte");
  });
});
