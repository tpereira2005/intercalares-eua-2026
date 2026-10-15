"use client";

import { Grafico, HALO, escala } from "@/components/charts/base.tsx";
import { formatarPercentagem, formatarPontos, formatarVariacao } from "@/lib/formatacao.ts";

const TEXTO_EIXO = "fill-ink-3 font-mono text-[10.5px]";

export interface LinhaHaltere {
  rotulo: string;
  quota: number;
  quotaBase: number;
}

/**
 * Quota de um grupo em cada estado: círculo vazio no ano de referência, círculo ocre em
 * 2026, ligados por um traço. O valor de 2026 fica à direita.
 */
export function Halteres({ titulo, linhas }: { titulo: string; linhas: readonly LinhaHaltere[] }) {
  const alturaLinha = 44;
  const topo = 20;
  const altura = topo + linhas.length * alturaLinha + 4;
  const { maximo, marcas } = escala(
    Math.max(...linhas.flatMap((l) => [l.quota, l.quotaBase]), 0.01),
  );
  return (
    <Grafico titulo={titulo} altura={altura}>
      {(largura) => {
        const x0 = 6;
        const x1 = largura - 112;
        const x = (v: number) => x0 + ((x1 - x0) * v) / maximo;
        return (
          <g aria-hidden="true">
            {marcas.map((m) => (
              <g key={m}>
                <line x1={x(m)} x2={x(m)} y1={topo - 4} y2={altura - 4} className="stroke-rule-2" />
                <text x={x(m)} y={12} textAnchor="middle" className={TEXTO_EIXO}>
                  {formatarPercentagem(m, Number.isInteger(Math.round(m * 1e6) / 1e4) ? 0 : 1)}
                </text>
              </g>
            ))}
            {linhas.map((l, i) => {
              const y = topo + i * alturaLinha + 30;
              const variacao = l.quota - l.quotaBase;
              return (
                <g key={l.rotulo}>
                  <text x={0} y={y - 13} className="fill-ink text-[12.5px] font-medium">
                    {l.rotulo}
                  </text>
                  <line
                    x1={x(l.quotaBase)}
                    x2={x(l.quota)}
                    y1={y}
                    y2={y}
                    strokeWidth={2}
                    className="stroke-ink-3"
                  />
                  <circle
                    cx={x(l.quotaBase)}
                    cy={y}
                    r={4.5}
                    strokeWidth={1.75}
                    className="fill-sheet stroke-ink-2"
                  />
                  <circle cx={x(l.quota)} cy={y} r={5.5} className="fill-signal stroke-sheet" />
                  <text
                    x={x1 + 10}
                    y={y + 4}
                    className="fill-ink font-mono text-[12px] font-semibold"
                  >
                    {formatarPercentagem(l.quota, 1)}
                    <tspan className="fill-ink-3 font-normal">
                      {` ${formatarPontos(variacao)}`}
                    </tspan>
                  </text>
                </g>
              );
            })}
          </g>
        );
      }}
    </Grafico>
  );
}

export interface GrupoDesvio {
  rotulo: string;
  valores: { chave: string; rotulo: string; valor: number | null }[];
}

/** Desvio face ao esperado: barras divergentes, acima (up) à direita e abaixo (down) à esquerda. */
export function DesvioEstados({
  titulo,
  grupos,
}: {
  titulo: string;
  grupos: readonly GrupoDesvio[];
}) {
  const alturaLinha = 26;
  const cabecaGrupo = 22;
  const topo = 20;
  const linhas = grupos.reduce((n, g) => n + g.valores.length, 0);
  const altura = topo + grupos.length * cabecaGrupo + linhas * alturaLinha + 4;
  const { maximo: extremo, marcas } = escala(
    Math.max(...grupos.flatMap((g) => g.valores.map((v) => Math.abs(v.valor ?? 0))), 0.05),
  );
  const positivas = marcas.filter((_, i) => i > 0 && (marcas.length <= 4 || i % 2 === 0));
  return (
    <Grafico titulo={titulo} altura={altura}>
      {(largura) => {
        const esquerda = 64;
        const x1 = largura - 52;
        const x = (v: number) => esquerda + ((x1 - esquerda) * (v + extremo)) / (2 * extremo);
        let y = topo;
        return (
          <g aria-hidden="true">
            {[...positivas.map((m) => -m), 0, ...positivas].map((m) => (
              <g key={m}>
                <line
                  x1={x(m)}
                  x2={x(m)}
                  y1={topo - 4}
                  y2={altura - 4}
                  strokeDasharray={m === 0 ? undefined : "2 3"}
                  className={m === 0 ? "stroke-ink-3" : "stroke-rule-2"}
                />
                <text x={x(m)} y={12} textAnchor="middle" className={TEXTO_EIXO}>
                  {m === 0 ? "0" : formatarVariacao(m)}
                </text>
              </g>
            ))}
            {grupos.map((g) => {
              const inicio = y;
              y += cabecaGrupo;
              return (
                <g key={g.rotulo}>
                  <text x={0} y={inicio + 15} className="fill-ink text-[13px] font-semibold">
                    {g.rotulo}
                  </text>
                  {g.valores.map((v) => {
                    const centro = y + alturaLinha / 2;
                    y += alturaLinha;
                    const valor = v.valor;
                    return (
                      <g key={v.chave}>
                        <text x={8} y={centro + 4} className="fill-ink-2 text-[12px]">
                          {v.rotulo}
                        </text>
                        {valor === null ? null : (
                          <>
                            <rect
                              x={Math.min(x(0), x(valor))}
                              y={centro - 7}
                              width={Math.abs(x(valor) - x(0))}
                              height={14}
                              className={valor >= 0 ? "fill-up" : "fill-down"}
                            />
                            <text
                              x={largura - 2}
                              y={centro + 4}
                              textAnchor="end"
                              className="fill-ink font-mono text-[11px] font-semibold"
                            >
                              {formatarVariacao(valor)}
                            </text>
                          </>
                        )}
                      </g>
                    );
                  })}
                </g>
              );
            })}
          </g>
        );
      }}
    </Grafico>
  );
}

