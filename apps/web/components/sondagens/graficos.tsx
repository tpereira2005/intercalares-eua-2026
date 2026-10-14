"use client";

import { Grafico, escala } from "@/components/charts/base.tsx";
import { formatarDataCurta, formatarMargemPontos, formatarMesAno } from "@/lib/formatacao.ts";

const TEXTO_EIXO = "fill-ink-3 font-mono text-[10.5px]";
const UM_DIA = 24 * 60 * 60 * 1000;

function dia(data: string): number {
  return Date.parse(`${data}T12:00:00Z`);
}

/** Eixo comum: datas no x, margem D − R (pontos) no y, de um lado ao outro dos dados e do 0. */
function eixos(
  datas: readonly string[],
  margens: readonly number[],
  largura: number,
  altura: number,
) {
  const m = { esquerda: 46, direita: 14, topo: 10, fundo: 24 };
  const t0 = Math.min(...datas.map(dia));
  const t1 = Math.max(Math.max(...datas.map(dia)), t0 + UM_DIA);
  const { marcas } = escala(Math.max(...margens.map(Math.abs), 2));
  const passo = (marcas[1] ?? 1) - (marcas[0] ?? 0);
  const baixo = Math.min(0, Math.floor(Math.min(...margens) / passo) * passo);
  const cima = Math.max(0, Math.ceil(Math.max(...margens) / passo) * passo);
  const x = (data: string) =>
    m.esquerda + ((largura - m.esquerda - m.direita) * (dia(data) - t0)) / (t1 - t0);
  const y = (v: number) =>
    m.topo + ((altura - m.topo - m.fundo) * (cima - v)) / Math.max(cima - baixo, passo);
  const valores: number[] = [];
  for (let v = baixo; v <= cima + 1e-9; v += passo) valores.push(Number(v.toPrecision(6)));
  return { m, x, y, valores, t0, t1 };
}

/** Rótulo de data: dia e mês, ou mês e ano quando a série passa de seis meses. */
function rotuloData(t: number, longa: boolean): string {
  const d = new Date(t);
  return longa ? formatarMesAno(d) : formatarDataCurta(d);
}

function Eixos({
  e,
  largura,
  altura,
}: {
  e: ReturnType<typeof eixos>;
  largura: number;
  altura: number;
}) {
  const longa = e.t1 - e.t0 > 180 * UM_DIA;
  // Cinco datas igualmente espaçadas; ficam só as que têm pelo menos 80 px entre si.
  const candidatas = Array.from({ length: 5 }, (_, i) => e.t0 + ((e.t1 - e.t0) * i) / 4);
  const px = (t: number) =>
    e.m.esquerda + ((largura - e.m.esquerda - e.m.direita) * (t - e.t0)) / (e.t1 - e.t0);
  const datas = candidatas.reduce<number[]>((escolhidas, t) => {
    const anterior = escolhidas.at(-1);
    return anterior === undefined || px(t) - px(anterior) >= 80 ? [...escolhidas, t] : escolhidas;
  }, []);
  return (
    <g aria-hidden="true">
      {e.valores.map((v) => (
        <g key={v}>
          <line
            x1={e.m.esquerda}
            x2={largura - e.m.direita}
            y1={e.y(v)}
            y2={e.y(v)}
            strokeDasharray={v === 0 ? "3 3" : undefined}
            className={v === 0 ? "stroke-ink-3" : "stroke-rule-2"}
          />
          <text x={e.m.esquerda - 6} y={e.y(v) + 4} textAnchor="end" className={TEXTO_EIXO}>
            {v === 0 ? "0" : formatarMargemPontos(v, 0)}
          </text>
        </g>
      ))}
      {datas.map((d, i) => (
        <text
          key={d}
          x={px(d)}
          y={altura - 6}
          textAnchor={i === 0 ? "start" : i === datas.length - 1 ? "end" : "middle"}
          className={TEXTO_EIXO}
        >
          {rotuloData(d, longa)}
        </text>
      ))}
    </g>
  );
}

