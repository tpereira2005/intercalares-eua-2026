"use client";

import { useId, useState } from "react";
import { ControloSegmentado } from "@/components/ui/ControloSegmentado.tsx";
import { Painel, type ReferenciaFonte } from "@/components/ui/Painel.tsx";
import { formatarNumero, formatarPercentagem, formatarPontos } from "@/lib/formatacao.ts";
import { t } from "@/lib/mensagens.ts";
import {
  FAIXAS_LARGAS,
  linhasUnidades,
  MINIMO_VOTOS_UNIDADE,
  type FaixaLarga,
  type NivelGeografico,
  type UnidadeGeografica,
} from "@/lib/voto-antecipado/geografia.ts";

/** Unidades mostradas antes de "ver todas". */
const VISIVEIS = 12;

function rotulo(faixa: FaixaLarga): string {
  return faixa.replace("-", "–");
}

/** Barra horizontal da quota da faixa, com a marca do ano de comparação. */
function BarraQuota({ quota, base }: { quota: number | null; base: number | null }) {
  const largura = 72;
  return (
    <svg width={largura} height={10} aria-hidden="true" className="hidden shrink-0 sm:block">
      <rect x={0} y={2} width={largura} height={6} rx={1} className="fill-rule-2" />
      {quota === null ? null : (
        <rect x={0} y={2} width={largura * quota} height={6} rx={1} className="fill-signal" />
      )}
      {base === null ? null : (
        <line
          x1={largura * base}
          x2={largura * base}
          y1={0}
          y2={10}
          strokeWidth={2}
          className="stroke-ink"
        />
      )}
    </svg>
  );
}

