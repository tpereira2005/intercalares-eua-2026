import { readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ESPERA_MAXIMA_MS, FRESCURA_MS, LeitorAoVivo, USER_AGENT } from "../src/ao-vivo.ts";
import { app, definirLeitor } from "../src/app.ts";
import type { Env } from "../src/env.ts";
import { ResultadosParciais } from "../src/gerado/validadores.js";

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

describe("stale-while-revalidate", () => {
  const FONTE = { url: "https://fonte.test/parciais.json", validar: ResultadosParciais };

  /** Fonte cuja resposta só sai quando o teste a liberar (ou nunca). */
  function fonteControlada() {
    const pendentes: ((r: Response) => void)[] = [];
    let pedidos = 0;
    const buscar: typeof fetch = () => {
      pedidos += 1;
      return new Promise<Response>((resolver) => pendentes.push(resolver));
    };
    return {
      buscar,
      pedidos: () => pedidos,
      responder: (texto: string, etag: string) =>
        pendentes.shift()?.(new Response(texto, { headers: { ETag: etag } })),
    };
  }

  /** Aquece a cópia (primeira leitura, a fonte responde logo) e deixa-a expirar. */
  async function comCopiaExpirada() {
    const controlada = fonteControlada();
    const leitorLocal = new LeitorAoVivo(controlada.buscar, () => agora);
    const primeira = leitorLocal.ler(FONTE);
    controlada.responder(PARCIAIS, '"v1"');
    await primeira;
    agora += FRESCURA_MS;
    return { controlada, leitorLocal };
  }

  beforeEach(() => {
    vi.useFakeTimers();
  });
  afterEach(() => {
    vi.useRealTimers();
  });

  it("sem cópia, espera pela fonte", async () => {
    const controlada = fonteControlada();
    const leitorLocal = new LeitorAoVivo(controlada.buscar, () => agora);
    let resultado: unknown = null;
    const leitura = leitorLocal.ler(FONTE).then((l) => (resultado = l));

    await vi.advanceTimersByTimeAsync(ESPERA_MAXIMA_MS * 3);
    expect(resultado).toBeNull();

    controlada.responder(PARCIAIS, '"v1"');
    await leitura;
    expect(resultado).toMatchObject({ tipo: "dados", origem: "fonte" });
  });

  it("com a fonte pendurada, serve a cópia expirada ao fim de ESPERA_MAXIMA_MS", async () => {
    const { controlada, leitorLocal } = await comCopiaExpirada();
    const entregues: Promise<unknown>[] = [];
    let resultado: unknown = null;
    const leitura = leitorLocal.ler(FONTE, (p) => entregues.push(p)).then((l) => (resultado = l));

    await vi.advanceTimersByTimeAsync(ESPERA_MAXIMA_MS - 1);
    expect(resultado).toBeNull();
    await vi.advanceTimersByTimeAsync(1);
    await leitura;

    expect(resultado).toMatchObject({ tipo: "dados", texto: PARCIAIS, origem: "memoria" });
    // A renovação continua em segundo plano e foi entregue ao contexto.
    expect(entregues).toHaveLength(1);
    expect(controlada.pedidos()).toBe(2);
    expect(vi.getTimerCount()).toBe(0);
  });

  it("devolve dados novos quando a fonte responde dentro do prazo", async () => {
    const { controlada, leitorLocal } = await comCopiaExpirada();
    const leitura = leitorLocal.ler(FONTE, () => undefined);
    await vi.advanceTimersByTimeAsync(100);
    controlada.responder(PARCIAIS, '"v2"');
    const resultado = await leitura;

    expect(resultado).toMatchObject({ tipo: "dados", origem: "fonte", confirmadaEm: agora });
    expect(vi.getTimerCount()).toBe(0);
  });

  it("pedidos simultâneos partilham a renovação e uma fonte em falha só é perguntada uma vez", async () => {
    const { controlada, leitorLocal } = await comCopiaExpirada();
    const leituras = [1, 2, 3].map(async () => leitorLocal.ler(FONTE, () => undefined));
    await vi.advanceTimersByTimeAsync(ESPERA_MAXIMA_MS);
    await Promise.all(leituras);
    expect(controlada.pedidos()).toBe(2);

    // A renovação falha (JSON inválido): serve-se a cópia antiga e não se insiste antes do prazo.
    controlada.responder("", '"x"');
    await vi.advanceTimersByTimeAsync(0);
    const depois = await leitorLocal.ler(FONTE, () => undefined);
    expect(depois).toMatchObject({ tipo: "dados", origem: "copia-antiga" });
    expect(controlada.pedidos()).toBe(2);
  });

  it("assinala copia-antiga quando a última tentativa falhou", async () => {
    const { controlada, leitorLocal } = await comCopiaExpirada();
    const primeira = leitorLocal.ler(FONTE, () => undefined);
    controlada.responder("<html>", '"v2"');
    await primeira;
    agora += FRESCURA_MS;
    const segunda = leitorLocal.ler(FONTE, () => undefined);
    await vi.advanceTimersByTimeAsync(ESPERA_MAXIMA_MS);
    expect(await segunda).toMatchObject({ origem: "copia-antiga" });
  });
});

