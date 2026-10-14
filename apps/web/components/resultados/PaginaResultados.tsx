import type { ReactNode } from "react";
import { FaixaKpis, Kpi } from "@/components/ui/Kpi.tsx";
import { Painel } from "@/components/ui/Painel.tsx";
import { Selo } from "@/components/ui/Selo.tsx";
import { nomeEstado } from "@/lib/estados.ts";
import { formatarData, formatarDataHora } from "@/lib/formatacao.ts";
import { t } from "@/lib/mensagens.ts";
import type { DadosNoiteEleitoral } from "@/lib/resultados/carregar.ts";
import type { VistaResultados } from "@/lib/resultados/vista.ts";
import { PainelFalta } from "./PainelFalta.tsx";
import { PainelProjecao } from "./PainelProjecao.tsx";
import { Chamada, TabelaResultados } from "./TabelaResultados.tsx";

const METODOLOGIA = "/metodologia/resultados/";
const LIGACAO = "text-ink underline decoration-rule underline-offset-[3px]";
/** Linhas mostradas antes de "ver as outras". */
const VISIVEIS = 20;
/** Chamadas listadas ao lado da cobertura. */
const MAX_CHAMADAS = 12;

function hora(instante: string): string {
  return formatarDataHora(new Date(instante));
}

function Indicadores({ vista }: { vista: VistaResultados }) {
  const comVotos = vista.aoVivo.filter((l) => (l.contagem?.total ?? 0) > 0).length;
  const estados = vista.cobertura.filter((c) => c.corridas > 0).length;
  const horas = vista.cobertura.flatMap((c) => (c.atualizadoEm ? [c.atualizadoEm] : []));
  const ultima = horas.reduce<string | null>(
    (max, h) => (max === null || Date.parse(h) > Date.parse(max) ? h : max),
    null,
  );
  return (
    <FaixaKpis>
      <Kpi
        rotulo={t("resultados.kpis.corridas")}
        valor={comVotos}
        detalhe={t("resultados.kpis.corridasDetalhe", { n: vista.aoVivo.length })}
      />
      <Kpi
        rotulo={t("resultados.kpis.estados")}
        valor={estados}
        detalhe={t("resultados.kpis.estadosDetalhe", { n: vista.cobertura.length })}
      />
      <Kpi
        rotulo={t("resultados.kpis.atualizacao")}
        valor={<span className="text-[26px]">{ultima ? hora(ultima) : t("comum.semDados")}</span>}
        detalhe={t("resultados.kpis.atualizacaoDetalhe", { hora: hora(vista.instante) })}
      />
    </FaixaKpis>
  );
}

/** Chamadas das redações registadas, da mais recente para a mais antiga. */
function Chamadas({ vista }: { vista: VistaResultados }) {
  const lado = (l: "D" | "R" | "outro") => vista.chamadas.filter((c) => c.vencedor === l).length;
  return (
    <div className="mt-4 border-t border-rule-2 pt-3">
      <h2 className="rotulo mb-1">{t("resultados.chamadas.titulo")}</h2>
      {vista.chamadas.length === 0 ? (
        <p className="text-ink-2">{t("resultados.chamadas.nenhuma")}</p>
      ) : (
        <>
          <p className="mb-2 text-ink-2">
            {t("resultados.chamadas.resumo", {
              n: vista.chamadas.length,
              d: lado("D"),
              r: lado("R"),
            })}
          </p>
          <ul className="flex flex-col gap-1.5">
            {vista.chamadas.slice(0, MAX_CHAMADAS).map((c) => (
              <li key={c.corrida}>
                <span className="font-semibold">{c.corrida}</span>
                <Chamada c={c} />
              </li>
            ))}
          </ul>
        </>
      )}
      <p className="mt-2 text-[12px] text-ink-3">{t("resultados.chamadas.nota")}</p>
    </div>
  );
}

function Cobertura({ vista }: { vista: VistaResultados }) {
  return (
    <section className="self-start rounded-md border border-rule bg-sheet px-[18px] py-3.5 text-sm">
      <h2 className="rotulo mb-1">{t("resultados.cobertura.titulo")}</h2>
      <p className="mb-2 text-ink-2">{t("resultados.cobertura.texto")}</p>
      <dl className="grid grid-cols-[auto_minmax(0,1fr)] gap-x-4 gap-y-1.5">
        {vista.cobertura.map((c) => (
          <div key={c.estado} className="contents">
            <dt className="font-semibold">{nomeEstado(c.estado)}</dt>
            <dd className="text-ink-2">
              {c.corridas === 0
                ? t("resultados.cobertura.aEspera")
                : c.atualizadoEm
                  ? t("resultados.cobertura.comDados", {
                      n: c.corridas,
                      hora: hora(c.atualizadoEm),
                    })
                  : t("resultados.cobertura.comDadosSemHora", { n: c.corridas })}
              {c.soTotal || c.parcial ? (
                <span className="block text-[12px] text-ink-3">
                  {c.soTotal
                    ? t("resultados.cobertura.soTotal")
                    : (c.nota ?? t("resultados.cobertura.parcial"))}
                </span>
              ) : null}
            </dd>
          </div>
        ))}
      </dl>
      <p className="mt-3 text-ink-2">{t("resultados.cobertura.fora")}</p>
      <Chamadas vista={vista} />
      <p className="mt-3">
        <a href={METODOLOGIA} rel="noopener noreferrer" className={LIGACAO}>
          {t("resultados.cobertura.documentacao")}
        </a>
      </p>
    </section>
  );
}

