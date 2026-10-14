import { describe, expect, it } from "vitest";
import { carregarSemDados, lerNacional } from "./nacional.ts";

describe("estados sem dados", () => {
  it("lê os estados bloqueados do resumo nacional publicado", () => {
    const nacional = lerNacional("test/fixtures/nacional/nacional.json");
    expect(nacional?.estados_sem_dados?.map((e) => e.estado)).toEqual([
      "GA",
      "TX",
      "MI",
      "OH",
      "NV",
      "AZ",
    ]);
    expect(nacional?.estados_sem_dados?.every((e) => e.motivo === "bloqueado")).toBe(true);
  });

  it("sem resumo nacional, a lista fica vazia", () => {
    expect(carregarSemDados("nao-existe")).toEqual([]);
  });
});