describe("/api/ao-vivo", () => {
  function tudo() {
    fonte.respostas.set(env.URL_PARCIAIS, ficheiro(PARCIAIS));
    fonte.respostas.set(env.URL_CHAMADAS, ficheiro(CHAMADAS));
    fonte.respostas.set(env.URL_PROJECAO_NOITE, ficheiro(PROJECAO));
    fonte.respostas.set(env.URL_HISTORICO_NOITE, ficheiro(HISTORICO));
  }

  it("junta os corpos de /api/resultados e /api/noite e o intervalo", async () => {
    tudo();
    const resposta = await app.request("/api/ao-vivo", {}, env);

    expect(resposta.status).toBe(200);
    expect(resposta.headers.get("Cache-Control")).toBe("public, max-age=15");
    expect(resposta.headers.get("X-Origem")).toBe("fonte");
    const texto = await resposta.text();
    const corpo = JSON.parse(texto) as Record<string, unknown>;
    const resultados = await (await app.request("/api/resultados", {}, env)).text();
    const noite = await (await app.request("/api/noite", {}, env)).text();
    expect(corpo.intervaloS).toBe(60);
    // O corpo de cada parte é o texto da rota própria; só a origem muda (agora vem da memória).
    expect(corpo.resultados).toEqual({ ...JSON.parse(resultados), origem: "fonte" });
    expect(corpo.noite).toEqual({ ...JSON.parse(noite), origem: "fonte" });
  });

  it("não volta a serializar os ficheiros: o texto da fonte vai tal como chegou", async () => {
    tudo();
    const texto = await (await app.request("/api/ao-vivo", {}, env)).text();
    expect(texto).toContain(PARCIAIS);
    expect(texto).toContain(PROJECAO);
  });

  it("200 com uma das partes ausente (null)", async () => {
    fonte.respostas.set(env.URL_PROJECAO_NOITE, ficheiro(PROJECAO));
    const resposta = await app.request("/api/ao-vivo", {}, env);

    expect(resposta.status).toBe(200);
    const corpo = await resposta.json<{ resultados: unknown; noite: unknown }>();
    expect(corpo.resultados).toBeNull();
    expect(corpo.noite).not.toBeNull();
  });

  it("404 quando nenhuma das partes foi publicada", async () => {
    const resposta = await app.request("/api/ao-vivo", {}, env);
    expect(resposta.status).toBe(404);
    expect(resposta.headers.get("Cache-Control")).toBe("no-store");
  });

  it("503 quando falha sem cópia, mesmo que a outra parte esteja ausente", async () => {
    fonte.respostas.set(env.URL_PARCIAIS, ficheiro("<html>"));
    const resposta = await app.request("/api/ao-vivo", {}, env);
    expect(resposta.status).toBe(503);
    expect(resposta.headers.get("Cache-Control")).toBe("no-store");
  });

  it("limita INTERVALO_S a 30-600 e usa 60 se faltar ou for inválido", async () => {
    tudo();
    const intervalo = async (valor: string | undefined) => {
      const resposta = await app.request(
        "/api/ao-vivo",
        {},
        valor === undefined ? env : { ...env, INTERVALO_S: valor },
      );
      return (await resposta.json<{ intervaloS: number }>()).intervaloS;
    };
    expect(await intervalo(undefined)).toBe(60);
    expect(await intervalo("120")).toBe(120);
    expect(await intervalo("5")).toBe(30);
    expect(await intervalo("9999")).toBe(600);
    expect(await intervalo("abc")).toBe(60);
    expect(await intervalo("")).toBe(60);
  });

  it("entrega a renovação ao waitUntil do contexto quando há cópia expirada", async () => {
    tudo();
    await app.request("/api/ao-vivo", {}, env);
    agora += FRESCURA_MS;
    const waitUntil = vi.fn();
    const contexto = { waitUntil, passThroughOnException: vi.fn() } as unknown as ExecutionContext;
    const resposta = await app.request("/api/ao-vivo", {}, env, contexto);

    expect(resposta.status).toBe(200);
    expect(waitUntil).toHaveBeenCalled();
  });

  it("X-Origem é a pior das duas partes", async () => {
    tudo();
    await app.request("/api/ao-vivo", {}, env);
    agora += FRESCURA_MS;
    // Só a projeção passa a falhar; a contagem é confirmada com 304.
    fonte.respostas.set(env.URL_PARCIAIS, () => new Response(null, { status: 304 }));
    fonte.respostas.set(env.URL_PROJECAO_NOITE, () => new Response("", { status: 502 }));
    const resposta = await app.request("/api/ao-vivo", {}, env);

    expect(resposta.status).toBe(200);
    expect(resposta.headers.get("X-Origem")).toBe("copia-antiga");
    const corpo = await resposta.json<{
      resultados: { origem: string };
      noite: { origem: string };
    }>();
    expect(corpo.resultados.origem).toBe("fonte");
    expect(corpo.noite.origem).toBe("copia-antiga");
  });
});
