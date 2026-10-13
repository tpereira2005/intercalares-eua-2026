import { Hono } from "hono";
import { secureHeaders } from "hono/secure-headers";
import type { Env } from "./env.ts";

export const app = new Hono<{ Bindings: Env }>().basePath("/api");

app.use(
  "*",
  secureHeaders({
    crossOriginResourcePolicy: "cross-origin",
  }),
);

app.use("*", async (c, next) => {
  await next();
  if (!c.res.headers.has("Cache-Control")) {
    c.header("Cache-Control", "no-store");
  }
});

/** Verificação de estado usada pela monitorização e pelos testes de fumo. */
app.get("/saude", (c) => c.json({ estado: "ok", ambiente: c.env.AMBIENTE }));

app.notFound((c) => c.json({ erro: "Recurso não encontrado." }, 404));

app.onError((erro, c) => {
  console.error("Erro não tratado na API", erro);
  return c.json({ erro: "Erro interno." }, 500);
});
