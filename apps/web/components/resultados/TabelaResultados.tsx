"use client";

import { useId, useState } from "react";
import { nomeEstado } from "@/lib/estados.ts";
import {
  formatarMargem,
  formatarMargemPontos,
  formatarNumero,
  formatarPercentagem,
} from "@/lib/formatacao.ts";
import { t } from "@/lib/mensagens.ts";
import type { CorridaVista } from "@/lib/previsao/vista.ts";
import type { ContagemCorrida, LinhaResultados } from "@/lib/resultados/vista.ts";

/**
 * Tabela da noite eleitoral. É um componente de cliente para o HTML levar só os
 * dados das linhas; as linhas a mais só se desenham quando se pedem.
 */

function nomeCorrida(l: LinhaResultados): string {
  if (!l.senado) return l.id;
  const estado = nomeEstado(l.estado);
  return l.id.endsWith("-especial") ? `${estado} (${t("previsao.senado.especial")})` : estado;
}

function Amostra({ lado }: { lado: "D" | "R" }) {
  return (
    <span
      aria-hidden="true"
      className={`mr-1.5 inline-block size-2 rounded-[1px] align-middle ${lado === "D" ? "fundo-dem" : "fundo-rep"}`}
    />
  );
}

function Apuramento({ c }: { c: ContagemCorrida }) {
  if (!c.seccoes) return <>{t("resultados.tabela.semSeccoes")}</>;
  const texto = t(c.soTotal ? "resultados.tabela.condados" : "resultados.tabela.seccoes", {
    reportadas: formatarNumero(c.seccoes.reportadas),
    totais: formatarNumero(c.seccoes.totais),
  });
  return c.soTotal ? (
    <>
      {texto} · {t("resultados.tabela.soTotal")}
    </>
  ) : (
    <>{texto}</>
  );
}

function Contagem({ c }: { c: ContagemCorrida }) {
  return (
    <>
      <span className="font-semibold">
        {c.margem === null ? (
          <span className="text-ink-3">{t("resultados.tabela.semVotos")}</span>
        ) : (
          <>
            {c.margem === 0 ? null : <Amostra lado={c.margem > 0 ? "D" : "R"} />}
            {formatarMargem(c.margem)}
          </>
        )}
      </span>
      <span className="block text-[11px] text-ink-3">
        {t("resultados.tabela.votos", { n: formatarNumero(c.total) })}
      </span>
      <span className="block text-[11px] text-ink-3">
        <Apuramento c={c} />
      </span>
    </>
  );
}

function Previsao({ p }: { p: CorridaVista | null }) {
  if (!p)
    return <span className="text-[12px] text-ink-3">{t("resultados.tabela.semPrevisao")}</span>;
  const lado = p.probD >= 0.5 ? "D" : "R";
  const prob = lado === "D" ? p.probD : 1 - p.probD;
  return (
    <>
      <span
        className={`inline-block rounded-[2px] p-0.5 font-mono text-[12.5px] font-semibold ${
          lado === "D" ? "bg-dem px-1.5 text-sheet" : "fundo-rep text-ink"
        }`}
      >
        <span className={lado === "R" ? "block rounded-[1px] bg-sheet px-1" : undefined}>
          {`${lado} ${formatarPercentagem(prob, 0)}`}
        </span>
      </span>
      <span className="block font-mono text-[11px] text-ink-3">
        {p.decidida ? t("previsao.tabela.decidida") : formatarMargemPontos(p.margem)}
      </span>
    </>
  );
}

export function TabelaResultados({
  linhas,
  legenda,
  comContagem,
  visiveis,
}: {
  linhas: readonly LinhaResultados[];
  legenda: string;
  /** Coluna da margem contada (só nas corridas com dados ao vivo). */
  comContagem: boolean;
  /** Linhas mostradas antes de "ver as outras"; todas por omissão. */
  visiveis?: number;
}) {
  const [aberta, setAberta] = useState(false);
  const id = useId();
  const limite = visiveis ?? linhas.length;
  const mostradas = aberta ? linhas : linhas.slice(0, limite);
  const escondidas = linhas.length - limite;
  return (
    <div className="flex flex-col gap-2">
      <table id={id} className="w-full border-collapse text-sm">
        <caption className="sr-only">{legenda}</caption>
        <thead>
          <tr className="rotulo text-left">
            <th scope="col" className="pr-3 pb-1.5 font-medium">
              {t("resultados.tabela.corrida")}
            </th>
            {comContagem ? (
              <th scope="col" className="pr-3 pb-1.5 font-medium">
                {t("resultados.tabela.contagem")}
              </th>
            ) : null}
            <th scope="col" className="pb-1.5 text-right font-medium">
              {t("resultados.tabela.previsao")}
            </th>
          </tr>
        </thead>
        <tbody>
          {mostradas.map((l) => (
            <tr key={l.id} className="border-t border-rule-2 align-top">
              <th scope="row" className="py-2 pr-3 text-left font-semibold">
                {nomeCorrida(l)}
                {l.senado ? null : (
                  <span className="ml-1.5 text-[12px] font-normal text-ink-3">
                    {nomeEstado(l.estado)}
                  </span>
                )}
                {comContagem ? null : (
                  <span className="block text-[11px] font-normal text-ink-3">
                    {t("resultados.semDados.nota")}
                  </span>
                )}
              </th>
              {comContagem ? (
                <td className="py-2 pr-3 font-mono text-[13px]">
                  {l.contagem ? <Contagem c={l.contagem} /> : null}
                </td>
              ) : null}
              <td className="py-2 text-right whitespace-nowrap">
                <Previsao p={l.previsao} />
              </td>
            </tr>
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
          {aberta ? t("resultados.tabela.menos") : t("resultados.tabela.mais", { n: escondidas })}
        </button>
      ) : null}
    </div>
  );
}