/** Composição por idade em cada condado e distrito, face ao mesmo dia de um ano de referência. */
export function PainelGeografia({
  unidades,
  ano,
  anoBase,
  fontes,
}: {
  unidades: readonly UnidadeGeografica[];
  ano: number;
  anoBase: number;
  fontes: readonly ReferenciaFonte[];
}) {
  const niveis = (["distrito", "condado"] as const).filter((n) =>
    unidades.some((u) => u.nivel === n),
  );
  // Por omissão, o primeiro nível que tem o ano de comparação (na Pensilvânia, 2022 só tem condados).
  const comBase = niveis.find((n) =>
    unidades.some((u) => u.nivel === n && u.anos.some((a) => a.ano === anoBase)),
  );
  const [nivel, setNivel] = useState<NivelGeografico>(comBase ?? niveis[0] ?? "condado");
  const [faixa, setFaixa] = useState<FaixaLarga>("18-29");
  const [aberta, setAberta] = useState(false);
  const id = useId();
  if (niveis.length === 0) return null;
  const linhas = linhasUnidades(unidades, nivel, faixa, ano, anoBase);
  // Sem recenseados (estados sem ficheiro de eleitores), não há participação a mostrar.
  const comTaxa = linhas.some((l) => l.taxa !== null);
  const comNovos = linhas.some((l) => l.novos !== null);
  const mostradas = aberta ? linhas : linhas.slice(0, VISIVEIS);
  const escondidas = linhas.length - mostradas.length;
  const nomeUnidade = (codigo: string, nome: string) =>
    nivel === "distrito" ? t("votoAntecipado.geografia.distrito", { n: codigo }) : nome;

  return (
    <Painel
      className="col-span-full"
      sobrelinha={t("votoAntecipado.geografia.sobrelinha", { ano: anoBase })}
      titulo={t("votoAntecipado.geografia.titulo", { faixa: rotulo(faixa) })}
      acessorio={
        niveis.length > 1 ? (
          <ControloSegmentado<NivelGeografico>
            rotuloGrupo={t("votoAntecipado.geografia.nivelAria")}
            valor={nivel}
            aoMudar={(v) => {
              setNivel(v);
              setAberta(false);
            }}
            opcoes={niveis.map((n) => ({
              valor: n,
              rotulo: t(`votoAntecipado.geografia.niveis.${n}`),
            }))}
          />
        ) : null
      }
      fontes={fontes}
      metodo={t(
        comTaxa ? "votoAntecipado.geografia.metodo" : "votoAntecipado.geografia.metodoSemTaxa",
        {
          minimo: MINIMO_VOTOS_UNIDADE,
        },
      )}
    >
      <p className="max-w-[70ch] text-sm text-ink-2">
        {t(comTaxa ? "votoAntecipado.geografia.texto" : "votoAntecipado.geografia.textoSemTaxa", {
          ano: anoBase,
        })}
      </p>
      <ControloSegmentado<FaixaLarga>
        rotuloGrupo={t("votoAntecipado.geografia.faixaAria")}
        valor={faixa}
        aoMudar={setFaixa}
        opcoes={FAIXAS_LARGAS.map((f) => ({ valor: f, rotulo: rotulo(f) }))}
      />
      <table id={id} className="w-full border-collapse text-sm">
        <caption className="sr-only">
          {t("votoAntecipado.geografia.legenda", {
            faixa: rotulo(faixa),
            nivel: t(`votoAntecipado.geografia.niveis.${nivel}`),
            ano: anoBase,
          })}
        </caption>
        <thead>
          <tr className="rotulo text-left">
            <th scope="col" className="pr-3 pb-1.5 font-medium">
              {t(`votoAntecipado.geografia.niveis.${nivel}`)}
            </th>
            <th scope="col" className="pr-3 pb-1.5 text-right font-medium">
              {t("votoAntecipado.geografia.quota", { ano })}
            </th>
            <th scope="col" className="pr-3 pb-1.5 text-right font-medium">
              {t("votoAntecipado.geografia.diferenca", { ano: anoBase })}
            </th>
            {comTaxa ? (
              <th scope="col" className="hidden pb-1.5 pl-3 text-right font-medium sm:table-cell">
                {t("votoAntecipado.geografia.taxa")}
              </th>
            ) : null}
            {comNovos ? (
              <th scope="col" className="pb-1.5 pl-3 text-right font-medium">
                {t("votoAntecipado.geografia.novos")}
              </th>
            ) : null}
          </tr>
        </thead>
        <tbody>
          {mostradas.map((l) => (
            <tr
              key={l.codigo}
              className={`border-t border-rule-2 align-top ${l.poucosVotos ? "text-ink-3" : ""}`}
            >
              <th scope="row" className="py-1.5 pr-3 text-left font-semibold">
                {nomeUnidade(l.codigo, l.nome)}
                <span className="block font-mono text-[11px] font-normal text-ink-3">
                  {t("votoAntecipado.geografia.votos", { n: formatarNumero(l.votos) })}
                  {l.poucosVotos ? ` · ${t("votoAntecipado.geografia.poucosVotos")}` : null}
                </span>
              </th>
              <td className="py-1.5 pr-3 text-right font-mono text-[13px]">
                <span className="flex items-center justify-end gap-2">
                  <BarraQuota quota={l.quota} base={l.quotaBase} />
                  {l.quota === null ? t("comum.semDados") : formatarPercentagem(l.quota)}
                </span>
              </td>
              <td className="py-1.5 pr-3 text-right font-mono text-[13px] whitespace-nowrap">
                {l.diferenca === null ? t("comum.semDados") : formatarPontos(l.diferenca)}
              </td>
              {comTaxa ? (
                <td className="hidden py-1.5 pl-3 text-right font-mono text-[13px] sm:table-cell">
                  {l.taxa === null ? t("comum.semDados") : formatarPercentagem(l.taxa)}
                </td>
              ) : null}
              {comNovos ? (
                <td className="py-1.5 pl-3 text-right font-mono text-[13px]">
                  {l.novos === null ? t("comum.semDados") : formatarPercentagem(l.novos, 0)}
                  {l.novosBase === null ? null : (
                    <span className="block text-[11px] text-ink-3">
                      {t("votoAntecipado.geografia.novosBase", {
                        ano: anoBase,
                        valor: formatarPercentagem(l.novosBase, 0),
                      })}
                    </span>
                  )}
                </td>
              ) : null}
            </tr>
          ))}
        </tbody>
      </table>
      {comNovos ? (
        <p className="text-[12.5px] text-ink-3">{t("votoAntecipado.geografia.novosNota")}</p>
      ) : null}
      {linhas.length > VISIVEIS ? (
        <button
          type="button"
          aria-expanded={aberta}
          aria-controls={id}
          onClick={() => {
            setAberta((a) => !a);
          }}
          className="self-start rounded-[2px] border border-rule px-2.5 py-1.5 text-[13px] text-ink hover:border-ink-3"
        >
          {aberta
            ? t("votoAntecipado.geografia.menos")
            : t("votoAntecipado.geografia.mais", { n: escondidas })}
        </button>
      ) : null}
    </Painel>
  );
}
