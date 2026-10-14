import Link from "next/link";
import type { SondagensCorrida } from "@intercalares/contratos";
import { Painel } from "@/components/ui/Painel.tsx";
import { Selo } from "@/components/ui/Selo.tsx";
import { ItemLegenda, Legenda } from "@/components/voto-antecipado/legendas.tsx";
import {
  formatarData,
  formatarDataCurta,
  formatarMargemPontos,
  formatarNumero,
  formatarPercentagem,
} from "@/lib/formatacao.ts";
import { caminhoPaginaCorrida } from "@/lib/corridas.ts";
import { t } from "@/lib/mensagens.ts";
import { caminhoCorrida, nomeCorrida, type VistaSondagens } from "@/lib/sondagens/vista.ts";
import { EvolucaoVotoGenerico, SerieSondagens } from "./graficos.tsx";

const METODOLOGIA =
  "https://github.com/tpereira2005/intercalares-eua-2026/blob/main/docs/metodologia/previsao.md#4-sondagens-do-senado";
const LIGACAO = "text-ink underline decoration-rule underline-offset-[3px]";

function data(dia: string): Date {
  return new Date(`${dia}T12:00:00Z`);
}

function fontes(vista: VistaSondagens) {
  return vista.fontes.length > 0 ? vista.fontes : [{ nome: t("sondagens.fonte") }];
}

function metodoMedia(vista: VistaSondagens): string {
  const m = vista.metodo;
  return t("sondagens.senado.metodo", {
    meia: formatarNumero(m.meia_vida_dias),
    janela: m.janela_dias,
    referencia: formatarNumero(m.amostra_referencia),
    maxima: formatarNumero(m.amostra_maxima),
    partidaria: formatarPercentagem(m.peso_partidaria, 0),
  });
}

function base(media: NonNullable<SondagensCorrida["media"]>): string {
  return media.institutos === 1
    ? t("sondagens.senado.base1", { sondagens: media.sondagens })
    : t("sondagens.senado.base2", { institutos: media.institutos, sondagens: media.sondagens });
}

function Cabecalho({
  vista,
  sobrelinha,
  titulo,
  lede,
}: {
  vista: VistaSondagens;
  sobrelinha: string;
  titulo: string;
  lede: string;
}) {
  return (
    <header className="flex flex-wrap items-start justify-between gap-x-6 gap-y-3">
      <div className="min-w-0">
        <p className="rotulo mb-1">{sobrelinha}</p>
        <h1 className="font-display text-[clamp(30px,5vw,40px)] leading-[1.02] font-bold">
          {titulo}
        </h1>
        <p className="mt-1.5 max-w-[68ch] text-[15.5px] text-ink-2">{lede}</p>
      </div>
      <span className="font-mono text-[11px] text-ink-3">
        {t("sondagens.atualizado", { data: formatarData(data(vista.corte)) })}
      </span>
    </header>
  );
}

