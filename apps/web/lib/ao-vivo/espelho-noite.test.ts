import { readFileSync } from "node:fs";
import type { ResultadosParciais } from "@intercalares/contratos";
import { describe, expect, it } from "vitest";
import { montarEspelho } from "./espelho.ts";
import { URL_ESPELHO, atualizarEstado, consultarResultados, type EstadoAoVivo } from "./estado.ts";

function ler(caminho: string): unknown {
  return JSON.parse(readFileSync(caminho, "utf-8"));
}

const parciais = ler("test/fixtures/resultados/parciais.json") as ResultadosParciais;
const projecao = ler("test/fixtures/noite/projecao.json");
const historico = ler("test/fixtures/noite/historico.json");
const AGORA = new Date("2026-11-04T02:00:00Z");

describe("espelho de emergência", () => {
  it("embrulha os ficheiros válidos na forma das respostas da API", () => {
    const e = montarEspelho({ parciais, projecao, historico }, AGORA);
    expect(e.resultados).toEqual({
      origem: "espelho",
      confirmadoEm: "2026-11-04T02:00:00.000Z",
      parciais,
    });
    expect(e.noite?.historico).toEqual(historico);
    expect(e.rejeitados).toEqual([]);
  });

  it("deixa de fora o que falta ou não cumpre o contrato", () => {
    const e = montarEspelho({ parciais: { unidades: 1 }, projecao: null, historico: null }, AGORA);
    expect(e.resultados).toBeNull();
    expect(e.noite).toBeNull();
    expect(e.rejeitados).toEqual(["ResultadosParciais"]);
  });

  it("o browser vai ao espelho quando a API falha, mas não quando diz 404", async () => {
    const pedidos: string[] = [];
    const corpo = montarEspelho({ parciais, projecao: null, historico: null }, AGORA).resultados;
    const buscar = (estadoApi: number): typeof fetch =>
      ((url: string) => {
        pedidos.push(url);
        return Promise.resolve(
          url.startsWith(URL_ESPELHO)
            ? Response.json(corpo)
            : new Response("", { status: estadoApi }),
        );
      }) as typeof fetch;

    const consulta = await consultarResultados(buscar(429));
    expect(consulta.tipo).toBe("dados");
    expect(pedidos).toEqual(["/api/resultados", `${URL_ESPELHO}/resultados.json`]);

    pedidos.length = 0;
    expect((await consultarResultados(buscar(404))).tipo).toBe("ausente");
    expect(pedidos).toEqual(["/api/resultados"]);

    const vazio: EstadoAoVivo = { dados: null, parciais: null, ligacao: { tipo: "build" } };
    const estado = atualizarEstado(vazio, consulta, { tipo: "ausente" }, null);
    expect(estado.ligacao).toEqual(expect.objectContaining({ tipo: "aoVivo", espelho: true }));
  });
});
