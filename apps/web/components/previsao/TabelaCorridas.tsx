"use client";

import Link from "next/link";
import { useId, useState } from "react";
import { caminhoPaginaCorrida } from "@/lib/corridas.ts";
import { nomeEstado } from "@/lib/estados.ts";
import {
  formatarMargemPontos as margem,
  formatarPercentagem,
  formatarPontos,
} from "@/lib/formatacao.ts";
import { t } from "@/lib/mensagens.ts";
import type { CorridaVista } from "@/lib/previsao/vista.ts";

/**
 * Tabela de corridas. É um componente de cliente para o HTML levar só os
 * dados das linhas e não a árvore inteira de cada uma; as linhas a mais só se
 * desenham quando se pedem.
 */

/** Faixa do intervalo de 80% da margem, de R+30 a D+30, com o valor previsto. */
function FaixaMargem({ c }: { c: CorridaVista }) {
  const largura = 120;
  const limite = 30;
  const x = (v: number) =>
    ((Math.max(-limite, Math.min(limite, v)) + limite) / (2 * limite)) * largura;
  const cor =
    c.margemP10 > 0
      ? { className: "fill-dem", opacity: 0.35 }
      : c.margemP90 < 0
        ? { style: { fill: "url(#padrao-rep)" }, opacity: 0.6 }
        : { className: "fill-ink-3", opacity: 0.35 };
  return (
    <svg width={largura} height={14} aria-hidden="true" className="block overflow-visible">
      <line x1={0} x2={largura} y1={7} y2={7} className="stroke-rule" />
      <line x1={x(0)} x2={x(0)} y1={1} y2={13} className="stroke-ink-3" />
      <rect
        x={x(c.margemP10)}
        y={3}
        width={x(c.margemP90) - x(c.margemP10)}
        height={8}
        rx={2}
        {...cor}
      />
      <circle cx={x(c.margem)} cy={7} r={3.5} className="fill-ink stroke-sheet" />
    </svg>
  );
}

function Candidato({ lado, c }: { lado: "D" | "R"; c: CorridaVista }) {
  const nome = lado === "D" ? c.candidatoD : c.candidatoR;
  const independente = lado === "D" ? c.independenteD : c.independenteR;
  const incumbente = c.incumbente === lado || (independente && c.incumbente === "I");
  const extras = [
    incumbente ? t("previsao.tabela.incumbente") : null,
    independente ? t("previsao.tabela.independente") : null,
  ].filter((e): e is string => e !== null);
  return (
    <span className="block">
      <span
        aria-hidden="true"
        className={`mr-1.5 inline-block size-2 rounded-[1px] align-middle ${lado === "D" ? "fundo-dem" : "fundo-rep"}`}
      />
      <span className="sr-only">{lado}: </span>
      {nome ?? <span className="text-ink-3">{t("previsao.tabela.semCandidato")}</span>}
      {extras.length > 0 ? <span className="text-ink-3"> ({extras.join(", ")})</span> : null}
    </span>
  );
}

function nomeCorrida(c: CorridaVista): string {
  if (c.camara === "camara") return c.id;
  const estado = nomeEstado(c.estado);
  return c.especial ? `${estado} (${t("previsao.senado.especial")})` : estado;
}

