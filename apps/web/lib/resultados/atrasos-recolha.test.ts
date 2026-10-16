import { readFileSync } from "node:fs";
import type { SaudeRecolha } from "@intercalares/contratos";
import { describe, expect, it } from "vitest";
import { obterValidador } from "../validacao.ts";
import { atrasosDosEstados } from "./atrasos.ts";
import { lerSaude } from "./carregar.ts";

const SAUDE = "test/fixtures/resultados/saude.json";

function exemplo(): SaudeRecolha {
  return JSON.parse(readFileSync(SAUDE, "utf-8")) as SaudeRecolha;
}

describe("fontes atrasadas", () => {
  it("o ficheiro de exemplo cumpre o contrato", () => {
    expect(obterValidador("SaudeRecolha")(exemplo())).toBe(true);
    expect(lerSaude(SAUDE)).toEqual(exemplo());
    expect(lerSaude("test/fixtures/resultados/nao-existe.json")).toBeNull();
  });

  it("marca só os estados com todas as entradas em alerta", () => {
    const atrasos = atrasosDosEstados(exemplo(), 2026);
    // O Texas tem a fonte automática em falha, mas a entrada manual está em dia.
    expect([...atrasos.keys()]).toEqual(["GA"]);
    expect(atrasos.get("GA")).toEqual({ motivo: "parada", desde: "2026-11-04T01:40:00Z" });
  });

  it("distingue a fonte que não responde da que não traz dados novos", () => {
    const saude = exemplo();
    const semManual = { ...saude.estados };
    delete semManual["TX-manual"];
    const atrasos = atrasosDosEstados({ ...saude, estados: semManual }, 2026);
    expect(atrasos.get("TX")).toEqual({ motivo: "semResposta", desde: "2026-11-04T02:15:00Z" });
  });

  it("ignora a saúde de outra eleição e a ausência de ficheiro", () => {
    expect(atrasosDosEstados(exemplo(), 2024).size).toBe(0);
    expect(atrasosDosEstados(null, 2026).size).toBe(0);
  });
});
