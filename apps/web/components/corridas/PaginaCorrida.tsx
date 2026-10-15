import { CorridaAoVivo } from "./CorridaAoVivo.tsx";
import { VersaoPrevisao } from "@/components/previsao/PaginaPrevisao.tsx";
import { PainelPrognosticosCorrida } from "@/components/previsao/PainelPrognosticos.tsx";
import type { ComparacaoCorrida, VistaPrognosticos } from "@/lib/previsao/prognosticos.ts";
import type { Fase } from "@/lib/fases.ts";
import Link from "next/link";
import { EvolucaoControlo, OrigemMargem } from "@/components/previsao/graficos.tsx";
import { FaixaKpis, Kpi } from "@/components/ui/Kpi.tsx";
import { Painel } from "@/components/ui/Painel.tsx";
import { Selo } from "@/components/ui/Selo.tsx";
import { caminhoEstado } from "@/components/voto-antecipado/PaginaEstado.tsx";
import { evolucaoCorrida, fechoDoEstado, limitesMargem, tituloCorrida } from "@/lib/corridas.ts";
import {
  formatarData,
  formatarDataCurta,
  formatarDataHora,
  formatarHora,
  formatarMargemPontos as margem,
  formatarPercentagem,
} from "@/lib/formatacao.ts";
import { t } from "@/lib/mensagens.ts";
import {
  categoria,
  type CorridaVista,
  type PontoCorrida,
  type VistaPrevisao,
} from "@/lib/previsao/vista.ts";

const LIGACAO = "text-ink underline decoration-rule underline-offset-[3px]";
const LISBOA = "Europe/Lisbon";

function data(dia: string): Date {
  return new Date(`${dia}T12:00:00Z`);
}

function Estimativa() {
  return <Selo variante="tracejado">{t("comum.selos.estimativa")}</Selo>;
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
    <li className="flex items-center gap-2">
      <span
        aria-hidden="true"
        className={`inline-block size-3 shrink-0 rounded-[2px] ${lado === "D" ? "fundo-dem" : "fundo-rep"}`}
      />
      <span className="sr-only">{t(`previsao.partidos.${lado}`)}: </span>
      <span>
        {nome ?? <span className="text-ink-3">{t("previsao.tabela.semCandidato")}</span>}
        {extras.length > 0 ? <span className="text-ink-3"> ({extras.join(", ")})</span> : null}
      </span>
    </li>
  );
}

function Indicadores({ c }: { c: CorridaVista }) {
  const lado = c.probD >= 0.5 ? "D" : "R";
  const outro = lado === "D" ? "R" : "D";
  const prob = lado === "D" ? c.probD : 1 - c.probD;
  return (
    <FaixaKpis>
      <Kpi
        rotulo={t("corrida.kpis.prob")}
        valor={`${lado} ${formatarPercentagem(prob, 0)}`}
        detalhe={t("corrida.kpis.probDetalhe", {
          categoria: t(`previsao.categorias.${categoria(c.probD)}`),
          outro,
          prob: formatarPercentagem(1 - prob, 0),
        })}
      />
      {c.decidida ? (
        <Kpi
          rotulo={t("corrida.kpis.margem")}
          valor={t("corrida.kpis.decidida")}
          detalhe={t("corrida.kpis.decididaDetalhe")}
        />
      ) : (
        <Kpi
          rotulo={t("corrida.kpis.margem")}
          valor={margem(c.margem)}
          detalhe={t("corrida.kpis.margemDetalhe", {
            de: margem(c.margemP10, 0),
            ate: margem(c.margemP90, 0),
          })}
        />
      )}
      <Kpi
        rotulo={t("corrida.kpis.pvi")}
        valor={margem(c.pvi, 0)}
        detalhe={t("corrida.kpis.pviDetalhe")}
      />
    </FaixaKpis>
  );
}

