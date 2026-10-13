import { describe, expect, it } from "vitest";
import { t } from "./mensagens.ts";

describe("mensagens", () => {
  it("devolve o texto de uma chave", () => {
    expect(t("site.nome")).toBe("Intercalares EUA 2026");
  });

  it("substitui marcadores", () => {
    expect(t("inicio.contagemDecrescente", { dias: 21 })).toBe("Faltam 21 dias para a eleição");
  });
});
