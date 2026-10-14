"use client";

import Link from "next/link";
import { useState } from "react";
import { Grafico, escala, linhaEscolhivel } from "@/components/charts/base.tsx";
import { ControloSegmentado } from "@/components/ui/ControloSegmentado.tsx";
import { QualidadeDados } from "@/components/ui/QualidadeDados.tsx";
import { COLUNAS_GRELHA, ESTADOS, LINHAS_GRELHA, nomeEstado } from "@/lib/estados.ts";
import {
  formatarData,
  formatarDiaCiclo,
  formatarMargem,
  formatarNumero,
  formatarPercentagem,
  formatarVariacao,
} from "@/lib/formatacao.ts";
import { t } from "@/lib/mensagens.ts";
import type { ResumoEstado } from "@/lib/voto-antecipado/resumo.ts";

/** Estado prioritário sem dados, e porquê (resumo nacional do pipeline). */
export interface EstadoForaMapa {
  estado: ResumoEstado["estado"];
  motivo: "bloqueado" | "sem_fonte_gratuita";
  nota: string;
}

type Indicador = "ritmo" | "partido" | "todos" | "mais65" | "jovens";

function valorDe(r: ResumoEstado, indicador: Indicador): number | null {
  if (indicador === "ritmo") return r.variacaoVotos;
  if (indicador === "partido") {
    // Deslocação da vantagem D−R entre quem já votou face ao mesmo dia de referência.
    return r.vantagemDemRep === null || r.vantagemDemRepBase === null
      ? null
      : r.vantagemDemRep - r.vantagemDemRepBase;
  }
  return r.desvio[indicador];
}

function formatarValor(valor: number, indicador: Indicador): string {
  return indicador === "partido" ? formatarMargem(valor) : formatarVariacao(valor);
}

const ESPACO = 4;

/**
 * Cor de um quadrado, mais forte quanto maior o valor: verde-azulado acima do esperado e
 * violeta abaixo; no indicador partidário, azul para D e vermelho tracejado para R.
 */
function preenchimento(
  valor: number,
  extremo: number,
  indicador: Indicador,
): { fill: string; forte: boolean; padraoRep: number } {
  const intensidade = Math.min(1, Math.abs(valor) / extremo);
  const partido = indicador === "partido";
  const cor = partido
    ? valor >= 0
      ? "var(--dem)"
      : "var(--rep)"
    : valor >= 0
      ? "var(--up)"
      : "var(--down)";
  return {
    fill: `color-mix(in oklab, ${cor} ${String(Math.round(intensidade * 85))}%, var(--rule-2))`,
    forte: intensidade > 0.55,
    padraoRep: partido && valor < 0 ? intensidade : 0,
  };
}

