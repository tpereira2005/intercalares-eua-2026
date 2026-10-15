import Link from "next/link";
import { Painel, type ReferenciaFonte } from "@/components/ui/Painel.tsx";
import { QualidadeDados } from "@/components/ui/QualidadeDados.tsx";
import { Selo } from "@/components/ui/Selo.tsx";
import { Amostra, ItemLegenda, Legenda } from "@/components/voto-antecipado/legendas.tsx";
import { caminhoEstado } from "@/components/voto-antecipado/PaginaEstado.tsx";
import { GRUPOS, type EstadoDemografia, type Grupo, type Momento } from "@/lib/demografia.ts";
import { nomeEstado } from "@/lib/estados.ts";
import {
  formatarCompacto,
  formatarData,
  formatarMargem,
  formatarPercentagem,
  formatarVariacao,
} from "@/lib/formatacao.ts";
import { t } from "@/lib/mensagens.ts";
import type { ResumoEstado } from "@/lib/voto-antecipado/resumo.ts";
import { DesvioEstados, Halteres, MomentoEstados, type LinhaMomento } from "./graficos.tsx";

const LIGACAO = "text-ink underline decoration-rule underline-offset-[3px]";

function Estimativa() {
  return <Selo variante="tracejado">{t("comum.selos.estimativa")}</Selo>;
}

function rotuloGrupo(grupo: Grupo, e: EstadoDemografia): string {
  return grupo === "jovens" && e.soMenos25
    ? t("demografia.grupos.jovensSo24")
    : t(`demografia.grupos.${grupo}`);
}

function PainelComposicao({
  estados,
  fontes,
}: {
  estados: readonly EstadoDemografia[];
  fontes: readonly ReferenciaFonte[];
}) {
  const algumSo24 = estados.some((e) => e.soMenos25);
  return (
    <Painel
      sobrelinha={t("demografia.composicao.sobrelinha")}
      titulo={t("demografia.composicao.titulo")}
      descricao={t("demografia.composicao.texto")}
      fontes={fontes}
      metodo={t("demografia.composicao.metodo")}
    >
      <div className="grid gap-5 md:grid-cols-2">
        {GRUPOS.map((grupo) => {
          const linhas = estados.flatMap((e) => {
            const c = e.composicao[grupo];
            if (!c || e.anoBase === null) return [];
            const marca = grupo === "jovens" && e.soMenos25 ? "*" : "";
            return [
              {
                rotulo: `${nomeEstado(e.estado)}${marca} · ${String(e.anoBase)} → 2026`,
                quota: c.quota,
                quotaBase: c.quotaBase,
                aria: t("demografia.composicao.linhaAria", {
                  estado: nomeEstado(e.estado),
                  base: formatarPercentagem(c.quotaBase),
                  ano: e.anoBase,
                  atual: formatarPercentagem(c.quota),
                }),
              },
            ];
          });
          return (
            <figure key={grupo} className="flex min-w-0 flex-col gap-1.5">
              <figcaption className="rotulo">{t(`demografia.gruposNome.${grupo}`)}</figcaption>
              <Halteres
                titulo={t("demografia.composicao.aria", {
                  grupo: t(`demografia.gruposNome.${grupo}`),
                  lista: linhas.map((l) => l.aria).join("; "),
                })}
                linhas={linhas}
              />
            </figure>
          );
        })}
      </div>
      <Legenda>
        <ItemLegenda
          amostra={
            <svg width={12} height={12}>
              <circle
                cx={6}
                cy={6}
                r={4.5}
                strokeWidth={1.75}
                className="fill-sheet stroke-ink-2"
              />
            </svg>
          }
        >
          {t("votoAntecipado.legenda.mesmoDia", { ano: t("demografia.anoReferencia") })}
        </ItemLegenda>
        <ItemLegenda
          amostra={
            <svg width={12} height={12}>
              <circle cx={6} cy={6} r={5.5} className="fill-signal" />
            </svg>
          }
        >
          2026
        </ItemLegenda>
      </Legenda>
      {algumSo24 ? (
        <p className="font-mono text-[11px] text-ink-3">{t("demografia.composicao.notaSo24")}</p>
      ) : null}
    </Painel>
  );
}

