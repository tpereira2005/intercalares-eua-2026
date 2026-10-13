import { describe, expect, it } from "vitest";
import { ESTADOS } from "./estados.ts";
import { FECHOS, gruposFecho, proximoFecho } from "./fecho.ts";
import { formatarHora } from "./formatacao.ts";

describe("horários de fecho", () => {
  it("cobrem os 50 estados e o Distrito de Colúmbia, uma vez cada", () => {
    const codigos = FECHOS.map((f) => f.estado);
    expect(new Set(codigos).size).toBe(codigos.length);
    expect(new Set(codigos)).toEqual(new Set(ESTADOS.map((e) => e.codigo)));
  });

  it("as últimas urnas de um estado nunca fecham antes das primeiras", () => {
    for (const f of FECHOS) {
      if (f.todas) expect(Date.parse(f.todas)).toBeGreaterThan(Date.parse(f.primeiro));
    }
  });

  it("agrupa por hora, da primeira (23:00 em Lisboa) à última", () => {
    const grupos = gruposFecho();
    const primeiro = grupos[0];
    expect(primeiro?.estados.map((f) => f.estado)).toEqual(["IN", "KY"]);
    expect(formatarHora(new Date(primeiro?.instante ?? ""), "Europe/Lisbon")).toBe("23:00");
    expect(formatarHora(new Date(grupos.at(-1)?.instante ?? ""), "Europe/Lisbon")).toBe("05:00");
  });

  it("encontra o próximo fecho e nenhum depois do último", () => {
    const grupos = gruposFecho();
    expect(proximoFecho(new Date("2026-11-03T23:30:00Z"), grupos)?.instante).toBe(
      "2026-11-04T00:00:00Z",
    );
    expect(proximoFecho(new Date("2026-11-04T07:00:00Z"), grupos)).toBeNull();
  });
});
