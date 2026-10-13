import { describe, expect, it } from "vitest";
import { app } from "../src/app.ts";
import type { Env } from "../src/env.ts";

const env = { AMBIENTE: "teste" } as Env;

describe("API", () => {
  it("responde à verificação de estado", async () => {
    const resposta = await app.request("/api/saude", {}, env);

    expect(resposta.status).toBe(200);
    expect(await resposta.json()).toEqual({ estado: "ok", ambiente: "teste" });
    expect(resposta.headers.get("Cache-Control")).toBe("no-store");
  });

  it("envia cabeçalhos de segurança", async () => {
    const resposta = await app.request("/api/saude", {}, env);

    expect(resposta.headers.get("X-Content-Type-Options")).toBe("nosniff");
    expect(resposta.headers.get("Strict-Transport-Security")).toContain("max-age=");
  });

  it("devolve 404 em JSON para rotas desconhecidas", async () => {
    const resposta = await app.request("/api/inexistente", {}, env);

    expect(resposta.status).toBe(404);
    expect(await resposta.json()).toEqual({ erro: "Recurso não encontrado." });
  });
});