/** Contagem oficial por corrida, cobertura e corridas sem dados ao vivo. */
function Contagem({ vista }: { vista: VistaResultados }) {
  const notaPrevisao =
    vista.cortePrevisao === null
      ? null
      : t(
          vista.previsaoCongelada ? "resultados.previsaoNota" : "resultados.previsaoNotaProvisoria",
          {
            data: formatarData(new Date(`${vista.cortePrevisao}T12:00:00Z`)),
          },
        );
  return (
    <>
      <Indicadores vista={vista} />

      <div className="grid gap-4 min-[960px]:grid-cols-[minmax(0,2fr)_minmax(0,1fr)]">
        <Painel
          sobrelinha={t("resultados.aoVivo.sobrelinha")}
          titulo={t("resultados.aoVivo.titulo")}
          descricao={
            notaPrevisao
              ? `${t("resultados.aoVivo.texto")} ${notaPrevisao}`
              : t("resultados.aoVivo.texto")
          }
          acessorio={vista.ensaio ? null : <Selo variante="sinal">{t("comum.selos.aoVivo")}</Selo>}
          fontes={vista.fontes}
          metodo={t("resultados.aoVivo.metodo")}
        >
          {vista.aoVivo.length > 0 ? (
            <TabelaResultados
              linhas={vista.aoVivo}
              legenda={t("resultados.aoVivo.legenda")}
              comContagem
              visiveis={VISIVEIS}
            />
          ) : (
            <p className="text-ink-2">{t("resultados.aoVivo.vazio")}</p>
          )}
        </Painel>
        <Cobertura vista={vista} />
      </div>

      <PainelFalta vista={vista} />

      {vista.semDados.length > 0 ? (
        <Painel
          sobrelinha={t("resultados.semDados.sobrelinha")}
          titulo={t("resultados.semDados.titulo")}
          descricao={[
            t(
              vista.semDados.some((l) => l.projecao !== null)
                ? "resultados.semDados.textoComProjecao"
                : "resultados.semDados.texto",
            ),
            notaPrevisao,
          ]
            .filter(Boolean)
            .join(" ")}
          acessorio={<Selo variante="tracejado">{t("comum.selos.estimativa")}</Selo>}
          fontes={[{ nome: t("resultados.semDados.fonte"), url: "/previsao/" }]}
          metodo={t("resultados.semDados.metodo")}
        >
          <TabelaResultados
            linhas={vista.semDados}
            legenda={t("resultados.semDados.legenda")}
            comContagem={false}
            visiveis={VISIVEIS}
          />
        </Painel>
      ) : null}
    </>
  );
}

/** Página da noite eleitoral: projeção do modelo, contagem oficial e previsão congelada. */
export function PaginaResultados({
  resultados,
  noite,
  ligacao = null,
}: DadosNoiteEleitoral & { ligacao?: ReactNode }) {
  const instante = resultados?.instante ?? noite?.instante;
  return (
    <div className="flex flex-col gap-4">
      <header className="flex flex-wrap items-start justify-between gap-x-6 gap-y-3">
        <div className="min-w-0">
          <p className="rotulo mb-1">{t("resultados.sobrelinha")}</p>
          <h1 className="font-display text-[clamp(30px,5vw,40px)] leading-[1.02] font-bold">
            {t("resultados.titulo")}
          </h1>
          <p className="mt-1.5 max-w-[68ch] text-[15.5px] text-ink-2">{t("resultados.lede")}</p>
        </div>
        <div className="flex flex-col items-start gap-1.5 sm:items-end">
          {resultados ? (
            resultados.ensaio ? (
              <Selo variante="tracejado">{t("resultados.ensaio")}</Selo>
            ) : (
              <Selo variante="solido">{t("comum.selos.oficial")}</Selo>
            )
          ) : null}
          {instante ? (
            <span className="font-mono text-[11px] text-ink-3">
              {t("resultados.retrato", { hora: hora(instante) })}
            </span>
          ) : null}
          {ligacao}
        </div>
      </header>

      {resultados?.ensaio ? (
        <p
          role="note"
          className="rounded-md border border-dashed border-ink-3 bg-sheet px-[18px] py-3 text-sm text-ink-2"
        >
          {t("resultados.ensaioAviso", { ano: resultados.ano })}
        </p>
      ) : null}

      {noite ? <PainelProjecao noite={noite} /> : null}

      {resultados ? <Contagem vista={resultados} /> : null}
    </div>
  );
}
