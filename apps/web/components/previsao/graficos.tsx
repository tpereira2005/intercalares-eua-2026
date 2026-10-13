"use client";

import { Grafico, HALO } from "@/components/charts/base.tsx";
import { COLUNAS_GRELHA, ESTADOS, LINHAS_GRELHA } from "@/lib/estados.ts";
import {
  formatarDataCurta,
  formatarHora,
  formatarMargemPontos as margem,
  formatarNumero,
  formatarPercentagem,
} from "@/lib/formatacao.ts";
import { t } from "@/lib/mensagens.ts";
import type { CorridaVista, PontoEvolucao, ResumoVista } from "@/lib/previsao/vista.ts";

const TEXTO_EIXO = "fill-ink-3 font-mono text-[10.5px]";
const REP = { fill: "url(#padrao-rep)" } as const;

/** Um dia ("2026-10-13") ao meio-dia UTC, ou um instante ISO com hora tal como vem. */
function data(dia: string): Date {
  return new Date(dia.includes("T") ? dia : `${dia}T12:00:00Z`);
}

/** Marcas redondas entre dois valores, com no máximo `n` divisões. */
function marcasEntre(de: number, ate: number, n = 6): number[] {
  const bruto = (ate - de) / n;
  const potencia = 10 ** Math.floor(Math.log10(Math.max(bruto, 1e-9)));
  const passo = [1, 2, 2.5, 5, 10].map((m) => m * potencia).find((p) => p >= bruto) ?? bruto;
  const inicio = Math.ceil(de / passo) * passo;
  return Array.from(
    { length: Math.floor((ate - inicio) / passo + 1e-9) + 1 },
    (_, i) => inicio + i * passo,
  );
}

/**
 * Histograma dos lugares democratas: barras azuis quando dão maioria
 * democrata, tracejado republicano quando não dão, faixa do intervalo de 80%
 * e linha da maioria.
 */
export function DistribuicaoLugares({
  resumo,
}: {
  resumo: Pick<ResumoVista, "camara" | "distribuicao" | "maioria" | "mediana" | "p10" | "p90">;
}) {
  const altura = 200;
  const m = { esquerda: 8, direita: 8, topo: 26, fundo: 26 };
  const pontos = resumo.distribuicao;
  const de = Math.min(pontos[0]?.lugares ?? resumo.p10, resumo.maioria - 1);
  const ate = Math.max(pontos.at(-1)?.lugares ?? resumo.p90, resumo.maioria);
  const maximo = Math.max(...pontos.map((p) => p.probabilidade), 1e-6);
  return (
    <Grafico
      titulo={t("previsao.lugares.aria", {
        camara: t(`previsao.camaraNa.${resumo.camara}`),
        mediana: resumo.mediana,
        de: resumo.p10,
        ate: resumo.p90,
        maioria: resumo.maioria,
      })}
      altura={altura}
    >
      {(largura) => {
        const passo = (largura - m.esquerda - m.direita) / (ate - de + 1);
        const x = (lugares: number) => m.esquerda + (lugares - de) * passo;
        const y = (p: number) => m.topo + (altura - m.topo - m.fundo) * (1 - p / maximo);
        const base = altura - m.fundo;
        const marcas = marcasEntre(de, ate, largura < 420 ? 4 : 7).filter(
          (v) => Number.isInteger(v) && Math.abs(v - resumo.maioria) * passo > 34,
        );
        const xMaioria = x(resumo.maioria);
        return (
          <>
            <g aria-hidden="true">
              <rect
                x={x(resumo.p10)}
                y={m.topo - 8}
                width={x(resumo.p90 + 1) - x(resumo.p10)}
                height={base - m.topo + 8}
                className="fill-rule-2"
              />
            </g>
            <g aria-hidden="true">
              {pontos.map((p) => {
                const topo = y(p.probabilidade);
                return (
                  <rect
                    key={p.lugares}
                    x={x(p.lugares) + (passo > 3 ? 0.5 : 0)}
                    y={topo}
                    width={Math.max(0.8, passo - (passo > 3 ? 1 : 0))}
                    height={Math.max(0, base - topo)}
                    {...(p.lugares >= resumo.maioria ? { className: "fill-dem" } : { style: REP })}
                  />
                );
              })}
            </g>
            <g aria-hidden="true">
              <line
                x1={m.esquerda}
                x2={largura - m.direita}
                y1={base}
                y2={base}
                className="stroke-ink-3"
              />
              <line
                x1={xMaioria}
                x2={xMaioria}
                y1={m.topo - 18}
                y2={base + 4}
                strokeWidth={1.5}
                className="stroke-ink"
              />
              <text
                x={xMaioria}
                y={m.topo - 20}
                textAnchor="middle"
                style={HALO}
                className="fill-ink font-mono text-[10.5px] font-semibold"
              >
                {t("previsao.lugares.maioria", { lugares: resumo.maioria })}
              </text>
              <line
                x1={x(resumo.mediana) + passo / 2}
                x2={x(resumo.mediana) + passo / 2}
                y1={base}
                y2={base + 6}
                strokeWidth={2}
                className="stroke-ink"
              />
              {marcas.map((v) => (
                <text
                  key={v}
                  x={x(v) + passo / 2}
                  y={altura - 6}
                  textAnchor="middle"
                  className={TEXTO_EIXO}
                >
                  {formatarNumero(v)}
                </text>
              ))}
              <text x={xMaioria} y={altura - 6} textAnchor="middle" className={TEXTO_EIXO}>
                {formatarNumero(resumo.maioria)}
              </text>
            </g>
          </>
        );
      }}
    </Grafico>
  );
}