function PainelParticipacao({
  estados,
  fontes,
}: {
  estados: readonly EstadoDemografia[];
  fontes: readonly ReferenciaFonte[];
}) {
  const comDesvio = estados.filter((e) => e.desvio.todos !== null);
  const grupos = comDesvio.map((e) => ({
    rotulo: `${nomeEstado(e.estado)} · ${t("votoAntecipado.legenda.variacaoFace", { ano: e.anoBase ?? "" })}`,
    valores: [
      { chave: "todos", rotulo: t("demografia.participacao.todos"), valor: e.desvio.todos },
      ...GRUPOS.map((g) => ({ chave: g, rotulo: rotuloGrupo(g, e), valor: e.desvio[g] })),
    ],
  }));
  return (
    <Painel
      sobrelinha={t("demografia.participacao.sobrelinha")}
      titulo={t("demografia.participacao.titulo")}
      descricao={t("demografia.participacao.texto")}
      acessorio={<Estimativa />}
      fontes={fontes}
      metodo={t("demografia.participacao.metodo")}
    >
      {grupos.length > 0 ? (
        <>
          <DesvioEstados
            titulo={t("demografia.participacao.aria", {
              lista: grupos
                .flatMap((g) =>
                  g.valores.map((v) =>
                    t("demografia.participacao.linhaAria", {
                      estado: g.rotulo,
                      grupo: v.rotulo,
                      valor: v.valor === null ? "—" : formatarVariacao(v.valor),
                    }),
                  ),
                )
                .join("; "),
            })}
            grupos={grupos}
          />
          <Legenda>
            <ItemLegenda amostra={<Amostra className="fill-up" />}>
              {t("votoAntecipado.legenda.acima")}
            </ItemLegenda>
            <ItemLegenda amostra={<Amostra className="fill-down" />}>
              {t("votoAntecipado.legenda.abaixo")}
            </ItemLegenda>
          </Legenda>
          <p className="text-[12.5px] text-ink-3">{t("demografia.participacao.intervalo")}</p>
        </>
      ) : (
        <p className="text-sm text-ink-2">{t("demografia.participacao.semDados")}</p>
      )}
    </Painel>
  );
}

function linhaMomento(
  chave: string,
  rotulo: string,
  secundaria: boolean,
  m: Momento | null,
): LinhaMomento[] {
  return m ? [{ chave, rotulo, secundaria, ...m }] : [];
}

function PainelMomento({
  estados,
  fontes,
}: {
  estados: readonly EstadoDemografia[];
  fontes: readonly ReferenciaFonte[];
}) {
  const comMomento = estados.filter((e) => e.momento !== null);
  const grupos = comMomento.flatMap((e) => {
    const m = e.momento;
    if (!m) return [];
    const referencia = m.anoReferencia ?? "";
    return [
      {
        rotulo: `${nomeEstado(e.estado)} · ${t("demografia.momento.rotuloAno", { ano: 2026, referencia })}`,
        linhas: (["todos", ...GRUPOS] as const).flatMap((g) => {
          const rotulo = g === "todos" ? t("demografia.participacao.todos") : rotuloGrupo(g, e);
          return [
            ...linhaMomento(`${e.estado}-${g}`, rotulo, false, m.grupos[g].atual),
            ...linhaMomento(
              `${e.estado}-${g}-base`,
              String(m.anoComparar ?? ""),
              true,
              m.grupos[g].base,
            ),
          ];
        }),
      },
    ];
  });
  const aria = grupos
    .flatMap((g) =>
      g.linhas.map((l) =>
        t("demografia.momento.linhaAria", {
          estado: g.rotulo,
          grupo: l.rotulo,
          ano: l.secundaria ? l.rotulo : 2026,
          habituais: formatarPercentagem(l.habituais, 0),
          antecipacao: formatarPercentagem(l.antecipacao, 0),
          novos: formatarPercentagem(l.novos, 0),
        }),
      ),
    )
    .join("; ");
  return (
    <Painel
      sobrelinha={t("demografia.momento.sobrelinha")}
      titulo={t("demografia.momento.titulo")}
      descricao={t("demografia.momento.texto")}
      fontes={fontes}
      metodo={t("demografia.momento.metodo")}
    >
      {grupos.length > 0 ? (
        <>
          <MomentoEstados titulo={t("demografia.momento.aria", { lista: aria })} grupos={grupos} />
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
        </>
      ) : (
        <p className="text-sm text-ink-2">{t("demografia.momento.semDados")}</p>
      )}
    </Painel>
  );
}

const CELULA =
  "py-1.5 pr-2 text-right font-mono text-[12.5px] whitespace-nowrap sm:pr-3 sm:text-[13px]";
const CABECALHO = "pr-2 pb-1.5 text-right font-medium sm:pr-3";