function Linha({
  c,
  comSondagens,
  variacao,
}: {
  c: CorridaVista;
  comSondagens: boolean;
  variacao: number | undefined;
}) {
  const lado = c.probD >= 0.5 ? "D" : "R";
  const prob = lado === "D" ? c.probD : 1 - c.probD;
  return (
    <tr className="border-t border-rule-2 align-top">
      <th scope="row" className="py-2 pr-3 text-left font-semibold">
        <Link
          href={caminhoPaginaCorrida(c.id)}
          className="underline decoration-rule underline-offset-[3px] hover:decoration-ink-3"
        >
          {nomeCorrida(c)}
        </Link>
        {c.camara === "camara" ? (
          <span className="ml-1.5 text-[12px] font-normal text-ink-3">{nomeEstado(c.estado)}</span>
        ) : null}
        <span className="mt-0.5 block text-[12.5px] font-normal">
          <Candidato lado="D" c={c} />
          <Candidato lado="R" c={c} />
        </span>
      </th>
      <td className="py-2 pr-3 text-right font-mono text-[13px] whitespace-nowrap sm:text-left">
        <span className="flex flex-col items-end gap-1 sm:flex-row sm:items-center sm:gap-2.5">
          <span className="hidden lg:block">
            <FaixaMargem c={c} />
          </span>
          <span>{c.decidida ? t("previsao.tabela.decidida") : margem(c.margem)}</span>
        </span>
        <span className="block text-[11px] text-ink-3">
          {margem(c.margemP10, 0)} {t("previsao.tabela.a")} {margem(c.margemP90, 0)}
        </span>
      </td>
      {comSondagens ? (
        <td className="hidden py-2 pr-3 font-mono text-[12px] text-ink-2 sm:table-cell">
          {c.sondagens
            ? t(
                c.sondagens.institutos === 1
                  ? "previsao.tabela.instituto"
                  : "previsao.tabela.institutos",
                {
                  margem: margem(c.sondagens.margem),
                  n: c.sondagens.institutos,
                },
              )
            : t("previsao.tabela.semSondagens")}
        </td>
      ) : null}
      <td className="py-2 text-right whitespace-nowrap">
        <span
          className={`inline-block rounded-[2px] p-0.5 font-mono text-[12.5px] font-semibold ${
            lado === "D" ? "bg-dem px-1.5 text-sheet" : "fundo-rep text-ink"
          }`}
        >
          <span className={lado === "R" ? "block rounded-[1px] bg-sheet px-1" : undefined}>
            {`${lado} ${formatarPercentagem(prob, 0)}`}
          </span>
        </span>
        {variacao !== undefined && Math.abs(variacao) >= 0.01 ? (
          <span className="ml-auto block max-w-[6.5rem] font-mono text-[11px] whitespace-normal text-ink-3">
            {t("previsao.tabela.variacao", { valor: formatarPontos(variacao, 0) })}
          </span>
        ) : null}
      </td>
    </tr>
  );
}

export function TabelaCorridas({
  corridas,
  legenda,
  comSondagens,
  variacoes,
  visiveis,
}: {
  corridas: readonly CorridaVista[];
  legenda: string;
  comSondagens: boolean;
  /** Variação da probabilidade democrata numa semana, por corrida. */
  variacoes: Readonly<Record<string, number>>;
  /** Linhas mostradas antes de "ver as outras"; todas por omissão. */
  visiveis?: number;
}) {
  const [aberta, setAberta] = useState(false);
  const id = useId();
  const limite = visiveis ?? corridas.length;
  const mostradas = aberta ? corridas : corridas.slice(0, limite);
  const escondidas = corridas.length - limite;
  return (
    <div className="flex flex-col gap-2">
      <table id={id} className="w-full border-collapse text-sm">
        <caption className="sr-only">{legenda}</caption>
        <thead>
          <tr className="rotulo text-left">
            <th scope="col" className="pr-3 pb-1.5 font-medium">
              {t("previsao.tabela.corrida")}
            </th>
            <th scope="col" className="pr-3 pb-1.5 text-right font-medium sm:text-left">
              {t("previsao.tabela.margem")}
            </th>
            {comSondagens ? (
              <th scope="col" className="hidden pr-3 pb-1.5 font-medium sm:table-cell">
                {t("previsao.tabela.sondagens")}
              </th>
            ) : null}
            <th scope="col" className="pb-1.5 text-right font-medium">
              {t("previsao.tabela.favorito")}
            </th>
          </tr>
        </thead>
        <tbody>
          {mostradas.map((c) => (
            <Linha key={c.id} c={c} comSondagens={comSondagens} variacao={variacoes[c.id]} />
          ))}
        </tbody>
      </table>
      {escondidas > 0 ? (
        <button
          type="button"
          aria-expanded={aberta}
          aria-controls={id}
          onClick={() => {
            setAberta((a) => !a);
          }}
          className="self-start rounded-[2px] border border-rule px-2.5 py-1.5 text-[13px] text-ink hover:border-ink-3"
        >
          {aberta ? t("previsao.tabela.menos") : t("previsao.camara.mais", { n: escondidas })}
        </button>
      ) : null}
    </div>
  );
}