function PainelOrigem({ c, vista }: { c: CorridaVista; vista: VistaPrevisao }) {
  const descricao = c.decidida
    ? t("corrida.origem.decidida")
    : c.sondagens
      ? t("corrida.origem.texto")
      : t("corrida.origem.textoSemSondagens");
  return (
    <Painel
      sobrelinha={t("corrida.origem.sobrelinha")}
      titulo={t("corrida.origem.titulo")}
      descricao={descricao}
      acessorio={<Estimativa />}
      fontes={vista.fontes}
      metodo={t(c.camara === "senado" ? "corrida.origem.metodo" : "corrida.origem.metodoCamara")}
    >
      {c.decidida ? null : (
        <>
          <OrigemMargem
            corrida={c}
            limites={limitesMargem([
              c.margemFundamentos,
              c.margemP10,
              c.margemP90,
              ...(c.sondagens ? [c.sondagens.margem] : []),
            ])}
            titulo={t("corrida.origem.aria", {
              fundamentos: margem(c.margemFundamentos),
              sondagens: c.sondagens
                ? margem(c.sondagens.margem)
                : t("corrida.origem.semSondagens"),
              final: margem(c.margem),
              de: margem(c.margemP10),
              ate: margem(c.margemP90),
            })}
          />
          <dl className="grid grid-cols-[minmax(0,1fr)_auto] gap-x-4 gap-y-1 text-sm">
            <dt className="text-ink-2">{t("corrida.origem.fundamentos")}</dt>
            <dd className="text-right font-mono">{margem(c.margemFundamentos)}</dd>
            {c.sondagens ? (
              <>
                <dt className="text-ink-2">
                  {t("corrida.origem.sondagens")}
                  <span className="block font-mono text-[11px] text-ink-3">
                    {t(
                      c.sondagens.institutos === 1
                        ? "corrida.origem.sondagensDetalheUm"
                        : "corrida.origem.sondagensDetalhe",
                      {
                        n: c.sondagens.institutos,
                        peso: formatarPercentagem(c.sondagens.peso, 0),
                      },
                    )}
                  </span>
                </dt>
                <dd className="text-right font-mono">{margem(c.sondagens.margem)}</dd>
              </>
            ) : null}
            <dt className="font-semibold">{t("corrida.origem.final")}</dt>
            <dd className="text-right font-mono font-semibold">{margem(c.margem)}</dd>
            <dt className="text-ink-2">{t("corrida.origem.intervalo")}</dt>
            <dd className="text-right font-mono whitespace-nowrap">
              {margem(c.margemP10)} {t("previsao.tabela.a")} {margem(c.margemP90)}
            </dd>
          </dl>
        </>
      )}
    </Painel>
  );
}

function PainelEvolucao({
  pontos,
  vista,
}: {
  pontos: readonly PontoCorrida[];
  vista: VistaPrevisao;
}) {
  const primeiro = pontos[0];
  const ultimo = pontos.at(-1);
  const dias = pontos.length;
  return (
    <Painel
      sobrelinha={t("corrida.evolucao.sobrelinha")}
      titulo={t("corrida.evolucao.titulo")}
      descricao={
        dias > 1 && primeiro
          ? t("corrida.evolucao.texto", { de: formatarData(data(primeiro.corte)), n: dias })
          : t("previsao.evolucao.umDia")
      }
      acessorio={dias > 1 ? <Estimativa /> : <Selo>{t("comum.emPreparacao")}</Selo>}
      fontes={vista.fontes}
      metodo={t("previsao.evolucao.metodo")}
    >
      {primeiro && ultimo ? (
        <>
          <EvolucaoControlo
            pontos={evolucaoCorrida(pontos)}
            titulo={t("corrida.evolucao.aria", {
              de: formatarPercentagem(primeiro.probD, 0),
              ate: formatarPercentagem(ultimo.probD, 0),
            })}
          />
          {dias > 1 ? (
            <p className="font-mono text-[11px] text-ink-3">
              {t("corrida.evolucao.margem", {
                de: margem(primeiro.margem),
                ate: margem(ultimo.margem),
                data: formatarDataCurta(data(primeiro.corte)),
              })}
            </p>
          ) : null}
        </>
      ) : null}
    </Painel>
  );
}