/** Ritmo, vantagem por partido de registo e peso do correio, estado a estado. */
function PainelPartidoModo({
  resumos,
  fontes,
}: {
  resumos: readonly ResumoEstado[];
  fontes: readonly ReferenciaFonte[];
}) {
  const semDados = t("comum.semDados");
  return (
    <Painel
      sobrelinha={t("demografia.partidoModo.sobrelinha")}
      titulo={t("demografia.partidoModo.titulo")}
      descricao={t("demografia.partidoModo.texto")}
      fontes={fontes}
      metodo={t("demografia.partidoModo.metodo")}
    >
      {resumos.some((r) => r.vantagemDemRep !== null) ? null : (
        <p className="text-sm text-ink-2">{t("demografia.partidoModo.semPartido")}</p>
      )}
      {/* Em ecrãs estreitos a tabela desliza dentro de si: foco de teclado e nome (2.1.1). */}
      <div
        className="overflow-x-auto"
        tabIndex={0}
        role="region"
        aria-label={t("demografia.partidoModo.regiao")}
      >
        <table className="w-full border-collapse text-sm">
          <caption className="sr-only">{t("demografia.partidoModo.legenda")}</caption>
          <thead>
            <tr className="rotulo">
              <th scope="col" className="pr-3 pb-1.5 text-left font-medium">
                {t("demografia.partidoModo.colunas.estado")}
              </th>
              <th scope="col" className={CABECALHO}>
                {t("demografia.partidoModo.colunas.ritmo")}
              </th>
              <th scope="col" className={CABECALHO}>
                {t("demografia.partidoModo.colunas.vantagem")}
              </th>
              <th scope="col" className={CABECALHO}>
                {t("demografia.partidoModo.colunas.vantagemBase")}
              </th>
              <th scope="col" className="pb-1.5 text-right font-medium">
                {t("demografia.partidoModo.colunas.correio")}
              </th>
            </tr>
          </thead>
          <tbody>
            {resumos.map((r) => (
              <tr key={r.estado} className="border-t border-rule-2">
                <th scope="row" className="py-1.5 pr-3 text-left font-semibold">
                  <Link href={caminhoEstado(r.estado)} prefetch={false} className={LIGACAO}>
                    {nomeEstado(r.estado)}
                  </Link>
                </th>
                <td className={CELULA}>
                  {r.variacaoVotos === null ? semDados : formatarVariacao(r.variacaoVotos)}
                </td>
                <td className={CELULA}>
                  {r.vantagemDemRep === null ? semDados : formatarMargem(r.vantagemDemRep)}
                </td>
                <td className={`${CELULA} text-ink-2`}>
                  {r.vantagemDemRepBase === null || r.anoBase === null ? (
                    semDados
                  ) : (
                    <>
                      {formatarMargem(r.vantagemDemRepBase)}
                      <span className="block text-[11px] text-ink-3">{r.anoBase}</span>
                    </>
                  )}
                </td>
                <td className="py-1.5 text-right font-mono text-[12.5px] sm:text-[13px]">
                  {r.quotaCorreio === null ? semDados : formatarPercentagem(r.quotaCorreio)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Painel>
  );
}

function PainelEstados({ estados }: { estados: readonly EstadoDemografia[] }) {
  return (
    <Painel titulo={t("demografia.estados.titulo")} descricao={t("demografia.estados.texto")}>
      <ul className="flex flex-col gap-2 text-sm">
        {estados.map((e) => (
          <li key={e.estado} className="flex flex-wrap items-center gap-x-3 gap-y-1">
            <QualidadeDados nivel={e.qualidade} />
            <Link href={caminhoEstado(e.estado)} prefetch={false} className={LIGACAO}>
              {t("demografia.estados.linha", {
                estado: nomeEstado(e.estado),
                votos: formatarCompacto(e.votos),
              })}
            </Link>
            <span className="text-[12.5px] text-ink-3">{t(`comum.qualidade.${e.qualidade}`)}</span>
          </li>
        ))}
      </ul>
      <p className="text-sm">
        <Link href="/mapa/" className={LIGACAO}>
          {t("demografia.estados.mapa")}
        </Link>
      </p>
    </Painel>
  );
}

export function PaginaDemografia({
  estados,
  resumos,
  fontes,
  fontesResumos,
  dadosAte,
}: {
  estados: readonly EstadoDemografia[];
  /** Todos os estados acompanhados, com ou sem idade. */
  resumos: readonly ResumoEstado[];
  fontes: readonly ReferenciaFonte[];
  fontesResumos: readonly ReferenciaFonte[];
  dadosAte: { data: string; dias: number } | null;
}) {
  return (
    <div className="flex flex-col gap-4">
      <header className="flex min-w-0 flex-col gap-2">
        <p className="rotulo">{t("demografia.sobrelinha", { ano: 2026 })}</p>
        <h1 className="font-display text-[clamp(30px,5vw,40px)] leading-[1.02] font-bold">
          {t("demografia.titulo")}
        </h1>
        <p className="max-w-[68ch] text-ink-2">{t("demografia.lede")}</p>
        {dadosAte ? (
          <p className="font-mono text-[11px] text-ink-3">
            {t("demografia.dadosAte", {
              data: formatarData(new Date(`${dadosAte.data}T12:00:00Z`)),
              dias: dadosAte.dias,
            })}
          </p>
        ) : null}
      </header>
      {resumos.length > 0 ? <PainelPartidoModo resumos={resumos} fontes={fontesResumos} /> : null}
      <PainelComposicao estados={estados} fontes={fontes} />
      <div className="grid gap-4 lg:grid-cols-2">
        <PainelParticipacao estados={estados} fontes={fontes} />
        <PainelMomento estados={estados} fontes={fontes} />
      </div>
      <PainelEstados estados={estados} />
    </div>
  );
}