/**
 * Média de sondagens de uma corrida ao longo do tempo (linha) e cada sondagem (ponto:
 * cheio se entra na média atual, vazio se já não entra).
 */
export function SerieSondagens({
  titulo,
  serie,
  sondagens,
}: {
  titulo: string;
  serie: readonly { data: string; margem: number }[];
  sondagens: readonly { fim: string; margem: number; peso: number }[];
}) {
  const altura = 220;
  const datas = [...serie.map((p) => p.data), ...sondagens.map((s) => s.fim)];
  if (datas.length === 0) return null;
  const margens = [...serie.map((p) => p.margem), ...sondagens.map((s) => s.margem)];
  return (
    <Grafico titulo={titulo} altura={altura}>
      {(largura) => {
        const e = eixos(datas, margens, largura, altura);
        const caminho = serie
          .map((p, i) => `${i ? "L" : "M"}${e.x(p.data).toFixed(1)},${e.y(p.margem).toFixed(1)}`)
          .join("");
        return (
          <>
            <Eixos e={e} largura={largura} altura={altura} />
            <g aria-hidden="true">
              {sondagens.map((s, i) => (
                <circle
                  key={`${s.fim}-${String(i)}`}
                  cx={e.x(s.fim)}
                  cy={e.y(s.margem)}
                  r={3.5}
                  strokeWidth={1.25}
                  className={s.peso > 0 ? "fill-ink-3 stroke-sheet" : "fill-sheet stroke-ink-3"}
                />
              ))}
              {serie.length > 1 ? (
                <path
                  d={caminho}
                  fill="none"
                  strokeWidth={2.25}
                  strokeLinejoin="round"
                  className="stroke-ink"
                />
              ) : null}
              {serie.at(-1) ? (
                <circle
                  cx={e.x(serie.at(-1)?.data ?? "")}
                  cy={e.y(serie.at(-1)?.margem ?? 0)}
                  r={4.5}
                  className="fill-signal stroke-sheet"
                  strokeWidth={1.5}
                />
              ) : null}
            </g>
          </>
        );
      }}
    </Grafico>
  );
}

/** Voto genérico: média dos agregadores (linha cheia) e cada agregador (linhas finas). */
export function EvolucaoVotoGenerico({
  titulo,
  pontos,
}: {
  titulo: string;
  pontos: readonly {
    data: string;
    margem: number;
    agregadores: readonly { nome: string; margem: number }[];
  }[];
}) {
  const altura = 200;
  if (pontos.length < 2) return null;
  const nomes = [...new Set(pontos.flatMap((p) => p.agregadores.map((a) => a.nome)))];
  const margens = pontos.flatMap((p) => [p.margem, ...p.agregadores.map((a) => a.margem)]);
  return (
    <Grafico titulo={titulo} altura={altura}>
      {(largura) => {
        const e = eixos(
          pontos.map((p) => p.data),
          margens,
          largura,
          altura,
        );
        const linha = (valores: { data: string; margem: number }[]) =>
          valores
            .map((p, i) => `${i ? "L" : "M"}${e.x(p.data).toFixed(1)},${e.y(p.margem).toFixed(1)}`)
            .join("");
        return (
          <>
            <Eixos e={e} largura={largura} altura={altura} />
            <g aria-hidden="true">
              {nomes.map((nome) => (
                <path
                  key={nome}
                  d={linha(
                    pontos.flatMap((p) => {
                      const a = p.agregadores.find((x) => x.nome === nome);
                      return a ? [{ data: p.data, margem: a.margem }] : [];
                    }),
                  )}
                  fill="none"
                  strokeWidth={1.25}
                  className="stroke-ink-3 opacity-60"
                />
              ))}
              <path
                d={linha(pontos.map((p) => ({ data: p.data, margem: p.margem })))}
                fill="none"
                strokeWidth={2.5}
                strokeLinejoin="round"
                className="stroke-ink"
              />
            </g>
          </>
        );
      }}
    </Grafico>
  );
}
