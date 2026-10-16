import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";
import { MAXIMO_PEDIDOS, percentil, planear } from "../scripts/carga-remota.mjs";
import { NOME_ENSAIO, configuracaoEnsaio, lerJsonc } from "../scripts/configurar-ensaio.mjs";

const base = lerJsonc(readFileSync(new URL("../wrangler.jsonc", import.meta.url), "utf-8"));
const opcoes = {
  etiqueta: "resultados-ensaio",
  etiquetaNoite: "resultados-ensaio",
  anoNoite: "2024",
  intervalo: 60,
};

describe("Worker de ensaio", () => {
  it("lê o wrangler.jsonc com comentários sem estragar os URLs", () => {
    expect(base.name).toBe("intercalares-eua-2026");
    expect(base.vars.URL_PARCIAIS).toMatch(/^https:\/\/github\.com\//);
  });

  it("tem outro nome, sem cron nem D1, e lê a Release de ensaio", () => {
    const c = configuracaoEnsaio(base, opcoes);
    expect(c.name).toBe(NOME_ENSAIO);
    expect(c.triggers.crons).toEqual([]);
    expect(c.d1_databases).toBeUndefined();
    expect(c.vars.AMBIENTE).toBe("ensaio");
    expect(c.vars.URL_PARCIAIS).toContain("/download/resultados-ensaio/parciais.json");
    expect(c.vars.URL_CHAMADAS).toContain("/download/resultados-ensaio/chamadas-2026.json");
    expect(c.vars.URL_SAUDE).toContain("/download/resultados-ensaio/saude.json");
    expect(c.vars.URL_PROJECAO_NOITE).toContain(
      "/download/resultados-ensaio/projecao-noite-2024.json",
    );
    expect(c.vars.URL_HISTORICO_NOITE).toContain(
      "/download/resultados-ensaio/historico-noite-2024.json",
    );
    expect(c.assets).toEqual(base.assets);
  });

  it("recusa a Release de produção e etiquetas estranhas", () => {
    expect(() => configuracaoEnsaio(base, { ...opcoes, etiqueta: "resultados-2026" })).toThrow();
    expect(() => configuracaoEnsaio(base, { ...opcoes, etiqueta: "../x" })).toThrow();
    expect(() => configuracaoEnsaio(base, { ...opcoes, anoNoite: "24/../x" })).toThrow();
  });
});

describe("carga remota", () => {
  it("planeia o total de pedidos antes de começar", () => {
    expect(planear({ leitores: 200, intervaloS: 60, duracaoMin: 30 })).toEqual({
      porLeitor: 30,
      total: 6000,
    });
    expect(planear({ leitores: 500, intervaloS: 60, duracaoMin: 61 }).total).toBeGreaterThan(
      MAXIMO_PEDIDOS,
    );
  });

  it("calcula percentis pelo método do posto mais próximo", () => {
    const v = [10, 20, 30, 40, 50, 60, 70, 80, 90, 100];
    expect(percentil(v, 50)).toBe(50);
    expect(percentil(v, 95)).toBe(100);
    expect(percentil([], 95)).toBeNull();
  });
});