function textoLimiar(
  limiares: readonly { camara: "camara" | "senado"; valor: number | null }[],
  camara: "camara" | "senado",
): string {
  const valor = limiares.find((l) => l.camara === camara)?.valor ?? null;
  return valor === null ? t("comum.semDados") : margem(valor);
}

/**
 * Linha do voto genérico: intervalo de 80% do ambiente, valor previsto,
 * agregadores e o limiar de cada câmara.
 */
export function LinhaLimiares({
  ambiente,
  limiares,
}: {
  ambiente: {
    margem: number;
    p10: number;
    p90: number;
    agregadores: { nome: string; margem: number }[];
  };
  limiares: { camara: "camara" | "senado"; valor: number | null }[];
}) {
  const valores = [
    ambiente.p10,
    ambiente.p90,
    0,
    ...ambiente.agregadores.map((a) => a.margem),
    ...limiares.flatMap((l) => (l.valor === null ? [] : [l.valor])),
  ];
  const de = Math.floor((Math.min(...valores) - 1) / 2) * 2;
  const ate = Math.ceil((Math.max(...valores) + 1) / 2) * 2;
  const altura = 150;
  const m = { esquerda: 14, direita: 14 };
  const eixoY = 104;
  const definidos = limiares.flatMap((l) => (l.valor === null ? [] : [{ ...l, valor: l.valor }]));
  return (
    <Grafico
      titulo={t("previsao.limiares.aria", {
        ambiente: margem(ambiente.margem),
        de: margem(ambiente.p10),
        ate: margem(ambiente.p90),
        camara: textoLimiar(limiares, "camara"),
        senado: textoLimiar(limiares, "senado"),
      })}
      altura={altura}
    >
      {(largura) => {
        const x = (v: number) =>
          m.esquerda + ((largura - m.esquerda - m.direita) * (v - de)) / (ate - de);
        const marcas = marcasEntre(de, ate, largura < 420 ? 4 : 8);
        // Rótulos dos limiares em linhas diferentes quando estão próximos.
        const ordenados = [...definidos].sort((a, b) => a.valor - b.valor);
        const proximos =
          ordenados.length === 2 &&
          Math.abs(x(ordenados[0]?.valor ?? 0) - x(ordenados[1]?.valor ?? 0)) < 120;
        return (
          <g aria-hidden="true">
            <rect
              x={x(ambiente.p10)}
              y={eixoY - 16}
              width={x(ambiente.p90) - x(ambiente.p10)}
              height={32}
              rx={3}
              className="fill-rule-2"
            />
            <line
              x1={m.esquerda}
              x2={largura - m.direita}
              y1={eixoY}
              y2={eixoY}
              className="stroke-ink-3"
            />
            <line
              x1={x(0)}
              x2={x(0)}
              y1={eixoY - 22}
              y2={eixoY + 22}
              strokeDasharray="2 3"
              className="stroke-ink-3"
            />
            {ambiente.agregadores.map((a) => (
              <circle
                key={a.nome}
                cx={x(a.margem)}
                cy={eixoY}
                r={3}
                className="fill-sheet stroke-ink-2"
              />
            ))}
            <circle
              cx={x(ambiente.margem)}
              cy={eixoY}
              r={6}
              className="fill-ink stroke-sheet"
              strokeWidth={2}
            />
            <text
              x={x(ambiente.margem)}
              y={eixoY + 32}
              textAnchor="middle"
              style={HALO}
              className="fill-ink font-mono text-[11px] font-semibold"
            >
              {t("previsao.limiares.previsto")} {margem(ambiente.margem)}
            </text>
            {ordenados.map((l, i) => {
              const linha = proximos ? i : 0;
              const topo = 18 + linha * 30;
              const xv = x(l.valor);
              const ancora = xv > largura - 90 ? "end" : xv < 90 ? "start" : "middle";
              return (
                <g key={l.camara}>
                  <line
                    x1={xv}
                    x2={xv}
                    y1={topo + 6}
                    y2={eixoY + 16}
                    strokeWidth={2}
                    className="stroke-ink"
                  />
                  <text
                    x={xv}
                    y={topo}
                    textAnchor={ancora}
                    style={HALO}
                    className="fill-ink text-[12px] font-semibold"
                  >
                    {t("previsao.limiares.limiar", {
                      camara: t(`previsao.camaraDa.${l.camara}`),
                    })}
                  </text>
                  <text
                    x={xv}
                    y={topo + 13}
                    textAnchor={ancora}
                    style={HALO}
                    className="fill-ink-2 font-mono text-[10.5px]"
                  >
                    {margem(l.valor)}
                  </text>
                </g>
              );
            })}
            {marcas.map((v) => (
              <text key={v} x={x(v)} y={altura - 2} textAnchor="middle" className={TEXTO_EIXO}>
                {margem(v, 0)}
              </text>
            ))}
          </g>
        );
      }}
    </Grafico>
  );
}

