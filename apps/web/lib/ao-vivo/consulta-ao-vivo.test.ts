import { readFileSync } from "node:fs";
import type { HistoricoNoite, ProjecaoNoite, ResultadosParciais } from "@intercalares/contratos";
import { describe, expect, it, vi } from "vitest";
import {
  ESPERA_MAXIMA_RECUO_MS,
  INTERVALO_MS,
  URL_AO_VIVO,
  URL_ESPELHO,
  consultaFalhou,
  consultarAoVivo,
  proximaEspera,
  type Consulta,
  type RespostaResultados,
} from "./estado.ts";

function ler(caminho: string): unknown {
  return JSON.parse(readFileSync(caminho, "utf-8"));
}

const parciais = ler("test/fixtures/resultados/parciais.json") as ResultadosParciais;
const projecao = ler("test/fixtures/noite/projecao.json") as ProjecaoNoite;
const historico = ler("test/fixtures/noite/historico.json") as HistoricoNoite;

const CONFIRMADO = "2026-11-04T01:00:00Z";
const partResultados = (origem: string) => ({ origem, confirmadoEm: CONFIRMADO, parciais });
const partNoite = (origem: string) => ({
  origem,
  confirmadoEm: CONFIRMADO,
  projecao,
  historico,
});

/** `fetch` falso: responde por URL e regista os pedidos. */
function fetchFalso(respostas: Record<string, () => Response>) {
  const chamadas: string[] = [];
  const buscar = vi.fn((url: string) => {
    chamadas.push(url);
    const resposta = respostas[url];
    return Promise.resolve(resposta ? resposta() : new Response("", { status: 404 }));
  });
  return { buscar: buscar as unknown as typeof fetch, chamadas };
}

const ESPELHO = {
  [`${URL_ESPELHO}/resultados.json`]: () => Response.json(partResultados("espelho")),
  [`${URL_ESPELHO}/noite.json`]: () => Response.json(partNoite("espelho")),
};

describe("consultarAoVivo", () => {
  it("lê as duas partes e o intervalo num só pedido", async () => {
    const { buscar, chamadas } = fetchFalso({
      [URL_AO_VIVO]: () =>
        Response.json({
          resultados: partResultados("fonte"),
          noite: partNoite("memoria"),
          intervaloS: 120,
        }),
    });
    const consulta = await consultarAoVivo(buscar);

    expect(chamadas).toEqual([URL_AO_VIVO]);
    expect(consulta.resultados.tipo).toBe("dados");
    expect(consulta.noite.tipo).toBe("dados");
    expect(consulta.intervaloMs).toBe(120_000);
  });

  it("uma parte null fica ausente; o intervalo é limitado a 30 s-10 min", async () => {
    const corpo = (intervaloS: unknown) => ({
      [URL_AO_VIVO]: () =>
        Response.json({ resultados: null, noite: partNoite("fonte"), intervaloS }),
    });
    const um = await consultarAoVivo(fetchFalso(corpo(5)).buscar);
    expect(um.resultados).toEqual({ tipo: "ausente" });
    expect(um.noite.tipo).toBe("dados");
    expect(um.intervaloMs).toBe(30_000);
    expect((await consultarAoVivo(fetchFalso(corpo(99_999)).buscar)).intervaloMs).toBe(600_000);
    expect((await consultarAoVivo(fetchFalso(corpo("x")).buscar)).intervaloMs).toBeNull();
  });

  it("404 da API: tudo ausente e o espelho não é consultado", async () => {
    const { buscar, chamadas } = fetchFalso({
      [URL_AO_VIVO]: () => new Response("", { status: 404 }),
      ...ESPELHO,
    });
    const consulta = await consultarAoVivo(buscar);

    expect(consulta).toEqual({
      resultados: { tipo: "ausente" },
      noite: { tipo: "ausente" },
      intervaloMs: null,
    });
    expect(chamadas).toEqual([URL_AO_VIVO]);
  });

  it("500 da API: lê o espelho", async () => {
    const { buscar, chamadas } = fetchFalso({
      [URL_AO_VIVO]: () => new Response("", { status: 500 }),
      ...ESPELHO,
    });
    const consulta = await consultarAoVivo(buscar);

    expect(chamadas).toEqual([
      URL_AO_VIVO,
      `${URL_ESPELHO}/resultados.json`,
      `${URL_ESPELHO}/noite.json`,
    ]);
    expect(consulta.resultados).toMatchObject({ tipo: "dados", dados: { origem: "espelho" } });
    expect(consulta.noite).toMatchObject({ tipo: "dados", dados: { origem: "espelho" } });
    expect(consulta.intervaloMs).toBeNull();
  });

  it("forma inesperada ou falha de rede: também recorre ao espelho", async () => {
    const forma = fetchFalso({
      [URL_AO_VIVO]: () => Response.json({ resultados: { parciais: 1 }, noite: null }),
      ...ESPELHO,
    });
    expect((await consultarAoVivo(forma.buscar)).resultados.tipo).toBe("dados");
    expect(forma.chamadas).toHaveLength(3);

    const rede = vi.fn(() => Promise.reject(new Error("rede")));
    const consulta = await consultarAoVivo(rede);
    expect(consulta.resultados.tipo).toBe("erro");
    expect(consulta.noite.tipo).toBe("erro");
  });
});

describe("consultaFalhou", () => {
  const dados = (origem: RespostaResultados["origem"]): Consulta<RespostaResultados> => ({
    tipo: "dados",
    dados: { origem, confirmadoEm: CONFIRMADO, parciais },
  });
  it("conta erros sem dados e respostas do espelho, não a API nem o 404", () => {
    const erro = { tipo: "erro" } as const;
    const ausente = { tipo: "ausente" } as const;
    expect(consultaFalhou(erro, erro)).toBe(true);
    expect(consultaFalhou(dados("espelho"), ausente)).toBe(true);
    expect(consultaFalhou(dados("fonte"), ausente)).toBe(false);
    expect(consultaFalhou(ausente, ausente)).toBe(false);
  });
});

describe("proximaEspera", () => {
  const base = INTERVALO_MS;

  it("varia ±10 % em torno da base", () => {
    expect(proximaEspera({ base, falhasSeguidas: 0, aleatorio: 0 })).toBeCloseTo(0.9 * base);
    expect(proximaEspera({ base, falhasSeguidas: 0, aleatorio: 0.5 })).toBeCloseTo(base);
    expect(proximaEspera({ base, falhasSeguidas: 0, aleatorio: 0.999999 })).toBeLessThanOrEqual(
      1.1 * base,
    );
  });

  it("duplica a cada falha seguida", () => {
    const com = (falhas: number) => proximaEspera({ base, falhasSeguidas: falhas, aleatorio: 0.5 });
    expect(com(1)).toBeCloseTo(2 * base);
    expect(com(2)).toBeCloseTo(4 * base);
  });

  it("não passa dos 5 minutos (antes da variação) e repõe a base sem falhas", () => {
    const maximo = proximaEspera({ base, falhasSeguidas: 10, aleatorio: 0.5 });
    expect(maximo).toBeCloseTo(ESPERA_MAXIMA_RECUO_MS);
    expect(proximaEspera({ base, falhasSeguidas: 0, aleatorio: 0.5 })).toBeCloseTo(base);
  });

  it("uma base acima do teto (10 min sem dados) não é encurtada pelo recuo", () => {
    const dezMin = 10 * 60_000;
    expect(proximaEspera({ base: dezMin, falhasSeguidas: 3, aleatorio: 0.5 })).toBeCloseTo(dezMin);
  });
});
