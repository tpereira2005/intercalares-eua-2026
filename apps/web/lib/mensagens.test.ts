import { describe, expect, it } from "vitest";
import { t } from "./mensagens.ts";

describe("mensagens", () => {
  it("devolve o texto de uma chave", () => {
    expect(t("site.nome")).toBe("Escrutínio");
  });

  it("substitui marcadores", () => {
    expect(t("comum.atualizadoEm", { data: "13 de outubro" })).toBe("Atualizado a 13 de outubro");
    expect(t("comum.atualizadoEm")).toBe("Atualizado a {data}");
  });
});
