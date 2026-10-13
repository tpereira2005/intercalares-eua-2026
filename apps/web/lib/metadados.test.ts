import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";
import { lerToken } from "./cartao.tsx";
import { metadadosPagina } from "./metadados.ts";

describe("metadadosPagina", () => {
  it("dá a cada página título, canónico e cartão próprios, em pt_PT", () => {
    const m = metadadosPagina({
      titulo: "Previsão",
      descricao: "Probabilidades.",
      caminho: "/previsao/",
      cartao: "previsao.png",
    });
    expect(m.title).toBe("Previsão");
    expect(m.alternates?.canonical).toBe("/previsao/");
    expect(m.openGraph).toMatchObject({
      locale: "pt_PT",
      title: "Previsão · Escrutínio",
      url: "/previsao/",
      images: [{ url: "/cartoes/previsao.png", width: 1200, height: 630 }],
    });
    expect(m.twitter).toMatchObject({ card: "summary_large_image" });
  });

  it("sem caminho (layout), não declara canónico nem endereço", () => {
    const m = metadadosPagina({
      titulo: null,
      descricao: "Site.",
      caminho: null,
      cartao: "inicio.png",
    });
    expect(m.alternates).toBeUndefined();
    expect(m.openGraph).not.toHaveProperty("url");
    expect(m.title).toBeUndefined();
  });
});

describe("lerToken", () => {
  it("lê os tokens do tema claro de tokens.css", () => {
    const css = readFileSync("styles/tokens.css", "utf-8");
    expect(lerToken(css, "signal")).toMatch(/^#[0-9a-f]{6}$/i);
    expect(() => lerToken(css, "nao-existe")).toThrow();
  });
});