const ESPACO = 4;

function ladoQuadrado(largura: number): number {
  return Math.min(56, Math.floor((largura - ESPACO * (COLUNAS_GRELHA - 1)) / COLUNAS_GRELHA));
}

/**
 * Mapa em grelha das corridas ao Senado: azul mais forte quanto mais provável
 * a vitória democrata, tracejado republicano mais opaco quanto mais provável a
 * republicana. Estados sem eleição ficam vazios. A tabela ao lado tem os
 * mesmos dados em texto.
 */
export function MapaSenado({ corridas }: { corridas: readonly CorridaVista[] }) {
  const porEstado = new Map(corridas.map((c) => [c.estado, c]));
  return (
    <Grafico
      titulo={t("previsao.senado.aria")}
      altura={0}
      alturaPorLargura={(l) => LINHAS_GRELHA * (ladoQuadrado(l) + ESPACO)}
    >
      {(largura) => {
        const lado = ladoQuadrado(largura);
        const deslocamento = Math.floor(
          (largura - (COLUNAS_GRELHA * lado + (COLUNAS_GRELHA - 1) * ESPACO)) / 2,
        );
        return ESTADOS.map((e) => {
          const x = deslocamento + e.coluna * (lado + ESPACO);
          const y = e.linha * (lado + ESPACO);
          const c = porEstado.get(e.codigo);
          if (!c) {
            return (
              <g key={e.codigo} aria-hidden="true">
                <rect
                  x={x}
                  y={y}
                  width={lado}
                  height={lado}
                  rx={3}
                  className="fill-sheet stroke-rule"
                />
                <text
                  x={x + 6}
                  y={y + (lado < 34 ? 13 : 16)}
                  className={`fill-ink-3 font-mono ${lado < 34 ? "text-[9.5px]" : "text-[12px]"}`}
                >
                  {e.codigo}
                </text>
              </g>
            );
          }
          const democrata = c.probD >= 0.5;
          const forca = Math.min(1, Math.abs(c.probD - 0.5) * 2);
          const forte = forca > 0.55;
          const prob = democrata ? c.probD : 1 - c.probD;
          return (
            <g key={e.codigo}>
              <title>{`${e.nome}: ${democrata ? "D" : "R"} ${formatarPercentagem(prob, 0)}`}</title>
              <rect x={x} y={y} width={lado} height={lado} rx={3} className="fill-sheet" />
              {democrata ? (
                <rect
                  x={x}
                  y={y}
                  width={lado}
                  height={lado}
                  rx={3}
                  style={{
                    fill: `color-mix(in oklab, var(--dem) ${String(Math.round(12 + forca * 78))}%, var(--sheet))`,
                  }}
                />
              ) : (
                <rect
                  x={x}
                  y={y}
                  width={lado}
                  height={lado}
                  rx={3}
                  opacity={0.18 + forca * 0.82}
                  style={REP}
                />
              )}
              <text
                x={x + 6}
                y={y + (lado < 34 ? 13 : 16)}
                style={forte && !democrata ? HALO : undefined}
                className={`font-mono font-bold ${forte && democrata ? "fill-sheet" : "fill-ink"} ${lado < 34 ? "text-[9.5px]" : "text-[12px]"}`}
              >
                {e.codigo}
              </text>
              {lado >= 40 ? (
                <text
                  x={x + 6}
                  y={y + lado - 8}
                  style={forte && !democrata ? HALO : undefined}
                  className={`font-mono text-[10.5px] ${forte && democrata ? "fill-sheet" : "fill-ink"}`}
                >
                  {`${democrata ? "D" : "R"} ${formatarPercentagem(prob, 0)}`}
                </text>
              ) : null}
            </g>
          );
        });
      }}
    </Grafico>
  );
}

/**
 * Evolução da probabilidade de controlo de uma câmara: linha azul cheia para
 * o lado democrata, vermelha tracejada para o republicano. O último dia fica
 * marcado a ocre.
 */
