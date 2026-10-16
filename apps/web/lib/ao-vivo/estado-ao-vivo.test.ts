import { readFileSync } from "node:fs";
import type { HistoricoNoite, ProjecaoNoite, ResultadosParciais } from "@intercalares/contratos";
import { describe, expect, it } from "vitest";
import { lerPrevisao } from "../previsao/carregar.ts";
import { construirVistaPrevisao } from "../previsao/vista.ts";
import { previsaoParaResultados } from "../resultados/vista.ts";
import {
  atualizarEstado,
  consultarResultados,
  type Consulta,
  type EstadoAoVivo,
  type RespostaNoite,
  type RespostaResultados,
} from "./estado.ts";

function ler(caminho: string): unknown {
  return JSON.parse(readFileSync(caminho, "utf-8"));
}

const parciais = ler("test/fixtures/resultados/parciais.json") as ResultadosParciais;
const projecao = ler("test/fixtures/noite/projecao.json") as ProjecaoNoite;
const historico = ler("test/fixtures/noite/historico.json") as HistoricoNoite;
const dadosPrevisao = lerPrevisao("test/fixtures/previsao/2026.json");
if (!dadosPrevisao) throw new Error("Falta a previsão de teste");
const previsao = previsaoParaResultados(construirVistaPrevisao(dadosPrevisao));

const VAZIO: EstadoAoVivo = {
  dados: null,
  parciais: null,
  chamadas: null,
  saude: null,
  ligacao: { tipo: "build" },
};
const AUSENTE = { tipo: "ausente" } as const;
const ERRO = { tipo: "erro" } as const;

function resultados(
  origem: RespostaResultados["origem"] = "fonte",
  confirmadoEm = "2026-11-04T01:00:20Z",
): Consulta<RespostaResultados> {
  return { tipo: "dados", dados: { origem, confirmadoEm, parciais } };
}

function noite(confirmadoEm = "2026-11-04T01:00:00Z"): Consulta<RespostaNoite> {
  return { tipo: "dados", dados: { origem: "memoria", confirmadoEm, projecao, historico } };
}

describe("atualizarEstado", () => {
  it("reconstrói as vistas com a contagem e a projeção recebidas", () => {
    const estado = atualizarEstado(VAZIO, resultados(), noite(), previsao);
    expect(estado.dados?.resultados?.instante).toBe(parciais.instante);
    expect(estado.dados?.noite?.instante).toBe(projecao.instante);
    expect(estado.parciais).toBe(parciais);
    // A hora mostrada é a da confirmação mais antiga.
    expect(estado.ligacao).toEqual({
      tipo: "aoVivo",
      confirmadoEm: "2026-11-04T01:00:00Z",
      antiga: false,
      espelho: false,
    });
  });

  it("mantém o que está no ecrã quando a API falha", () => {
    const antes = atualizarEstado(VAZIO, resultados(), noite(), previsao);
    const depois = atualizarEstado(antes, ERRO, ERRO, previsao);
    expect(depois.dados).toBe(antes.dados);
    expect(depois.ligacao).toEqual({ tipo: "falha" });
  });

  it("antes da noite, sem ficheiros publicados, fica com os dados do build", () => {
    const depois = atualizarEstado(VAZIO, AUSENTE, AUSENTE, previsao);
    expect(depois.dados).toBeNull();
    expect(depois.ligacao).toEqual({ tipo: "semDados" });
  });

  it("assinala uma cópia antiga ou uma consulta falhada", () => {
    expect(atualizarEstado(VAZIO, resultados("copia-antiga"), noite(), previsao).ligacao).toEqual(
      expect.objectContaining({ antiga: true }),
    );
    const parcial = atualizarEstado(VAZIO, resultados(), ERRO, previsao);
    expect(parcial.ligacao).toEqual(expect.objectContaining({ tipo: "aoVivo", antiga: true }));
    expect(parcial.dados?.noite).toBeNull();
  });

  it("quando só chega a projeção, recalcula a contagem com a última recebida", () => {
    const antes = atualizarEstado(VAZIO, resultados(), AUSENTE, previsao);
    const depois = atualizarEstado(antes, ERRO, noite(), previsao);
    expect(depois.dados?.resultados?.instante).toBe(parciais.instante);
    expect(depois.dados?.noite).not.toBeNull();
  });
});

describe("consultarResultados", () => {
  function buscar(resposta: Response): typeof fetch {
    return () => Promise.resolve(resposta);
  }

  it("distingue dados, ausência e erro", async () => {
    const corpo = { origem: "fonte", confirmadoEm: "2026-11-04T01:00:00Z", parciais };
    expect((await consultarResultados(buscar(Response.json(corpo)))).tipo).toBe("dados");
    expect((await consultarResultados(buscar(new Response("", { status: 404 })))).tipo).toBe(
      "ausente",
    );
    expect((await consultarResultados(buscar(new Response("", { status: 503 })))).tipo).toBe(
      "erro",
    );
    expect((await consultarResultados(buscar(Response.json({ parciais: 1 })))).tipo).toBe("erro");
    expect((await consultarResultados(() => Promise.reject(new Error("rede")))).tipo).toBe("erro");
  });
});