export interface LinhaMomento {
  chave: string;
  rotulo: string;
  /** Linha do ano de referência, mais discreta, por baixo da de 2026. */
  secundaria: boolean;
  habituais: number;
  antecipacao: number;
  novos: number;
}

export interface GrupoMomento {
  rotulo: string;
  linhas: LinhaMomento[];
}

/** Barras 100% dos três grupos do momento do voto, por estado. */
export function MomentoEstados({
  titulo,
  grupos,
}: {
  titulo: string;
  grupos: readonly GrupoMomento[];
}) {
  const alturaLinha = 26;
  const cabecaGrupo = 22;
  const altura =
    grupos.length * cabecaGrupo + grupos.reduce((n, g) => n + g.linhas.length, 0) * alturaLinha + 4;
  return (
    <Grafico titulo={titulo} altura={altura}>
      {(largura) => {
        const esquerda = 92;
        const util = largura - 8 - esquerda;
        let y = 0;
        return (
          <g aria-hidden="true">
            {grupos.map((g) => {
              const inicio = y;
              y += cabecaGrupo;
              return (
                <g key={g.rotulo}>
                  <text x={0} y={inicio + 15} className="fill-ink text-[13px] font-semibold">
                    {g.rotulo}
                  </text>
                  {g.linhas.map((l) => {
                    const centro = y + alturaLinha / 2;
                    y += alturaLinha;
                    const partes = [
                      { chave: "habituais", valor: l.habituais, classe: "fill-ink-3 opacity-45" },
                      {
                        chave: "antecipacao",
                        valor: l.antecipacao,
                        fill: "url(#padrao-antecipacao)",
                      },
                      { chave: "novos", valor: l.novos, classe: "fill-up" },
                    ] as const;
                    let x = esquerda;
                    return (
                      <g key={l.chave}>
                        <text
                          x={8}
                          y={centro + 4}
                          className={
                            l.secundaria
                              ? "fill-ink-3 font-mono text-[11px]"
                              : "fill-ink-2 text-[12px]"
                          }
                        >
                          {l.rotulo}
                        </text>
                        {/* O esbatimento só nas barras: o rótulo mantém o contraste (1.4.3). */}
                        {partes.map((p) => {
                          const w = util * p.valor;
                          const comeco = x;
                          x += w;
                          return (
                            <g key={p.chave}>
                              <rect
                                opacity={l.secundaria ? 0.75 : 1}
                                x={comeco}
                                y={centro - (l.secundaria ? 5 : 8)}
                                width={Math.max(0, w - 1)}
                                height={l.secundaria ? 10 : 16}
                                className={"classe" in p ? p.classe : undefined}
                                fill={"fill" in p ? p.fill : undefined}
                              />
                              {w > 34 && !l.secundaria ? (
                                <text
                                  x={comeco + w / 2}
                                  y={centro + 4}
                                  textAnchor="middle"
                                  style={HALO}
                                  className="fill-ink text-[11px] font-semibold"
                                >
                                  {formatarPercentagem(p.valor, 0)}
                                </text>
                              ) : null}
                            </g>
                          );
                        })}
                      </g>
                    );
                  })}
                </g>
              );
            })}
          </g>
        );
      }}
    </Grafico>
  );
}