/** Página /sondagens/: voto genérico e média de cada corrida ao Senado. */
export function PaginaSondagens({ vista }: { vista: VistaSondagens }) {
  const generico = vista.votoGenerico.at(-1);
  const primeiro = vista.votoGenerico[0];
  return (
    <div className="flex flex-col gap-4">
      <Cabecalho
        vista={vista}
        sobrelinha={t("sondagens.sobrelinha", { ano: vista.ano })}
        titulo={t("sondagens.titulo")}
        lede={t("sondagens.lede")}
      />

      <div className="grid gap-4 min-[960px]:grid-cols-[minmax(0,1fr)_minmax(0,1.6fr)]">
        {generico ? (
          <Painel
            className="self-start"
            sobrelinha={t("sondagens.generico.sobrelinha")}
            titulo={t("sondagens.generico.titulo")}
            descricao={t("sondagens.generico.texto", { data: formatarData(data(generico.data)) })}
            acessorio={<Selo variante="tracejado">{t("comum.selos.estimativa")}</Selo>}
            fontes={fontes(vista)}
            metodo={t("sondagens.generico.metodo")}
          >
            <p className="flex items-baseline gap-3">
              <span className="font-display text-[44px] leading-none font-extrabold">
                {formatarMargemPontos(generico.margem)}
              </span>
              <span className="text-sm text-ink-2">{t("sondagens.generico.media")}</span>
            </p>
            <table className="w-full border-collapse text-sm">
              <caption className="sr-only">{t("sondagens.generico.legenda")}</caption>
              <thead>
                <tr className="rotulo text-left">
                  <th scope="col" className="pb-1.5 font-medium">
                    {t("sondagens.generico.agregador")}
                  </th>
                  <th scope="col" className="pb-1.5 text-right font-medium">
                    {t("sondagens.generico.margem")}
                  </th>
                </tr>
              </thead>
              <tbody>
                {generico.agregadores.map((a) => (
                  <tr key={a.nome} className="border-t border-rule-2">
                    <th scope="row" className="py-1.5 text-left font-normal">
                      {a.nome}
                    </th>
                    <td className="py-1.5 text-right font-mono">
                      {formatarMargemPontos(a.margem)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            {primeiro && vista.votoGenerico.length > 1 ? (
              <EvolucaoVotoGenerico
                titulo={t("sondagens.generico.aria", {
                  de: formatarMargemPontos(primeiro.margem),
                  ate: formatarMargemPontos(generico.margem),
                })}
                pontos={vista.votoGenerico}
              />
            ) : (
              <p className="text-[12.5px] text-ink-3">{t("sondagens.generico.evolucaoNota")}</p>
            )}
          </Painel>
        ) : null}

        <Painel
          sobrelinha={t("sondagens.senado.sobrelinha")}
          titulo={t("sondagens.senado.titulo")}
          descricao={t("sondagens.senado.texto")}
          acessorio={<Selo variante="tracejado">{t("comum.selos.estimativa")}</Selo>}
          fontes={fontes(vista)}
          metodo={metodoMedia(vista)}
        >
          <table className="w-full border-collapse text-sm">
            <caption className="sr-only">{t("sondagens.senado.legenda")}</caption>
            <thead>
              <tr className="rotulo text-left">
                <th scope="col" className="pr-3 pb-1.5 font-medium">
                  {t("sondagens.senado.corrida")}
                </th>
                <th scope="col" className="pr-3 pb-1.5 text-right font-medium">
                  {t("sondagens.senado.media")}
                </th>
                <th scope="col" className="hidden pb-1.5 font-medium sm:table-cell">
                  {t("sondagens.senado.base")}
                </th>
              </tr>
            </thead>
            <tbody>
              {vista.corridas.map((c) => (
                <tr key={c.id} className="border-t border-rule-2 align-top">
                  <th scope="row" className="py-2 pr-3 text-left font-semibold">
                    <Link href={caminhoCorrida(c.id)} className={LIGACAO}>
                      {nomeCorrida(c)}
                    </Link>
                    {c.candidato_d && c.candidato_r ? (
                      <span className="block text-[12px] font-normal text-ink-3">
                        {t("sondagens.corrida.candidatos", { d: c.candidato_d, r: c.candidato_r })}
                      </span>
                    ) : null}
                  </th>
                  <td className="py-2 pr-3 text-right font-mono">
                    {c.media ? (
                      <span className="whitespace-nowrap">
                        {formatarMargemPontos(c.media.margem)}
                      </span>
                    ) : (
                      <span className="text-[12px] text-ink-3">
                        {t("sondagens.senado.semMedia")}
                      </span>
                    )}
                  </td>
                  <td className="hidden py-2 font-mono text-[12px] text-ink-2 sm:table-cell">
                    {c.media ? base(c.media) : null}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </Painel>
      </div>
    </div>
  );
}

/** Página de uma corrida: média, série e tabela das sondagens. */
export function PaginaCorridaSondagens({
  vista,
  corrida: c,
}: {
  vista: VistaSondagens;
  corrida: SondagensCorrida;
}) {
  const nome = nomeCorrida(c);
  return (
    <div className="flex flex-col gap-4">
      <Cabecalho
        vista={vista}
        sobrelinha={t("sondagens.corrida.sobrelinha")}
        titulo={nome}
        lede={
          c.candidato_d && c.candidato_r
            ? t("sondagens.corrida.candidatos", { d: c.candidato_d, r: c.candidato_r })
            : ""
        }
      />

      <Painel
        titulo={t("sondagens.corrida.mediaTitulo")}
        descricao={t("sondagens.corrida.mediaTexto")}
        acessorio={<Selo variante="tracejado">{t("comum.selos.estimativa")}</Selo>}
        fontes={fontes(vista)}
        metodo={metodoMedia(vista)}
      >
        <p className="text-[15px]">
          {c.media
            ? t("sondagens.corrida.mediaAtual", {
                data: formatarData(data(c.media.data)),
                margem: formatarMargemPontos(c.media.margem),
                base: base(c.media),
              })
            : t("sondagens.corrida.semMedia", { janela: vista.metodo.janela_dias })}
        </p>
        <Legenda>
          <ItemLegenda
            amostra={
              <svg width={18} height={10}>
                <line x1={0} x2={18} y1={5} y2={5} strokeWidth={2.25} className="stroke-ink" />
              </svg>
            }
          >
            {t("sondagens.corrida.legendaMedia")}
          </ItemLegenda>
          <ItemLegenda
            amostra={
              <svg width={10} height={10}>
                <circle cx={5} cy={5} r={3.5} className="fill-ink-3" />
              </svg>
            }
          >
            {t("sondagens.corrida.legendaDentro")}
          </ItemLegenda>
          <ItemLegenda
            amostra={
              <svg width={10} height={10}>
                <circle
                  cx={5}
                  cy={5}
                  r={3.5}
                  strokeWidth={1.25}
                  className="fill-sheet stroke-ink-3"
                />
              </svg>
            }
          >
            {t("sondagens.corrida.legendaFora")}
          </ItemLegenda>
        </Legenda>
        <SerieSondagens
          titulo={t("sondagens.corrida.aria", {
            estado: nome,
            margem: c.media ? formatarMargemPontos(c.media.margem) : t("comum.semDados"),
          })}
          serie={c.serie}
          sondagens={c.sondagens}
        />
      </Painel>

      <Painel
        titulo={t("sondagens.corrida.tabelaTitulo")}
        descricao={t("sondagens.corrida.tabelaTexto")}
        fontes={fontes(vista)}
        metodo={metodoMedia(vista)}
      >
        <div className="overflow-x-auto">
          <table className="w-full border-collapse text-sm">
            <caption className="sr-only">{t("sondagens.corrida.legenda")}</caption>
            <thead>
              <tr className="rotulo text-left">
                <th scope="col" className="pr-3 pb-1.5 font-medium">
                  {t("sondagens.corrida.instituto")}
                </th>
                <th scope="col" className="pr-3 pb-1.5 text-right font-medium">
                  {t("sondagens.corrida.margem")}
                </th>
                <th scope="col" className="pb-1.5 text-right font-medium">
                  {t("sondagens.corrida.peso")}
                </th>
              </tr>
            </thead>
            <tbody>
              {c.sondagens.map((s, i) => (
                <tr
                  key={`${s.instituto}-${s.fim}-${String(i)}`}
                  className={`border-t border-rule-2 align-top ${s.peso === 0 ? "text-ink-3" : ""}`}
                >
                  <th scope="row" className="py-1.5 pr-3 text-left font-semibold">
                    {s.instituto}
                    <span className="block font-mono text-[11px] font-normal text-ink-3">
                      {[
                        formatarDataCurta(data(s.fim)),
                        s.amostra === null ? null : `n=${formatarNumero(s.amostra)}`,
                        t(
                          `sondagens.corrida.populacoes.${s.populacao === "?" ? "?" : s.populacao}`,
                        ),
                        s.partidaria ? t("sondagens.corrida.partidaria") : null,
                      ]
                        .filter(Boolean)
                        .join(" · ")}
                    </span>
                  </th>
                  <td className="py-1.5 pr-3 text-right font-mono whitespace-nowrap">
                    {formatarMargemPontos(s.margem, 0)}
                    <span className="block text-[11px] text-ink-3">
                      {`D ${formatarNumero(s.percentagem_d)} · R ${formatarNumero(s.percentagem_r)}`}
                    </span>
                  </td>
                  <td className="py-1.5 text-right font-mono">{formatarPercentagem(s.peso, 0)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Painel>

      <p className="flex flex-wrap gap-x-5 gap-y-1.5 text-sm">
        <Link href="/sondagens/" className={LIGACAO}>
          {t("sondagens.corrida.voltar")}
        </Link>
        <Link href={caminhoPaginaCorrida(c.id)} className={LIGACAO}>
          {t("sondagens.corrida.previsao")}
        </Link>
        <a href={METODOLOGIA} rel="noopener noreferrer" className={LIGACAO}>
          {t("sondagens.corrida.metodologia")}
        </a>
      </p>
    </div>
  );
}
