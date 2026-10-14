"use client";

import { useId, useState } from "react";
import { ControloSegmentado } from "@/components/ui/ControloSegmentado.tsx";
import { Painel, type ReferenciaFonte } from "@/components/ui/Painel.tsx";
import { formatarNumero, formatarPercentagem, formatarPontos } from "@/lib/formatacao.ts";
import { t } from "@/lib/mensagens.ts";
import { Amostra, ItemLegenda, Legenda } from "./legendas.tsx";
import {
  FAIXAS_LARGAS,
  FAIXAS_MOMENTO,
  linhasMomento,
  linhasUnidades,
  MINIMO_VOTOS_UNIDADE,
  NIVEIS,
  nivelPorOmissao,
  type FaixaLarga,
  type FaixaMomento,
  type LinhaMomentoUnidade,
  type NivelGeografico,
  type UnidadeGeografica,
} from "@/lib/voto-antecipado/geografia.ts";

/** Unidades mostradas antes de "ver todas". */
const VISIVEIS = 12;

/** O que a tabela mostra: a idade de quem vota, ou se são eleitores habituais ou novos. */
type Pergunta = "composicao" | "momento";

const CELULA = "py-1.5 pr-2 sm:pr-3 text-right font-mono text-[13px] whitespace-nowrap";

function rotulo(faixa: FaixaMomento): string {
  // O travessão leva um "word joiner" a seguir, para "18–29" não partir entre linhas.
  return faixa === "total" ? t("votoAntecipado.geografia.todas") : faixa.replace("-", "–\u2060");
}