export function MapaEstados({
  resumos,
  caminhos,
  fora = [],
}: {
  resumos: readonly ResumoEstado[];
  /** Endereço da análise de cada estado com dados. */
  caminhos: Readonly<Record<string, string>>;
  /** Estados prioritários que ficam de fora: riscados, com a explicação ao escolher. */
  fora?: readonly EstadoForaMapa[];
}) {
  const [indicador, setIndicador] = useState<Indicador>("ritmo");
  const [escolhido, setEscolhido] = useState<string>(resumos[0]?.estado ?? "NC");
  const porEstado = new Map(resumos.map((r) => [r.estado, r]));
  const foraPorEstado = new Map(fora.map((f) => [f.estado, f]));
  const valores = resumos.flatMap((r) => {
    const v = valorDe(r, indicador);
    return v === null ? [] : [Math.abs(v)];
  });
  const extremo = escala(Math.max(indicador === "partido" ? 0.05 : 0.1, ...valores)).maximo;
  const resumo = porEstado.get(escolhido as ResumoEstado["estado"]);
  const foraEscolhido = foraPorEstado.get(escolhido as ResumoEstado["estado"]);
  const anoBase = resumos.find((r) => r.anoBase !== null)?.anoBase ?? 2022;

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-end gap-x-6 gap-y-3 rounded-md border border-rule bg-sheet px-[18px] py-3">
        <div className="flex flex-col gap-1.5">
          <span className="rotulo">{t("mapa.indicador")}</span>
          <ControloSegmentado<Indicador>
            rotuloGrupo={t("mapa.indicador")}
            valor={indicador}
            aoMudar={setIndicador}
            opcoes={[
              { valor: "ritmo", rotulo: t("mapa.indicadores.ritmo") },
              { valor: "partido", rotulo: t("mapa.indicadores.partido") },
              { valor: "todos", rotulo: t("mapa.indicadores.todos") },
              { valor: "mais65", rotulo: t("mapa.indicadores.mais65") },
              { valor: "jovens", rotulo: t("mapa.indicadores.jovens") },
            ]}
          />
        </div>
        <div className="flex items-center gap-2 font-mono text-[11px] text-ink-3">
          <span>{formatarValor(-extremo, indicador)}</span>
          <span
            aria-hidden="true"
            className={`inline-block h-2.5 w-28 rounded-[1px] ${
              indicador === "partido"
                ? "bg-[linear-gradient(90deg,var(--rep),var(--rule-2),var(--dem))]"
                : "bg-[linear-gradient(90deg,var(--down),var(--rule-2),var(--up))]"
            }`}
          />
          <span>{formatarValor(extremo, indicador)}</span>
        </div>
        <div className="flex flex-wrap gap-x-4 gap-y-1">
          <QualidadeDados nivel="individual" comTexto />
          <QualidadeDados nivel="parcial" comTexto />
          <QualidadeDados nivel="agregado" comTexto />
          <span className="inline-flex items-center gap-1.5 text-[12.5px] text-ink-2">
            <span
              aria-hidden="true"
              className="inline-block size-3 rounded-[2px] border border-dashed border-ink-3"
            />
            {t("mapa.semDados")}
          </span>
          {fora.length > 0 ? (
            <span className="inline-flex items-center gap-1.5 text-[12.5px] text-ink-2">
              <svg aria-hidden="true" width={12} height={12} className="shrink-0">
                <rect
                  x={0.5}
                  y={0.5}
                  width={11}
                  height={11}
                  rx={2}
                  className="fill-sheet stroke-ink-3"
                />
                <line x1={2} y1={10} x2={10} y2={2} strokeWidth={1.3} className="stroke-ink-3" />
              </svg>
              {t("mapa.fora")}
            </span>
          ) : null}
          <span className="inline-flex items-center gap-1.5 text-[12.5px] text-ink-2">
            <span
              aria-hidden="true"
              className="inline-block size-3 rounded-[2px] border border-rule bg-sheet"
            />
            {t("mapa.semValor")}
          </span>
        </div>
      </div>

      <div className="grid gap-4 lg:grid-cols-[minmax(0,1.6fr)_minmax(0,1fr)]">
        <section className="flex min-w-0 flex-col gap-3 rounded-md border border-rule bg-sheet px-[18px] pt-[18px] pb-3.5">
          <Grafico
            titulo={t("mapa.graficoAria")}
            altura={0}
            alturaPorLargura={alturaMapa}
            interativo
          >
            {(largura) => {
              const lado = ladoQuadrado(largura);
              const deslocamento = Math.floor(
                (largura - (COLUNAS_GRELHA * lado + (COLUNAS_GRELHA - 1) * ESPACO)) / 2,
              );
              return ESTADOS.map((e) => {
                const x = deslocamento + e.coluna * (lado + ESPACO);
                const y = e.linha * (lado + ESPACO);
                const r = porEstado.get(e.codigo);
                const semFonte = r ? undefined : foraPorEstado.get(e.codigo);
                const valor = r ? valorDe(r, indicador) : null;
                const cor = valor === null ? null : preenchimento(valor, extremo, indicador);
                const ativo = e.codigo === escolhido;
                const texto = cor?.forte ? "fill-sheet" : "fill-ink";
                return (
                  <g
                    key={e.codigo}
                    {...linhaEscolhivel(
                      !r
                        ? semFonte
                          ? t("mapa.quadradoFora", {
                              estado: e.nome,
                              codigo: e.codigo,
                              motivo: t(`mapa.motivos.${semFonte.motivo}`),
                            })
                          : t("mapa.quadradoSemDados", { estado: e.nome, codigo: e.codigo })
                        : valor === null
                          ? t("mapa.quadradoSemValor", { estado: e.nome, codigo: e.codigo })
                          : t("mapa.quadrado", {
                              estado: e.nome,
                              codigo: e.codigo,
                              valor: formatarValor(valor, indicador),
                            }),
                      () => {
                        setEscolhido(e.codigo);
                      },
                      ativo,
                    )}
                  >
                    <rect
                      x={x}
                      y={y}
                      width={lado}
                      height={lado}
                      rx={3}
                      strokeWidth={ativo ? 3 : 1}
                      strokeDasharray={r || semFonte ? undefined : "3 2"}
                      style={cor ? { fill: cor.fill } : undefined}
                      className={`${cor ? "" : "fill-sheet"} ${
                        ativo
                          ? "stroke-signal"
                          : r
                            ? cor
                              ? "stroke-transparent"
                              : "stroke-rule"
                            : "stroke-ink-3"
                      }`}
                    />
                    {cor && cor.padraoRep > 0 ? (
                      <rect
                        x={x}
                        y={y}
                        width={lado}
                        height={lado}
                        rx={3}
                        aria-hidden="true"
                        fill="url(#padrao-rep)"
                        opacity={Math.max(0.35, cor.padraoRep)}
                        className="pointer-events-none"
                      />
                    ) : null}
                    {semFonte ? (
                      <line
                        x1={x + 3}
                        y1={y + lado - 3}
                        x2={x + lado - 3}
                        y2={y + 3}
                        strokeWidth={1.3}
                        aria-hidden="true"
                        className="stroke-ink-3"
                      />
                    ) : null}
                    <text
                      x={x + 6}
                      y={y + (lado < 34 ? 13 : 16)}
                      className={`font-mono font-bold ${texto} ${lado < 34 ? "text-[9.5px]" : "text-[12px]"}`}
                    >
                      {e.codigo}
                    </text>
                    {lado >= 44 && valor !== null ? (
                      <text
                        x={x + 6}
                        y={y + lado - 8}
                        className={`font-mono text-[10.5px] ${cor?.forte ? "fill-sheet" : "fill-ink-2"}`}
                      >
                        {formatarValor(valor, indicador)}
                      </text>
                    ) : null}
                    {lado >= 30 && r ? (
                      <MarcaQualidade
                        x={x + lado - 9}
                        y={y + 11}
                        nivel={r.qualidade}
                        claro={cor?.forte ?? false}
                      />
                    ) : null}
                  </g>
                );
              });
            }}
          </Grafico>
          <footer className="flex flex-wrap justify-between gap-x-3.5 gap-y-1.5 border-t border-rule-2 pt-2 font-mono text-[11px] leading-snug text-ink-3">
            <span>
              {indicador === "ritmo"
                ? t("mapa.metodoRitmo", { ano: anoBase })
                : indicador === "partido"
                  ? t("mapa.metodoPartido", { ano: anoBase })
                  : t("mapa.metodo", { ano: anoBase })}
            </span>
            {indicador !== "ritmo" &&
            indicador !== "partido" &&
            resumos.some((r) => r.desvio.todos === null) ? (
              <span>{t("mapa.soIndividuais")}</span>
            ) : null}
          </footer>
        </section>

        <section
          aria-live="polite"
          className="flex min-w-0 flex-col gap-3 self-start rounded-md border border-rule bg-sheet px-[18px] py-[18px]"
        >
          <div className="flex flex-wrap items-start justify-between gap-2">
            <div>
              <p className="rotulo mb-1">{t("mapa.estadoEscolhido")}</p>
              <h2 className="font-display text-[30px] leading-none font-bold">
                {nomeEstado(escolhido as ResumoEstado["estado"])}
              </h2>
            </div>
            {resumo ? <QualidadeDados nivel={resumo.qualidade} comTexto /> : null}
          </div>
          {resumo ? (
            <>
              <dl className="grid grid-cols-[minmax(0,1fr)_auto] gap-x-4 gap-y-1.5 text-sm">
                <dt className="text-ink-2">{t("mapa.votos")}</dt>
                <dd className="text-right font-semibold">{formatarNumero(resumo.votos)}</dd>
                {resumo.variacaoVotos === null ? null : (
                  <>
                    <dt className="text-ink-2">
                      {t("mapa.ritmo", { ano: resumo.anoBase ?? anoBase })}
                    </dt>
                    <dd className="text-right font-semibold">
                      {formatarVariacao(resumo.variacaoVotos)}
                    </dd>
                  </>
                )}
                {resumo.vantagemDemRep === null ? null : (
                  <>
                    <dt className="text-ink-2">{t("mapa.vantagem")}</dt>
                    <dd className="text-right font-semibold">
                      {formatarMargem(resumo.vantagemDemRep)}
                      {resumo.vantagemDemRepBase === null ? null : (
                        <span className="block text-[11.5px] font-normal text-ink-3">
                          {t("mapa.vantagemBase", {
                            valor: formatarMargem(resumo.vantagemDemRepBase),
                            ano: resumo.anoBase ?? anoBase,
                          })}
                        </span>
                      )}
                    </dd>
                  </>
                )}
                {resumo.quotaCorreio === null ? null : (
                  <>
                    <dt className="text-ink-2">{t("mapa.correio")}</dt>
                    <dd className="text-right font-semibold">
                      {formatarPercentagem(resumo.quotaCorreio)}
                    </dd>
                  </>
                )}
                {resumo.pendentes === null ? null : (
                  <>
                    <dt className="text-ink-2">{t("mapa.pendentes")}</dt>
                    <dd className="text-right font-semibold">{formatarNumero(resumo.pendentes)}</dd>
                  </>
                )}
                {(["todos", "mais65", "jovens"] as const).map((chave) => {
                  const v = resumo.desvio[chave];
                  return v === null ? null : (
                    <div key={chave} className="contents">
                      <dt className="text-ink-2">{t(`mapa.desvios.${chave}`)}</dt>
                      <dd className="text-right font-semibold">{formatarVariacao(v)}</dd>
                    </div>
                  );
                })}
              </dl>
              <p className="font-mono text-[11px] text-ink-3">
                {formatarDiaCiclo(resumo.diasAntes)} ·{" "}
                {t("votoAntecipado.dadosAte", {
                  data: formatarData(new Date(`${resumo.dadosAte}T12:00:00Z`)),
                })}
              </p>
              {caminhos[resumo.estado] ? (
                <Link
                  href={caminhos[resumo.estado] ?? "/voto-antecipado/"}
                  className="self-start rounded-[2px] border border-rule px-2.5 py-1.5 text-[13px] text-ink hover:border-ink-3"
                >
                  {t("mapa.abrirAnalise")}
                </Link>
              ) : null}
            </>
          ) : foraEscolhido ? (
            <>
              <p className="rotulo">{t(`mapa.motivos.${foraEscolhido.motivo}`)}</p>
              <p className="text-sm text-ink-2">{foraEscolhido.nota}</p>
            </>
          ) : (
            <p className="text-sm text-ink-2">{t("mapa.estadoSemDados")}</p>
          )}
        </section>
      </div>
    </div>
  );
}

function ladoQuadrado(largura: number): number {
  return Math.min(62, Math.floor((largura - ESPACO * (COLUNAS_GRELHA - 1)) / COLUNAS_GRELHA));
}

function alturaMapa(largura: number): number {
  return LINHAS_GRELHA * (ladoQuadrado(largura) + ESPACO);
}

/** Ponto de qualidade dos dados: cheio, meio ou vazio. */
function MarcaQualidade({
  x,
  y,
  nivel,
  claro,
}: {
  x: number;
  y: number;
  nivel: ResumoEstado["qualidade"];
  claro: boolean;
}) {
  const cor = claro ? "stroke-sheet" : "stroke-ink-2";
  const enchimento = claro ? "fill-sheet" : "fill-ink-2";
  return (
    <g aria-hidden="true">
      <circle
        cx={x}
        cy={y}
        r={3.5}
        strokeWidth={1.3}
        className={`${cor} ${nivel === "individual" ? enchimento : "fill-none"}`}
      />
      {nivel === "parcial" ? (
        <path
          d={`M${String(x)},${String(y - 3.5)} A3.5,3.5 0 0 0 ${String(x)},${String(y + 3.5)} Z`}
          className={enchimento}
        />
      ) : null}
    </g>
  );
}
