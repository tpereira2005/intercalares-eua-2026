import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";
import { DESTINO, gerarCodigo } from "../scripts/gerar-validadores.mjs";

describe("validadores gerados", () => {
  it("estão atualizados (pnpm --filter @intercalares/edge validadores:gerar)", async () => {
    expect(readFileSync(DESTINO, "utf-8")).toBe(await gerarCodigo());
  });
});
