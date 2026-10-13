import { readFileSync } from "node:fs";
import type { VotoAntecipadoEstado } from "@intercalares/contratos";
import { describe, expect, it } from "vitest";
import { DIAS_CURVA, FAIXAS, construirVista } from "./vista.ts";

const dados = JSON.parse(
  readFileSync("test/fixtures/voto-antecipado-sintetico.json", "utf-8"),
) as VotoAntecipadoEstado;
const vista = construirVista(dados);

describe("construirVista", () => {
  it("ordena as comparações: intercalares mais recentes primeiro, depois presidenciais", () => {
    expect(vista.comparacoes.map((c) => c.anoBase)).toEqual([2022, 2018, 2024]);
    for (const comparacao of vista.comparacoes) {
      expect(comparacao.faixas.map((f) => f.faixa)).toEqual(FAIXAS);
    }
  });

  it("mantém a decomposição exata da variação da quota", () => {
    for (const { faixas } of vista.comparacoes) {
      for (const f of faixas) {
        expect(f.efeitoRecenseamento + f.efeitoParticipacao).toBeCloseTo(f.quota - f.quotaBase, 4);
      }
    }
  });

  it("divide os votos de cada faixa por momento do voto, com quotas que somam 1", () => {
    expect(vista.momento[0]?.ano).toBe(2026);
    expect(vista.momento[0]?.anoReferencia).toBe(2022);
    for (const { faixas } of vista.momento) {
      for (const f of faixas) {
        expect(f.habituais + f.antecipacao + f.novos).toBeCloseTo(1, 10);
      }
    }
  });

  it("constrói curvas acumuladas por ano, dentro da janela e sem descer", () => {
    expect(vista.curvas.total.map((c) => c.ano)).toEqual([2026, 2024, 2022, 2018]);
    for (const curvas of Object.values(vista.curvas)) {
      for (const { pontos } of curvas) {
        expect(pontos.length).toBeGreaterThan(0);
        expect(pontos.every((p) => p.dias >= 0 && p.dias <= DIAS_CURVA)).toBe(true);
        for (let i = 1; i < pontos.length; i++) {
          expect(pontos[i]?.dias).toBeLessThan(pontos[i - 1]?.dias ?? Infinity);
        }
      }
    }
    const atual = vista.curvas.total[0]?.pontos;
    expect(atual?.at(-1)?.dias).toBe(vista.diasAntes);
  });

  it("calcula quotas partidárias que somam 1 e a reserva face ao ano principal", () => {
    for (const c of vista.cruzamentos) {
      const soma = c.partidos.dem + c.partidos.rep + c.partidos.nao_afiliado + c.partidos.outro;
      expect(soma).toBeCloseTo(1, 10);
      expect(c.correio).not.toBeNull();
    }
    expect(vista.reserva.anoBase).toBe(2022);
    for (const p of vista.reserva.partidos) {
      expect(p.jaVotaram + p.restantes).toBe(p.habituais);
    }
  });

  it("trata os partidos de forma simétrica: trocar D e R troca os resultados", () => {
    const trocar = <T extends string>(valor: T): T =>
      (valor === "dem" ? "rep" : valor === "rep" ? "dem" : valor) as T;
    const trocados: VotoAntecipadoEstado = {
      ...dados,
      reserva: dados.reserva.map((l) => ({ ...l, partido: trocar(l.partido) })),
      cruzamentos: dados.cruzamentos.map((l) =>
        l.dimensao === "partido" ? { ...l, categoria: trocar(l.categoria) } : l,
      ),
    };
    const espelho = construirVista(trocados);
    vista.cruzamentos.forEach((c, i) => {
      const e = espelho.cruzamentos[i];
      expect(e?.partidos.dem).toBeCloseTo(c.partidos.rep, 12);
      expect(e?.partidos.rep).toBeCloseTo(c.partidos.dem, 12);
      expect(e?.variacaoDemRep).toBeCloseTo(-(c.variacaoDemRep ?? 0), 12);
    });
    const porPartido = (v: typeof vista, p: string) =>
      v.reserva.partidos.find((r) => r.partido === p);
    expect(porPartido(espelho, "dem")).toEqual({ ...porPartido(vista, "rep"), partido: "dem" });
    expect(porPartido(espelho, "rep")).toEqual({ ...porPartido(vista, "dem"), partido: "rep" });
  });

  it("aceita o ficheiro real com a faixa desconhecida, que fica fora dos gráficos", () => {
    const primeira = dados.comparacao[0];
    if (!primeira) throw new Error("fixture sem comparações");
    const comDesconhecida: VotoAntecipadoEstado = {
      ...dados,
      comparacao: [...dados.comparacao, { ...primeira, faixa: "desconhecida", desvio: null }],
    };
    const v = construirVista(comDesconhecida);
    expect(v.comparacoes[0]?.faixas.map((f) => f.faixa)).toEqual(FAIXAS);
  });
});