export function EvolucaoControlo({
  pontos,
  titulo,
  escala = "dia",
}: {
  /** `corte` é um dia ("2026-10-13") ou um instante ISO com hora (noite eleitoral). */
  pontos: readonly PontoEvolucao[];
  titulo: string;
  /** Rótulos do eixo: data curta ("13 out.") ou hora de Nova Iorque ("21:34"). */
  escala?: "dia" | "hora";
}) {
  const rotuloTempo = escala === "hora" ? formatarHora : formatarDataCurta;
  const altura = 180;
  const m = { esquerda: 38, direita: 50, topo: 10, fundo: 24 };
  const primeiro = pontos[0];
  const ultimo = pontos.at(-1);
  if (!primeiro || !ultimo) return null;
  const t0 = data(primeiro.corte).getTime();
  const t1 = Math.max(data(ultimo.corte).getTime(), t0 + 1);
  return (
    <Grafico titulo={titulo} altura={altura}>
      {(largura) => {
        const x = (dia: string) =>
          m.esquerda +
          ((largura - m.esquerda - m.direita) * (data(dia).getTime() - t0)) / (t1 - t0);
        const y = (p: number) => m.topo + (altura - m.topo - m.fundo) * (1 - p);
        const caminho = (valor: (p: PontoEvolucao) => number) =>
          pontos
            .map((p, i) => `${i ? "L" : "M"}${x(p.corte).toFixed(1)},${y(valor(p)).toFixed(1)}`)
            .join("");
        // Datas com pelo menos 80 px entre si; a mais recente fica sempre.
        const datas = pontos.reduceRight<PontoEvolucao[]>((escolhidas, p) => {
          const seguinte = escolhidas[0];
          return !seguinte || x(seguinte.corte) - x(p.corte) >= 80
            ? [p, ...escolhidas]
            : escolhidas;
        }, []);
        const rotulos = [
          { lado: "D", valor: ultimo.probD },
          { lado: "R", valor: ultimo.probR },
        ];
        const yD = y(ultimo.probD) + 4;
        const yR = y(ultimo.probR) + 4;
        const afastar = Math.abs(yD - yR) < 12 ? (yD < yR ? [-6, 6] : [6, -6]) : [0, 0];
        return (
          <>
            <g aria-hidden="true">
              {[0, 0.25, 0.5, 0.75, 1].map((v) => (
                <g key={v}>
                  <line
                    x1={m.esquerda}
                    x2={largura - m.direita}
                    y1={y(v)}
                    y2={y(v)}
                    strokeDasharray={v === 0.5 ? "3 3" : undefined}
                    className={v === 0.5 ? "stroke-ink-3" : "stroke-rule-2"}
                  />
                  <text x={m.esquerda - 6} y={y(v) + 4} textAnchor="end" className={TEXTO_EIXO}>
                    {formatarPercentagem(v, 0)}
                  </text>
                </g>
              ))}
              {datas.map((p, i) => (
                <text
                  key={p.corte}
                  x={x(p.corte)}
                  y={altura - 6}
                  textAnchor={
                    i === 0 && datas.length > 1
                      ? "start"
                      : i === datas.length - 1
                        ? "end"
                        : "middle"
                  }
                  className={TEXTO_EIXO}
                >
                  {rotuloTempo(data(p.corte))}
                </text>
              ))}
              <line
                x1={x(ultimo.corte)}
                x2={x(ultimo.corte)}
                y1={m.topo}
                y2={altura - m.fundo}
                strokeDasharray="2 3"
                className="stroke-signal"
              />
            </g>
            <g aria-hidden="true">
              <path
                d={caminho((p) => p.probR)}
                fill="none"
                strokeWidth={2.25}
                strokeDasharray="5 3"
                strokeLinejoin="round"
                className="stroke-rep"
              />
              <path
                d={caminho((p) => p.probD)}
                fill="none"
                strokeWidth={2.25}
                strokeLinejoin="round"
                className="stroke-dem"
              />
              {pontos.length === 1 ? (
                <>
                  <circle cx={x(ultimo.corte)} cy={y(ultimo.probD)} r={3.5} className="fill-dem" />
                  <circle cx={x(ultimo.corte)} cy={y(ultimo.probR)} r={3.5} className="fill-rep" />
                </>
              ) : null}
              {rotulos.map((r, i) => (
                <text
                  key={r.lado}
                  x={largura - m.direita + 6}
                  y={(r.lado === "D" ? yD : yR) + (afastar[i] ?? 0)}
                  className={`font-mono text-[11px] font-semibold ${r.lado === "D" ? "fill-dem" : "fill-rep"}`}
                >
                  {`${r.lado} ${formatarPercentagem(r.valor, 0)}`}
                </text>
              ))}
            </g>
          </>
        );
      }}
    </Grafico>
  );
}