function Seguir({
  c,
  comSondagens,
  comVotoAntecipado,
}: {
  c: CorridaVista;
  comSondagens: boolean;
  comVotoAntecipado: boolean;
}) {
  const fecho = fechoDoEstado(c.estado);
  return (
    <Painel titulo={t("corrida.seguir.titulo")}>
      <ul className="flex flex-col gap-2 text-sm">
        {fecho ? (
          <li className="text-ink-2">
            {fecho.todas
              ? t("corrida.seguir.fechoTodas", {
                  quando: formatarDataHora(new Date(fecho.primeiro), LISBOA),
                  todas: formatarHora(new Date(fecho.todas), LISBOA),
                })
              : t("corrida.seguir.fecho", {
                  quando: formatarDataHora(new Date(fecho.primeiro), LISBOA),
                })}
          </li>
        ) : null}
        {comSondagens ? (
          <li>
            <Link href={`/sondagens/${c.id.toLowerCase()}/`} className={LIGACAO}>
              {t("corrida.seguir.sondagens")}
            </Link>
          </li>
        ) : null}
        {comVotoAntecipado ? (
          <li>
            <Link href={caminhoEstado(c.estado)} prefetch={false} className={LIGACAO}>
              {t("corrida.seguir.votoAntecipado")}
            </Link>
          </li>
        ) : null}
        <li>
          <Link href="/resultados/" className={LIGACAO}>
            {t("corrida.seguir.resultados")}
          </Link>
        </li>
        <li>
          <Link href="/previsao/" className={LIGACAO}>
            {t("corrida.seguir.previsao")}
          </Link>
        </li>
      </ul>
    </Painel>
  );
}

export function PaginaCorrida({
  corrida: c,
  vista,
  evolucao,
  comSondagens,
  comVotoAntecipado,
  faseBuild,
  prognosticos = null,
}: {
  corrida: CorridaVista;
  vista: VistaPrevisao;
  evolucao: readonly PontoCorrida[];
  comSondagens: boolean;
  comVotoAntecipado: boolean;
  faseBuild: Fase;
  /** Classificações de outros prognosticadores para esta corrida; `null` sem elas. */
  prognosticos?: { vista: VistaPrognosticos; comparacao: ComparacaoCorrida } | null;
}) {
  return (
    <div className="flex flex-col gap-4">
      <header className="flex flex-wrap items-start justify-between gap-x-6 gap-y-3">
        <div className="flex min-w-0 flex-col gap-2">
          <p className="rotulo">
            {t("corrida.sobrelinha", {
              camara: t(`previsao.camaraNome.${c.camara}`),
              ano: vista.ano,
            })}
          </p>
          <h1 className="font-display text-[clamp(30px,5vw,40px)] leading-[1.02] font-bold">
            {tituloCorrida(c)}
          </h1>
          <p className="max-w-[62ch] text-ink-2">{t("corrida.lede")}</p>
          <ul aria-label={t("corrida.candidatos")} className="flex flex-col gap-1 text-[15px]">
            <Candidato lado="D" c={c} />
            <Candidato lado="R" c={c} />
          </ul>
        </div>
        <VersaoPrevisao vista={vista} />
      </header>
      <CorridaAoVivo
        id={c.id}
        faseBuild={faseBuild}
        previsao={{
          ano: vista.ano,
          congelada: vista.congelada,
          corte: vista.corte,
          corridasSenado: c.camara === "senado" ? [c] : [],
          corridasCamara: c.camara === "senado" ? [] : [c],
        }}
      />
      <Indicadores c={c} />
      <div className="grid gap-4 lg:grid-cols-2">
        <PainelOrigem c={c} vista={vista} />
        <PainelEvolucao pontos={evolucao} vista={vista} />
      </div>
      {prognosticos ? (
        <PainelPrognosticosCorrida
          vista={prognosticos.vista}
          comparacao={prognosticos.comparacao}
        />
      ) : null}
      <Seguir c={c} comSondagens={comSondagens} comVotoAntecipado={comVotoAntecipado} />
    </div>
  );
}
