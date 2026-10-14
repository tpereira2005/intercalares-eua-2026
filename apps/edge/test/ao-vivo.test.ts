import { readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { beforeEach, describe, expect, it } from "vitest";
import { FRESCURA_MS, LeitorAoVivo, USER_AGENT } from "../src/ao-vivo.ts";
import { app, definirLeitor } from "../src/app.ts";
import type { Env } from "../src/env.ts";

const FIXTURES = path.resolve(
  path.dirname(fileURLToPath(import.meta.url)),
  "../../web/test/fixtures",
);
const PARCIAIS = readFileSync(path.join(FIXTURES, "resultados/parciais.json"), "utf-8");
const PROJECAO = readFileSync(path.join(FIXTURES, "noite/projecao.json"), "utf-8");
const HISTORICO = readFileSync(path.join(FIXTURES, "noite/historico.json"), "utf-8");
const CHAMADAS = readFileSync(path.join(FIXTURES, "resultados/chamadas.json"), "utf-8");

const env = {
  AMBIENTE: "teste",
  URL_PARCIAIS: "https://fonte.test/parciais.json",
  URL_PROJECAO_NOITE: "https://fonte.test/projecao.json",
  URL_HISTORICO_NOITE: "https://fonte.test/historico.json",
  URL_CHAMADAS: "https://fonte.test/chamadas.json",
} as Env;

type Resposta = () => Response;

/** Fonte falsa: cada URL responde com a função indicada; guarda os pedidos recebidos. */
class FonteFalsa {
  respostas = new Map<string, Resposta>();
  pedidos: { url: string; cabecalhos: Headers }[] = [];

  /** Pedidos a um só ficheiro. */
  pedidosA(url: string) {
    return this.pedidos.filter((p) => p.url === url);
  }

  buscar: typeof fetch = (pedido, opcoes) => {
    const url = pedido instanceof Request ? pedido.url : String(pedido);
    this.pedidos.push({ url, cabecalhos: new Headers(opcoes?.headers) });
    const resposta = this.respostas.get(url);
    return Promise.resolve(resposta ? resposta() : new Response("", { status: 404 }));
  };
}

function ficheiro(texto: string, etag = '"v1"'): Resposta {
  return () =>
    new Response(texto, {
      headers: { ETag: etag, "Last-Modified": "Tue, 03 Nov 2026 23:00:00 GMT" },
    });
}

let fonte: FonteFalsa;
let agora: number;

beforeEach(() => {
  fonte = new FonteFalsa();
  agora = Date.parse("2026-11-04T01:00:00Z");
  definirLeitor(new LeitorAoVivo(fonte.buscar, () => agora));
});

describe("/api/resultados", () => {
  it("serve o ficheiro validado com a origem e a hora", async () => {
    fonte.respostas.set(env.URL_PARCIAIS, ficheiro(PARCIAIS));
    const resposta = await app.request("/api/resultados", {}, env);

    expect(resposta.status).toBe(200);
    expect(resposta.headers.get("Cache-Control")).toBe("public, max-age=15");
    expect(resposta.headers.get("X-Origem")).toBe("fonte");
    const corpo = await resposta.json<Record<string, unknown>>();
    expect(corpo.parciais).toEqual(JSON.parse(PARCIAIS));
    expect(corpo.origem).toBe("fonte");
    expect(corpo.confirmadoEm).toBe("2026-11-04T01:00:00.000Z");
    expect(fonte.pedidosA(env.URL_PARCIAIS)[0]?.cabecalhos.get("User-Agent")).toBe(USER_AGENT);
  });

  it("junta as chamadas das redações, ou null sem elas", async () => {
    fonte.respostas.set(env.URL_PARCIAIS, ficheiro(PARCIAIS));
    const sem = await app.request("/api/resultados", {}, env);
    expect((await sem.json<{ chamadas: unknown }>()).chamadas).toBeNull();

    agora += FRESCURA_MS;
    fonte.respostas.set(env.URL_CHAMADAS, ficheiro(CHAMADAS));
    const com = await app.request("/api/resultados", {}, env);
    expect((await com.json<{ chamadas: unknown }>()).chamadas).toEqual(JSON.parse(CHAMADAS));
  });

  it("serve da memória dentro do prazo e depois pergunta com cabeçalhos condicionais", async () => {
    fonte.respostas.set(env.URL_PARCIAIS, ficheiro(PARCIAIS));
    await app.request("/api/resultados", {}, env);
    agora += FRESCURA_MS - 1;
    const memoria = await app.request("/api/resultados", {}, env);
    expect(memoria.headers.get("X-Origem")).toBe("memoria");
    expect(fonte.pedidosA(env.URL_PARCIAIS)).toHaveLength(1);

    agora += 1;
    fonte.respostas.set(env.URL_PARCIAIS, () => new Response(null, { status: 304 }));
    const confirmada = await app.request("/api/resultados", {}, env);
    expect(confirmada.status).toBe(200);
    expect((await confirmada.json<{ parciais: unknown }>()).parciais).toEqual(JSON.parse(PARCIAIS));
    expect(fonte.pedidosA(env.URL_PARCIAIS)[1]?.cabecalhos.get("If-None-Match")).toBe('"v1"');
    expect(fonte.pedidosA(env.URL_PARCIAIS)[1]?.cabecalhos.get("If-Modified-Since")).toBe(
      "Tue, 03 Nov 2026 23:00:00 GMT",
    );
  });

  it("partilha uma só ida à fonte entre pedidos simultâneos", async () => {
    fonte.respostas.set(env.URL_PARCIAIS, ficheiro(PARCIAIS));
    await Promise.all([1, 2, 3].map(async () => app.request("/api/resultados", {}, env)));
    expect(fonte.pedidosA(env.URL_PARCIAIS)).toHaveLength(1);
  });

  it("nunca serve um ficheiro que não cumpre o contrato: fica a cópia anterior", async () => {
    fonte.respostas.set(env.URL_PARCIAIS, ficheiro(PARCIAIS));
    await app.request("/api/resultados", {}, env);
    agora += FRESCURA_MS;
    fonte.respostas.set(env.URL_PARCIAIS, ficheiro('{"ano": "2026"}', '"v2"'));
    const resposta = await app.request("/api/resultados", {}, env);

    expect(resposta.status).toBe(200);
    expect(resposta.headers.get("X-Origem")).toBe("copia-antiga");
    const corpo = await resposta.json<{ parciais: unknown; confirmadoEm: string }>();
    expect(corpo.parciais).toEqual(JSON.parse(PARCIAIS));
    expect(corpo.confirmadoEm).toBe("2026-11-04T01:00:00.000Z");
  });

  it("serve a cópia anterior quando a fonte falha, e não insiste antes do prazo", async () => {
    fonte.respostas.set(env.URL_PARCIAIS, ficheiro(PARCIAIS));
    await app.request("/api/resultados", {}, env);
    agora += FRESCURA_MS;
    fonte.respostas.set(env.URL_PARCIAIS, () => new Response("", { status: 502 }));
    const resposta = await app.request("/api/resultados", {}, env);
    expect(resposta.headers.get("X-Origem")).toBe("copia-antiga");

    await app.request("/api/resultados", {}, env);
    expect(fonte.pedidosA(env.URL_PARCIAIS)).toHaveLength(2);
  });

  it("responde 503 sem cópia quando a fonte falha, e 404 antes de haver ficheiro", async () => {
    fonte.respostas.set(env.URL_PARCIAIS, ficheiro("<html>"));
    const falha = await app.request("/api/resultados", {}, env);
    expect(falha.status).toBe(503);
    expect(falha.headers.get("Cache-Control")).toBe("no-store");

    fonte.respostas.delete(env.URL_PARCIAIS);
    agora += FRESCURA_MS;
    const ausente = await app.request("/api/resultados", {}, env);
    expect(ausente.status).toBe(404);
  });
});

describe("/api/noite", () => {
  it("junta a projeção e o histórico", async () => {
    fonte.respostas.set(env.URL_PROJECAO_NOITE, ficheiro(PROJECAO));
    fonte.respostas.set(env.URL_HISTORICO_NOITE, ficheiro(HISTORICO));
    const resposta = await app.request("/api/noite", {}, env);

    expect(resposta.status).toBe(200);
    const corpo = await resposta.json<Record<string, unknown>>();
    expect(corpo.projecao).toEqual(JSON.parse(PROJECAO));
    expect(corpo.historico).toEqual(JSON.parse(HISTORICO));
  });

  it("serve a projeção sem histórico", async () => {
    fonte.respostas.set(env.URL_PROJECAO_NOITE, ficheiro(PROJECAO));
    const resposta = await app.request("/api/noite", {}, env);

    expect(resposta.status).toBe(200);
    expect((await resposta.json<{ historico: unknown }>()).historico).toBeNull();
  });

  it("responde 404 sem projeção", async () => {
    fonte.respostas.set(env.URL_HISTORICO_NOITE, ficheiro(HISTORICO));
    const resposta = await app.request("/api/noite", {}, env);
    expect(resposta.status).toBe(404);
  });
});
