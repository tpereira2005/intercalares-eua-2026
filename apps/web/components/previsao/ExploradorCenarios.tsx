"use client";

import Link from "next/link";
import { useId, useRef, useState } from "react";
import { Grafico } from "@/components/charts/base.tsx";
import { formatarMargemPontos, formatarPercentagem, formatarPontos } from "@/lib/formatacao.ts";
import { t } from "@/lib/mensagens.ts";
import {
  obterCenario,
  viragem,
  type CenarioVista,
  type VistaCenarios,
} from "@/lib/previsao/explorador.ts";
import type { Camara } from "@/lib/previsao/vista.ts";

const TEXTO_EIXO = "fill-ink-3 font-mono text-[10.5px]";
const LIGACAO = "text-ink underline decoration-rule underline-offset-[3px]";
const CAMARAS: readonly Camara[] = ["camara", "senado"];
/** Corridas mostradas: as que a previsão ou o cenário escolhido não dão como certas. */
const INCERTA = 0.03;

export interface CorridaExplorador {
  id: string;
  nome: string;
  href: string;
}

function numero(valor: number, casas = 2): string {
  return valor.toLocaleString("pt-PT", { maximumFractionDigits: casas });
}

function Probabilidade({ probD }: { probD: number }) {
  const lado = probD >= 0.5 ? "D" : "R";
  return (
    <span
      className={`inline-block rounded-[2px] p-0.5 font-mono font-semibold ${
        lado === "D" ? "bg-dem px-1.5 text-sheet" : "fundo-rep text-ink"
      }`}
    >
      <span className={lado === "R" ? "block rounded-[1px] bg-sheet px-1" : undefined}>
        {`${lado} ${formatarPercentagem(lado === "D" ? probD : 1 - probD, 0)}`}
      </span>
    </span>
  );
}

function CartaoCamara({
  camara,
  cenario,
  base,
  maioria,
}: {
  camara: Camara;
  cenario: CenarioVista;
  base: CenarioVista;
  maioria: number;
}) {
  const r = cenario[camara];
  const variacao = r.probD - base[camara].probD;
  return (
    <section
      aria-labelledby={`cenario-${camara}`}
      className="flex min-w-0 flex-col gap-2 rounded-[3px] border border-rule p-3.5"
    >
      <h3 id={`cenario-${camara}`} className="font-display text-[20px] leading-none font-bold">
        {t(`previsao.camaraNome.${camara}`)}
      </h3>
      <p className="flex flex-wrap items-center gap-2 text-[18px]">
        <Probabilidade probD={r.probD} />
        <span className="font-mono text-[12px] text-ink-2">
          {Math.abs(variacao) < 0.005
            ? t("previsao.cenarios.igual")
            : t("previsao.cenarios.variacao", { variacao: formatarPontos(variacao, 0) })}
        </span>
      </p>
      <p className="text-[13px] text-ink-2">
        {t("previsao.cenarios.lugares", {
          mediana: r.mediana,
          de: r.p10,
          ate: r.p90,
          maioria,
        })}
      </p>
    </section>
  );
}

/** Probabilidade de controlo democrata de cada câmara ao longo da grelha de deslocações. */
function CurvaControlo({
  vista,
  fator,
  desvio,
}: {
  vista: VistaCenarios;
  fator: number;
  desvio: number;
}) {
  const altura = 200;
  const m = { esquerda: 38, direita: 62, topo: 10, fundo: 26 };
  const pontos = vista.desvios.flatMap((d) => {
    const c = obterCenario(vista, d, fator);
    return c ? [c] : [];
  });
  const primeiro = pontos[0];
  const ultimo = pontos.at(-1);
  if (!primeiro || !ultimo) return null;
  const a0 = primeiro.ambiente;
  const a1 = Math.max(ultimo.ambiente, a0 + 1);
  const escolhido = obterCenario(vista, desvio, fator);
  return (
    <Grafico
      titulo={t("previsao.cenarios.curvaAria", {
        de: formatarMargemPontos(a0),
        ate: formatarMargemPontos(ultimo.ambiente),
      })}
      altura={altura}
    >
      {(largura) => {
        const x = (a: number) =>
          m.esquerda + ((largura - m.esquerda - m.direita) * (a - a0)) / (a1 - a0);
        const y = (p: number) => m.topo + (altura - m.topo - m.fundo) * (1 - p);
        const caminho = (camara: Camara) =>
          pontos
            .map(
              (c, i) =>
                `${i ? "L" : "M"}${x(c.ambiente).toFixed(1)},${y(c[camara].probD).toFixed(1)}`,
            )
            .join("");
        const marcas = pontos.filter((_, i) => i % 4 === 0 || i === pontos.length - 1);
        return (
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
            {marcas.map((c) => (
              <text
                key={c.desvio}
                x={x(c.ambiente)}
                y={altura - 8}
                textAnchor="middle"
                className={TEXTO_EIXO}
              >
                {formatarMargemPontos(c.ambiente, 0)}
              </text>
            ))}
            {escolhido ? (
              <line
                x1={x(escolhido.ambiente)}
                x2={x(escolhido.ambiente)}
                y1={m.topo}
                y2={altura - m.fundo}
                strokeWidth={2}
                className="stroke-signal"
              />
            ) : null}
            <path d={caminho("camara")} fill="none" strokeWidth={2.25} className="stroke-ink" />
            <path
              d={caminho("senado")}
              fill="none"
              strokeWidth={2.25}
              strokeDasharray="6 4"
              className="stroke-ink-2"
            />
            {escolhido
              ? CAMARAS.map((c) => (
                  <circle
                    key={c}
                    cx={x(escolhido.ambiente)}
                    cy={y(escolhido[c].probD)}
                    r={4.5}
                    strokeWidth={2}
                    className={c === "camara" ? "fill-ink stroke-sheet" : "fill-sheet stroke-ink-2"}
                  />
                ))
              : null}
            {CAMARAS.map((c, i) => {
              const yFim = y(ultimo[c].probD) + 4;
              const outro = y(ultimo[CAMARAS[1 - i] ?? "camara"].probD) + 4;
              const ajuste = Math.abs(yFim - outro) < 12 ? (i === 0 ? -7 : 7) : 0;
              return (
                <text
                  key={c}
                  x={largura - m.direita + 6}
                  y={yFim + ajuste}
                  className="fill-ink-2 text-[11.5px] font-medium"
                >
                  {t(`previsao.camaraNome.${c}`)}
                </text>
              );
            })}
          </g>
        );
      }}
    </Grafico>
  );
}