/** Barra empilhada do momento: habituais, antecipação e novos (como no gráfico do estado). */
function BarraMomento({ linha }: { linha: LinhaMomentoUnidade }) {
  const largura = 72;
  const partes = [
    { valor: linha.habituais ?? 0, props: { className: "fill-ink-3 opacity-45" } },
    { valor: linha.antecipacao ?? 0, props: { fill: "url(#padrao-antecipacao)" } },
    { valor: linha.novos ?? 0, props: { className: "fill-up" } },
  ];
  let x = 0;
  return (
    <svg width={largura} height={10} aria-hidden="true" className="hidden shrink-0 sm:block">
      {partes.map((p, i) => {
        const w = largura * p.valor;
        const r = <rect key={i} x={x} y={2} width={w} height={6} {...p.props} />;
        x += w;
        return r;
      })}
      {linha.novosBase === null ? null : (
        <line
          x1={largura * (1 - linha.novosBase)}
          x2={largura * (1 - linha.novosBase)}
          y1={0}
          y2={10}
          strokeWidth={2}
          className="stroke-ink"
        />
      )}
    </svg>
  );
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
  comParticipacao = true,
  className = "lg:col-span-2",
}: {
  unidades: readonly UnidadeGeografica[];
  ano: number;
  anoBase: number;
  fontes: readonly ReferenciaFonte[];
  /** `false` nos estados sem recenseados por faixa: só quotas nos votos. */
  comParticipacao?: boolean;
  className?: string;
}) {
  const niveis = NIVEIS.filter((n) => unidades.some((u) => u.nivel === n));
  const [nivel, setNivel] = useState<NivelGeografico>(
    () => nivelPorOmissao(unidades, anoBase) ?? "condado",
  );
  const [faixa, setFaixa] = useState<FaixaMomento>("18-29");
  const [pergunta, setPergunta] = useState<Pergunta>("composicao");
  const [aberta, setAberta] = useState(false);
  const id = useId();
  if (niveis.length === 0) return null;
  const atual = unidades.flatMap((u) => u.anos).find((a) => a.ano === ano && a.momento !== null);
  const referencia = atual?.momento?.anoReferencia ?? null;
  const momento = pergunta === "momento" && referencia !== null;
  // A composição só existe por faixa; "todas" é só do momento.
  const faixaComposicao: FaixaLarga = faixa === "total" ? "18-29" : faixa;
  const linhas = momento
    ? linhasMomento(unidades, nivel, faixa, ano, anoBase)
    : linhasUnidades(unidades, nivel, faixaComposicao, ano, anoBase);
  const total = linhas.length;
  const mostradas = aberta ? linhas : linhas.slice(0, VISIVEIS);
  const escondidas = total - mostradas.length;
  const nomeUnidade = (codigo: string, nome: string) =>
    nivel === "distrito" ? t("votoAntecipado.geografia.distrito", { n: codigo }) : nome;

  return (
    <Painel
      className={className}
      sobrelinha={t("votoAntecipado.geografia.sobrelinha", { ano: anoBase })}
      titulo={
        momento
          ? t(
              faixa === "total"
                ? "votoAntecipado.geografia.tituloMomentoTodas"
                : "votoAntecipado.geografia.tituloMomento",
              { faixa: rotulo(faixa) },
            )
          : t("votoAntecipado.geografia.titulo", { faixa: rotulo(faixaComposicao) })
      }
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
        momento
          ? "votoAntecipado.geografia.metodoMomento"
          : comParticipacao
            ? "votoAntecipado.geografia.metodo"
            : "votoAntecipado.geografia.metodoSemParticipacao",
        { minimo: MINIMO_VOTOS_UNIDADE, referencia: referencia ?? anoBase },
      )}
    >
      <p className="max-w-[70ch] text-sm text-ink-2">
        {t(
          momento
            ? "votoAntecipado.geografia.textoMomento"
            : comParticipacao
              ? "votoAntecipado.geografia.texto"
              : "votoAntecipado.geografia.textoSemParticipacao",
          { ano: anoBase, referencia: referencia ?? anoBase },
        )}
      </p>
      <div className="flex flex-wrap gap-x-4 gap-y-2">
        {referencia !== null ? (
          <ControloSegmentado<Pergunta>
            rotuloGrupo={t("votoAntecipado.geografia.perguntaAria")}
            valor={pergunta}
            aoMudar={(v) => {
              setPergunta(v);
              if (v === "composicao" && faixa === "total") setFaixa("18-29");
            }}
            opcoes={[
              { valor: "composicao", rotulo: t("votoAntecipado.geografia.perguntas.composicao") },
              { valor: "momento", rotulo: t("votoAntecipado.geografia.perguntas.momento") },
            ]}
          />
        ) : null}
        <ControloSegmentado<FaixaMomento>
          rotuloGrupo={t("votoAntecipado.geografia.faixaAria")}
          valor={momento ? faixa : faixaComposicao}
          aoMudar={setFaixa}
          opcoes={(momento ? FAIXAS_MOMENTO : FAIXAS_LARGAS).map((f) => ({
            valor: f,
            rotulo: rotulo(f),
          }))}
        />
      </div>
      {momento ? (
        <Legenda>
          <ItemLegenda amostra={<Amostra className="fill-ink-3 opacity-45" />}>
            {t("votoAntecipado.legenda.habituais")}
          </ItemLegenda>
          <ItemLegenda amostra={<Amostra fill="url(#padrao-antecipacao)" />}>
            {t("votoAntecipado.legenda.antecipacao")}
          </ItemLegenda>
          <ItemLegenda amostra={<Amostra className="fill-up" />}>
            {t("votoAntecipado.legenda.novos")}
          </ItemLegenda>
        </Legenda>
      ) : null}
      <table id={id} className="w-full border-collapse text-sm">
        <caption className="sr-only">
          {t(
            momento
              ? faixa === "total"
                ? "votoAntecipado.geografia.legendaMomentoTodas"
                : "votoAntecipado.geografia.legendaMomento"
              : "votoAntecipado.geografia.legenda",
            {
              faixa: rotulo(momento ? faixa : faixaComposicao),
              nivel: t(`votoAntecipado.geografia.niveis.${nivel}`),
              ano: anoBase,
            },
          )}
        </caption>
        <thead>
          <tr className="rotulo text-left">
            <th scope="col" className="pr-2 pb-1.5 sm:pr-3 font-medium">
              {t(`votoAntecipado.geografia.niveis.${nivel}`)}
            </th>
            <th scope="col" className="pr-2 pb-1.5 sm:pr-3 text-right font-medium">
              {t(momento ? "votoAntecipado.geografia.novos" : "votoAntecipado.geografia.quota", {
                ano,
              })}
            </th>
            <th scope="col" className="pr-2 pb-1.5 sm:pr-3 text-right font-medium">
              {t("votoAntecipado.geografia.diferenca", { ano: anoBase })}
            </th>
            {momento ? (
              <th scope="col" className="pb-1.5 text-right font-medium">
                {t("votoAntecipado.geografia.habituais")}
              </th>
            ) : comParticipacao ? (
              <th scope="col" className="pb-1.5 text-right font-medium">
                {t("votoAntecipado.geografia.taxa")}
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
              <th scope="row" className="py-1.5 pr-2 sm:pr-3 text-left font-semibold">
                {nomeUnidade(l.codigo, l.nome)}
                <span className="block font-mono text-[11px] font-normal text-ink-3">
                  {t("votoAntecipado.geografia.votos", { n: formatarNumero(l.votos) })}
                  {l.poucosVotos ? ` · ${t("votoAntecipado.geografia.poucosVotos")}` : null}
                </span>
              </th>
              {"novos" in l ? (
                <>
                  <td className={CELULA}>
                    <span className="flex items-center justify-end gap-2">
                      <BarraMomento linha={l} />
                      {l.novos === null ? t("comum.semDados") : formatarPercentagem(l.novos)}
                    </span>
                  </td>
                  <td className={CELULA}>
                    {l.diferenca === null ? t("comum.semDados") : formatarPontos(l.diferenca)}
                  </td>
                  <td className="py-1.5 text-right font-mono text-[13px]">
                    {l.habituais === null ? t("comum.semDados") : formatarPercentagem(l.habituais)}
                  </td>
                </>
              ) : (
                <>
                  <td className={CELULA}>
                    <span className="flex items-center justify-end gap-2">
                      <BarraQuota quota={l.quota} base={l.quotaBase} />
                      {l.quota === null ? t("comum.semDados") : formatarPercentagem(l.quota)}
                    </span>
                  </td>
                  <td className={CELULA}>
                    {l.diferenca === null ? t("comum.semDados") : formatarPontos(l.diferenca)}
                  </td>
                  {comParticipacao ? (
                    <td className="py-1.5 text-right font-mono text-[13px]">
                      {l.taxa === null ? t("comum.semDados") : formatarPercentagem(l.taxa)}
                    </td>
                  ) : null}
                </>
              )}
            </tr>
          ))}
        </tbody>
      </table>
      {total > VISIVEIS ? (
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