function TabelaSenado({
  corridas,
  cenario,
  base,
}: {
  corridas: readonly CorridaExplorador[];
  cenario: CenarioVista;
  base: CenarioVista;
}) {
  const incerta = (p: number | undefined) => p !== undefined && p > INCERTA && p < 1 - INCERTA;
  const linhas = corridas
    .filter((c) => incerta(cenario.corridasSenado[c.id]) || incerta(base.corridasSenado[c.id]))
    .map((c) => ({
      ...c,
      agora: cenario.corridasSenado[c.id] ?? null,
      publicada: base.corridasSenado[c.id] ?? null,
    }))
    .sort(
      (a, b) =>
        Math.abs((a.agora ?? 0.5) - 0.5) - Math.abs((b.agora ?? 0.5) - 0.5) ||
        a.id.localeCompare(b.id),
    );
  return (
    <table className="w-full border-collapse text-sm">
      <caption className="sr-only">{t("previsao.cenarios.legendaSenado")}</caption>
      <thead>
        <tr className="rotulo text-left">
          <th scope="col" className="pr-3 pb-1.5 font-medium">
            {t("previsao.tabela.corrida")}
          </th>
          <th scope="col" className="pr-3 pb-1.5 text-right font-medium">
            {t("previsao.cenarios.publicada")}
          </th>
          <th scope="col" className="pb-1.5 text-right font-medium">
            {t("previsao.cenarios.nesteCenario")}
          </th>
        </tr>
      </thead>
      <tbody>
        {linhas.map((l) => (
          <tr key={l.id} className="border-t border-rule-2">
            <th scope="row" className="py-1.5 pr-3 text-left font-normal">
              <Link href={l.href} className={LIGACAO}>
                {l.nome}
              </Link>
            </th>
            <td className="py-1.5 pr-3 text-right font-mono text-[12.5px] text-ink-2">
              {l.publicada === null
                ? "—"
                : l.publicada >= 0.5
                  ? `D ${formatarPercentagem(l.publicada, 0)}`
                  : `R ${formatarPercentagem(1 - l.publicada, 0)}`}
            </td>
            <td className="py-1.5 text-right whitespace-nowrap">
              {l.agora === null ? "—" : <Probabilidade probD={l.agora} />}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

/** Explorador dos cenários publicados pelo modelo: desloca o ambiente e muda o erro. */
export function ExploradorCenarios({
  vista,
  corridas,
  maiorias,
}: {
  vista: VistaCenarios;
  corridas: readonly CorridaExplorador[];
  maiorias: Record<Camara, number>;
}) {
  const fatorPublicado = vista.fatores.reduce(
    (melhor, f) => (Math.abs(f - 1) < Math.abs(melhor - 1) ? f : melhor),
    vista.fatores[0] ?? 1,
  );
  const indiceZero = Math.max(
    0,
    vista.desvios.findIndex((d) => Math.abs(d) < 1e-6),
  );
  const [indice, setIndice] = useState(indiceZero);
  const [fator, setFator] = useState(fatorPublicado);
  const id = useId();
  // Ao repor, o botão fica desativado e perderia o foco: passa para o controlo do ambiente.
  const ambienteRef = useRef<HTMLInputElement>(null);
  const desvio = vista.desvios[indice] ?? 0;
  const cenario = obterCenario(vista, desvio, fator);
  const base = obterCenario(vista, 0, fatorPublicado);
  if (!cenario || !base) return null;
  const textoDesvio =
    Math.abs(desvio) < 1e-6
      ? t("previsao.cenarios.semDeslocacao")
      : t(desvio > 0 ? "previsao.cenarios.deslocacaoD" : "previsao.cenarios.deslocacaoR", {
          pontos: numero(Math.abs(desvio)),
        });
  return (
    <div className="flex flex-col gap-4">
      <div className="grid gap-4 min-[860px]:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
        <div className="flex flex-col gap-3">
          <label htmlFor={`${id}-ambiente`} className="flex flex-col gap-1">
            <span id={`${id}-ambiente-rotulo`} className="rotulo">
              {t("previsao.cenarios.ambiente")}
            </span>
            <span className="font-display text-[28px] leading-none font-bold">
              {formatarMargemPontos(cenario.ambiente)}
            </span>
            <span className="text-[13px] text-ink-2">{textoDesvio}</span>
          </label>
          <input
            ref={ambienteRef}
            id={`${id}-ambiente`}
            aria-labelledby={`${id}-ambiente-rotulo`}
            type="range"
            min={0}
            max={vista.desvios.length - 1}
            step={1}
            value={indice}
            aria-valuetext={`${formatarMargemPontos(cenario.ambiente)}. ${textoDesvio}`}
            onChange={(e) => {
              setIndice(Number(e.target.value));
            }}
            className="w-full accent-[var(--signal)]"
          />
          <div
            className="flex justify-between font-mono text-[10.5px] text-ink-3"
            aria-hidden="true"
          >
            <span>{t("previsao.cenarios.extremoR")}</span>
            <span>{t("previsao.cenarios.extremoD")}</span>
          </div>
          <fieldset className="flex flex-col gap-1.5">
            <legend className="rotulo mb-1">{t("previsao.cenarios.erro")}</legend>
            <div className="flex flex-wrap gap-2">
              {vista.fatores.map((f) => {
                const chave =
                  f === fatorPublicado ? "publicado" : f < fatorPublicado ? "menor" : "maior";
                return (
                  <label
                    key={f}
                    className="inline-flex cursor-pointer items-center gap-1.5 rounded-[2px] border border-rule px-2.5 py-1.5 text-[13px] has-[:checked]:border-ink has-[:checked]:shadow-[inset_0_0_0_1px_var(--ink)] has-[:focus-visible]:outline-2 has-[:focus-visible]:outline-signal"
                  >
                    <input
                      type="radio"
                      name={`${id}-fator`}
                      value={f}
                      checked={f === fator}
                      onChange={() => {
                        setFator(f);
                      }}
                      className="sr-only"
                    />
                    {t(`previsao.cenarios.fatores.${chave}`, { fator: numero(f) })}
                  </label>
                );
              })}
            </div>
            <p className="text-[12.5px] text-ink-3">{t("previsao.cenarios.erroNota")}</p>
          </fieldset>
          <button
            type="button"
            onClick={() => {
              setIndice(indiceZero);
              setFator(fatorPublicado);
              ambienteRef.current?.focus();
            }}
            disabled={indice === indiceZero && fator === fatorPublicado}
            className="self-start rounded-[2px] border border-rule px-2.5 py-1.5 text-[13px] text-ink hover:border-ink-3 disabled:cursor-default disabled:opacity-50"
          >
            {t("previsao.cenarios.repor")}
          </button>
        </div>
        <div aria-live="polite" className="grid content-start gap-3 sm:grid-cols-2">
          {CAMARAS.map((c) => (
            <CartaoCamara key={c} camara={c} cenario={cenario} base={base} maioria={maiorias[c]} />
          ))}
        </div>
      </div>

      <div className="flex flex-col gap-2">
        <h3 className="text-[15px] font-semibold">{t("previsao.cenarios.curvaTitulo")}</h3>
        <CurvaControlo vista={vista} fator={fator} desvio={desvio} />
        <p className="font-mono text-[11px] text-ink-3">{t("previsao.cenarios.curvaLegenda")}</p>
        <ul className="flex flex-col gap-1 text-[13px] text-ink-2">
          {CAMARAS.map((c) => {
            const v = viragem(vista, c, fator);
            const nome = t(`previsao.camaraNome.${c}`);
            return (
              <li key={c}>
                {v === null
                  ? t("previsao.cenarios.semViragem", { camara: nome })
                  : t("previsao.cenarios.viragem", {
                      camara: nome,
                      pontos: numero(Math.abs(v)),
                      direcao: t(
                        v > 0 ? "previsao.cenarios.direcaoD" : "previsao.cenarios.direcaoR",
                      ),
                    })}
              </li>
            );
          })}
        </ul>
      </div>

      <div className="flex flex-col gap-2">
        <h3 className="text-[15px] font-semibold">{t("previsao.cenarios.senadoTitulo")}</h3>
        <TabelaSenado corridas={corridas} cenario={cenario} base={base} />
      </div>
    </div>
  );
}
