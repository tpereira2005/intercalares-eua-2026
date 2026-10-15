import Link from "next/link";
import { FaixaKpis, Kpi } from "@/components/ui/Kpi.tsx";
import { Painel } from "@/components/ui/Painel.tsx";
import { Selo } from "@/components/ui/Selo.tsx";
import {
  formatarData,
  formatarDataCurta,
  formatarMargemPontos as margem,
  formatarNumero,
  formatarPercentagem,
} from "@/lib/formatacao.ts";
import { t } from "@/lib/mensagens.ts";
import type { DadosPrevisao } from "@/lib/previsao/carregar.ts";
import {
  CATEGORIAS,
  categoria,
  type Camara,
  type Categoria,
  type CorridaVista,
  type ResumoVista,
  type VistaEvolucao,
  type VistaPrevisao,
} from "@/lib/previsao/vista.ts";
import { DistribuicaoLugares, EvolucaoControlo, LinhaLimiares, MapaSenado } from "./graficos.tsx";
import { PainelAlteracoes } from "./PainelAlteracoes.tsx";
import { TabelaCorridas } from "./TabelaCorridas.tsx";

const METODOLOGIA = "/metodologia/previsao/";
const REPOSITORIO = "https://github.com/tpereira2005/intercalares-eua-2026";
const LIGACAO = "text-ink underline decoration-rule underline-offset-[3px]";
/** Distritos da Câmara mostrados antes de "ver os outros". */
const DISTRITOS_VISIVEIS = 25;

export function data(dia: string): Date {
  return new Date(`${dia}T12:00:00Z`);
}

export function Estimativa() {
  return <Selo variante="tracejado">{t("comum.selos.estimativa")}</Selo>;
}

function Indicadores({ vista }: { vista: VistaPrevisao }) {
  const kpi = (camara: Camara) => {
    const r = vista[camara];
    const lider = r.probD >= r.probR ? "D" : "R";
    const outro = lider === "D" ? "R" : "D";
    return (
      <Kpi
        rotulo={t(`previsao.kpis.${camara}`)}
        valor={`${lider} ${formatarPercentagem(lider === "D" ? r.probD : r.probR, 0)}`}
        detalhe={t("previsao.kpis.detalhe", {
          outro,
          prob: formatarPercentagem(outro === "D" ? r.probD : r.probR, 0),
          lugares: r.mediana,
        })}
      />
    );
  };
  return (
    <FaixaKpis>
      {kpi("camara")}
      {kpi("senado")}
      <Kpi
        rotulo={t("previsao.kpis.ambiente")}
        valor={margem(vista.ambiente.margem)}
        detalhe={t("previsao.kpis.ambienteDetalhe", {
          de: margem(vista.ambiente.p10),
          ate: margem(vista.ambiente.p90),
        })}
      />
    </FaixaKpis>
  );
}

/** Barra da probabilidade de controlo: azul para o lado democrata, tracejado para o republicano. */
export function BarraControlo({ resumo }: { resumo: ResumoVista }) {
  return (
    <div className="flex flex-col gap-1.5">
      <div className="flex justify-between gap-3 text-[13px]">
        <span>
          <span className="text-ink-2">{t("previsao.partidos.D")}</span>{" "}
          <strong className="font-semibold">{formatarPercentagem(resumo.probD)}</strong>
        </span>
        <span className="text-right">
          <span className="text-ink-2">{t("previsao.partidos.R")}</span>{" "}
          <strong className="font-semibold">{formatarPercentagem(resumo.probR)}</strong>
        </span>
      </div>
      <div aria-hidden="true" className="relative flex h-3 overflow-hidden rounded-[2px] bg-rule-2">
        <span className="fundo-dem h-full" style={{ width: `${String(resumo.probD * 100)}%` }} />
        <span className="flex-1" />
        <span className="fundo-rep h-full" style={{ width: `${String(resumo.probR * 100)}%` }} />
        <span className="absolute inset-y-0 left-1/2 w-px bg-sheet" />
      </div>
    </div>
  );
}

export function PainelLugares({
  vista,
  camara,
  comLigacao = false,
}: {
  vista: VistaPrevisao;
  camara: Camara;
  /** Ligação para a página só desta câmara (na página das duas). */
  comLigacao?: boolean;
}) {
  const r = vista[camara];
  return (
    <Painel
      sobrelinha={t(`previsao.lugares.sobrelinha.${camara}`)}
      titulo={t(`previsao.lugares.titulo.${camara}`)}
      descricao={t(`previsao.lugares.texto.${camara}`, {
        maioria: r.maioria,
        foraD: r.foraDeJogo.D,
        foraR: r.foraDeJogo.R,
      })}
      acessorio={<Estimativa />}
      fontes={vista.fontes}
      metodo={t("previsao.lugares.metodo", { simulacoes: formatarNumero(vista.simulacoes) })}
    >
      <p className="rotulo">{t("previsao.lugares.controlo")}</p>
      <BarraControlo resumo={r} />
      <DistribuicaoLugares resumo={r} />
      <div className="flex flex-wrap gap-x-4 gap-y-1 text-[12.5px] text-ink-2">
        <span className="inline-flex items-center gap-1.5">
          <span aria-hidden="true" className="fundo-dem inline-block size-3 rounded-[2px]" />
          {t("previsao.lugares.legendaD")}
        </span>
        <span className="inline-flex items-center gap-1.5">
          <span aria-hidden="true" className="fundo-rep inline-block size-3 rounded-[2px]" />
          {t("previsao.lugares.legendaR")}
        </span>
        <span className="inline-flex items-center gap-1.5">
          <span aria-hidden="true" className="inline-block size-3 rounded-[2px] bg-rule-2" />
          {t("previsao.lugares.intervalo")}
        </span>
      </div>
      <p className="text-sm text-ink-2">
        {t("previsao.lugares.resumo", {
          mediana: r.mediana,
          de: r.p10,
          ate: r.p90,
          medianaR: r.total - r.mediana,
          deR: r.total - r.p90,
          ateR: r.total - r.p10,
        })}
        {r.independentes >= 0.05
          ? ` ${t("previsao.lugares.independentes", {
              valor: r.independentes.toLocaleString("pt-PT", { maximumFractionDigits: 1 }),
            })}`
          : null}
      </p>
      {comLigacao ? (
        <p className="text-sm">
          <Link href={`/previsao/${camara}/`} className={LIGACAO}>
            {t(`previsao.paginas.${camara}.ligacao`)}
          </Link>
        </p>
      ) : null}
    </Painel>
  );
}

function PainelLimiares({ vista, comCenarios }: { vista: VistaPrevisao; comCenarios: boolean }) {
  const { ambiente } = vista;
  return (
    <Painel
      sobrelinha={t("previsao.limiares.sobrelinha")}
      titulo={t("previsao.limiares.titulo")}
      descricao={t("previsao.limiares.texto")}
      acessorio={<Estimativa />}
      fontes={vista.fontes}
      metodo={t("previsao.limiares.metodo", {
        fonte: t(`previsao.limiares.fonteAmbiente.${ambiente.fonte}`),
        desvio: ambiente.desvio.toLocaleString("pt-PT", { maximumFractionDigits: 1 }),
      })}
    >
      <LinhaLimiares
        ambiente={ambiente}
        limiares={(["camara", "senado"] as const).map((c) => ({
          camara: c,
          valor: vista[c].limiar,
        }))}
      />
      <div className="flex flex-wrap gap-x-4 gap-y-1 text-[12.5px] text-ink-2">
        <span className="inline-flex items-center gap-1.5">
          <span aria-hidden="true" className="inline-block size-3 rounded-full bg-ink" />
          {t("previsao.limiares.previsto")}
        </span>
        <span className="inline-flex items-center gap-1.5">
          <span aria-hidden="true" className="inline-block size-3 rounded-[2px] bg-rule-2" />
          {t("previsao.limiares.intervalo")}
        </span>
        {ambiente.agregadores.length > 0 ? (
          <span className="inline-flex items-center gap-1.5">
            <span
              aria-hidden="true"
              className="inline-block size-2.5 rounded-full border border-ink-2 bg-sheet"
            />
            {t("previsao.limiares.agregador")}
          </span>
        ) : null}
      </div>
      <ul className="flex flex-col gap-1 text-sm text-ink-2">
        {(["camara", "senado"] as const).map((c) => {
          const limiar = vista[c].limiar;
          const nome = t(`previsao.camaraNome.${c}`);
          return (
            <li key={c}>
              {limiar === null
                ? t("previsao.limiares.semLimiar", { camara: t(`previsao.camaraA.${c}`) })
                : t("previsao.limiares.leitura", {
                    camara: nome,
                    limiar: margem(limiar),
                    ambiente: margem(ambiente.margem),
                  })}
            </li>
          );
        })}
      </ul>
      {ambiente.agregadores.length > 0 ? (
        <div>
          <p className="rotulo mb-1.5">{t("previsao.limiares.agregadores")}</p>
          <dl className="grid grid-cols-[minmax(0,1fr)_auto] gap-x-4 gap-y-1 text-sm sm:grid-cols-[minmax(0,1fr)_auto_minmax(0,1fr)_auto]">
            {ambiente.agregadores.map((a) => (
              <div key={a.nome} className="contents">
                <dt className="text-ink-2">{a.nome}</dt>
                <dd className="text-right font-mono">{margem(a.margem)}</dd>
              </div>
            ))}
          </dl>
        </div>
      ) : null}
      {comCenarios ? (
        <p className="text-sm">
          <Link href="/previsao/cenarios/" className={LIGACAO}>
            {t("previsao.cenarios.ligacao")}
          </Link>
        </p>
      ) : null}
    </Painel>
  );
}

function PainelEvolucao({
  vista,
  evolucao,
}: {
  vista: VistaPrevisao;
  evolucao: VistaEvolucao | null;
}) {
  const dias = evolucao?.cortes.length ?? 0;
  return (
    <Painel
      sobrelinha={t("previsao.evolucao.sobrelinha")}
      titulo={t("previsao.evolucao.titulo")}
      descricao={
        dias > 1
          ? t("previsao.evolucao.texto", {
              de: formatarData(data(evolucao?.cortes[0] ?? vista.corte)),
              n: dias,
            })
          : t("previsao.evolucao.umDia")
      }
      acessorio={dias > 1 ? <Estimativa /> : <Selo>{t("comum.emPreparacao")}</Selo>}
      fontes={vista.fontes}
      metodo={t("previsao.evolucao.metodo")}
    >
      {evolucao && dias > 0 ? (
        <div className="grid gap-4 sm:grid-cols-2">
          {(["camara", "senado"] as const).map((c) => {
            const pontos = evolucao[c];
            const primeiro = pontos[0];
            const ultimo = pontos.at(-1);
            return (
              <figure key={c} className="flex min-w-0 flex-col gap-1.5">
                <figcaption className="rotulo">{t(`previsao.camaraNome.${c}`)}</figcaption>
                <EvolucaoControlo
                  pontos={pontos}
                  titulo={t("previsao.evolucao.aria", {
                    camara: t(`previsao.camaraNa.${c}`),
                    de: formatarPercentagem(primeiro?.probD ?? 0, 0),
                    ate: formatarPercentagem(ultimo?.probD ?? 0, 0),
                  })}
                />
                {primeiro && ultimo && dias > 1 ? (
                  <p className="font-mono text-[11px] text-ink-3">
                    {t("previsao.evolucao.lugares", {
                      de: primeiro.mediana,
                      ate: ultimo.mediana,
                      data: formatarDataCurta(data(primeiro.corte)),
                    })}
                  </p>
                ) : null}
              </figure>
            );
          })}
        </div>
      ) : null}
    </Painel>
  );
}

/** Variação da probabilidade democrata de cada corrida face à semana anterior. */
export function variacoes(
  corridas: readonly CorridaVista[],
  evolucao: VistaEvolucao | null,
): Record<string, number> {
  const antes = evolucao?.semanaAnterior?.probD;
  if (!antes) return {};
  return Object.fromEntries(
    corridas.flatMap((c) => {
      const p = antes.get(c.id);
      return p === undefined ? [] : [[c.id, c.probD - p]];
    }),
  );
}

export function NotaSemana({ evolucao }: { evolucao: VistaEvolucao | null }) {
  const semana = evolucao?.semanaAnterior;
  if (!semana) return null;
  return (
    <p className="font-mono text-[11px] text-ink-3">
      {t("previsao.tabela.notaVariacao", { data: formatarDataCurta(data(semana.corte)) })}
    </p>
  );
}

export function PainelSenado({
  vista,
  evolucao,
}: {
  vista: VistaPrevisao;
  evolucao: VistaEvolucao | null;
}) {
  const corridas = vista.corridasSenado;
  return (
    <Painel
      sobrelinha={t("previsao.senado.sobrelinha")}
      titulo={t("previsao.senado.titulo", { n: corridas.length })}
      descricao={t("previsao.senado.texto")}
      acessorio={<Estimativa />}
      fontes={vista.fontes}
      metodo={t("previsao.senado.metodo")}
    >
      <div className="mx-auto w-full max-w-[720px]">
        <MapaSenado corridas={corridas} />
      </div>
      <div className="flex flex-wrap gap-x-4 gap-y-1 text-[12.5px] text-ink-2">
        <span className="inline-flex items-center gap-1.5">
          <span
            aria-hidden="true"
            className="inline-block h-2.5 w-20 rounded-[1px] bg-[linear-gradient(90deg,color-mix(in_oklab,var(--dem)_12%,var(--sheet)),var(--dem))]"
          />
          {t("previsao.senado.legendaD")}
        </span>
        <span className="inline-flex items-center gap-1.5">
          <span aria-hidden="true" className="fundo-rep inline-block h-2.5 w-20 rounded-[1px]" />
          {t("previsao.senado.legendaR")}
        </span>
        <span className="inline-flex items-center gap-1.5">
          <span
            aria-hidden="true"
            className="inline-block size-3 rounded-[2px] border border-rule bg-sheet"
          />
          {t("previsao.senado.semEleicao")}
        </span>
      </div>
      <TabelaCorridas
        corridas={corridas}
        legenda={t("previsao.senado.legendaTabela")}
        comSondagens
        variacoes={variacoes(corridas, evolucao)}
      />
      <NotaSemana evolucao={evolucao} />
      <p className="text-sm">
        <Link href="/sondagens/" className={LIGACAO}>
          {t("previsao.senado.sondagens")}
        </Link>
      </p>
    </Painel>
  );
}

export const ESTILO_CATEGORIA: Record<
  Categoria,
  { className: string; style?: { opacity?: number; background?: string } }
> = {
  solidaD: { className: "fundo-dem" },
  provavelD: {
    className: "",
    style: { background: "color-mix(in oklab, var(--dem) 65%, var(--sheet))" },
  },
  inclinadaD: {
    className: "",
    style: { background: "color-mix(in oklab, var(--dem) 35%, var(--sheet))" },
  },
  renhida: { className: "bg-rule" },
  inclinadaR: { className: "fundo-rep", style: { opacity: 0.35 } },
  provavelR: { className: "fundo-rep", style: { opacity: 0.65 } },
  solidaR: { className: "fundo-rep" },
};

function BarraCategorias({
  contagem,
  total,
}: {
  contagem: Record<Categoria, number>;
  total: number;
}) {
  const lista = CATEGORIAS.map(
    (c) => `${t(`previsao.categorias.${c}`)} ${String(contagem[c])}`,
  ).join(", ");
  return (
    <div className="flex flex-col gap-2">
      <div
        role="img"
        aria-label={t("previsao.camara.categoriasAria", { lista })}
        className="flex h-6 gap-px overflow-hidden rounded-[2px] bg-sheet"
      >
        {CATEGORIAS.filter((c) => contagem[c] > 0).map((c) => (
          <span
            key={c}
            className={`h-full ${ESTILO_CATEGORIA[c].className}`}
            style={{
              ...ESTILO_CATEGORIA[c].style,
              width: `${String((contagem[c] / total) * 100)}%`,
            }}
          />
        ))}
      </div>
      <dl className="grid grid-cols-[repeat(auto-fill,minmax(118px,1fr))] gap-x-3 gap-y-1 text-[12.5px]">
        {CATEGORIAS.map((c) => (
          <div key={c} className="flex items-center gap-1.5">
            <dt className="flex items-center gap-1.5 text-ink-2">
              <span
                aria-hidden="true"
                className={`inline-block size-3 shrink-0 rounded-[2px] ${ESTILO_CATEGORIA[c].className}`}
                style={ESTILO_CATEGORIA[c].style}
              />
              {t(`previsao.categorias.${c}`)}
            </dt>
            <dd className="ml-auto font-mono font-semibold">{contagem[c]}</dd>
          </div>
        ))}
      </dl>
    </div>
  );
}

export function PainelCamara({
  vista,
  evolucao,
  todos = false,
}: {
  vista: VistaPrevisao;
  evolucao: VistaEvolucao | null;
  /** Mostra os 435 distritos na tabela, e não só os competitivos. */
  todos?: boolean;
}) {
  const competitivos = todos
    ? vista.corridasCamara
    : vista.corridasCamara.filter((c) => {
        const cat = categoria(c.probD);
        return cat !== "solidaD" && cat !== "solidaR";
      });
  const legenda = todos
    ? t("previsao.camara.todos", { n: competitivos.length })
    : t("previsao.camara.competitivos", { n: competitivos.length });
  return (
    <Painel
      sobrelinha={t("previsao.camara.sobrelinha")}
      titulo={t("previsao.camara.titulo", { n: vista.corridasCamara.length })}
      descricao={t(todos ? "previsao.camara.textoTodos" : "previsao.camara.texto")}
      acessorio={<Estimativa />}
      fontes={vista.fontes}
      metodo={t("previsao.camara.metodo")}
    >
      <BarraCategorias contagem={vista.categorias.camara} total={vista.corridasCamara.length} />
      <p className="font-mono text-[11px] text-ink-3">{t("previsao.camara.categoriasNota")}</p>
      <h3 className="rotulo mt-1">{legenda}</h3>
      <TabelaCorridas
        corridas={competitivos}
        legenda={legenda}
        comSondagens={false}
        variacoes={variacoes(competitivos, evolucao)}
        visiveis={DISTRITOS_VISIVEIS}
      />
      <NotaSemana evolucao={evolucao} />
      {todos ? null : (
        <p className="text-sm">
          <Link href="/previsao/camara/" className={LIGACAO}>
            {t("previsao.camara.verTodos")}
          </Link>
        </p>
      )}
    </Painel>
  );
}

function PainelBacktests({ vista }: { vista: VistaPrevisao }) {
  if (vista.backtests.length === 0) return null;
  return (
    <Painel
      sobrelinha={t("previsao.backtests.sobrelinha")}
      titulo={t("previsao.backtests.titulo")}
      descricao={t("previsao.backtests.texto")}
      metodo={t("previsao.backtests.metodo")}
    >
      <table className="w-full border-collapse text-sm">
        <caption className="sr-only">{t("previsao.backtests.titulo")}</caption>
        <thead>
          <tr className="rotulo text-left">
            <th scope="col" className="pb-1.5 pr-3 font-medium">
              {t("previsao.backtests.ano")}
            </th>
            <th scope="col" className="hidden pb-1.5 pr-3 font-medium md:table-cell">
              {t("previsao.backtests.ambiente")}
            </th>
            <th scope="col" className="pb-1.5 pr-3 text-right font-medium">
              {t("previsao.backtests.controlo")}
            </th>
            <th scope="col" className="pb-1.5 pr-3 text-right font-medium">
              {t("previsao.backtests.lugares")}
            </th>
            <th scope="col" className="hidden pb-1.5 pr-3 text-right font-medium sm:table-cell">
              {t("previsao.backtests.erradas")}
            </th>
            <th scope="col" className="hidden pb-1.5 pr-3 text-right font-medium lg:table-cell">
              {t("previsao.backtests.brier")}
            </th>
            <th scope="col" className="hidden pb-1.5 text-right font-medium lg:table-cell">
              {t("previsao.backtests.cobertura")}
            </th>
          </tr>
        </thead>
        <tbody className="font-mono text-[13px]">
          {vista.backtests.map((b) => {
            const probVencedor = b.controlo_real === "D" ? b.prob_controlo_d : b.prob_controlo_r;
            return (
              <tr key={`${String(b.ano)}-${b.camara}`} className="border-t border-rule-2">
                <th scope="row" className="py-1.5 pr-3 text-left font-sans font-semibold">
                  {b.ano} · {t(`previsao.camaraNome.${b.camara}`)}
                </th>
                <td className="hidden py-1.5 pr-3 md:table-cell">
                  {margem(b.ambiente_previsto)} / {margem(b.ambiente_real)}
                </td>
                <td className="py-1.5 pr-3 text-right">
                  {b.controlo_real} {formatarPercentagem(probVencedor, 0)}
                </td>
                <td className="py-1.5 pr-3 text-right">
                  {t("previsao.backtests.lugaresValor", {
                    mediana: b.lugares_d_mediana,
                    de: b.lugares_d_p10,
                    ate: b.lugares_d_p90,
                    reais: b.lugares_d_reais,
                  })}
                </td>
                <td className="hidden py-1.5 pr-3 text-right sm:table-cell">
                  {t("previsao.backtests.errados", {
                    n: b.corridas_erradas.length,
                    total: b.corridas_avaliadas,
                  })}
                </td>
                <td className="hidden py-1.5 pr-3 text-right lg:table-cell">
                  {b.brier.toLocaleString("pt-PT", {
                    minimumFractionDigits: 3,
                    maximumFractionDigits: 3,
                  })}
                </td>
                <td className="hidden py-1.5 text-right lg:table-cell">
                  {formatarPercentagem(b.cobertura_80, 0)}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </Painel>
  );
}

/** Versão da previsão: diária ou congelada, com a data dos dados. */
export function VersaoPrevisao({ vista }: { vista: VistaPrevisao }) {
  return (
    <div className="flex flex-col items-start gap-1.5 sm:items-end">
      {vista.congelada ? (
        <Selo variante="solido">{t("previsao.selos.congelada")}</Selo>
      ) : (
        <Selo variante="sinal">{t("previsao.selos.diaria")}</Selo>
      )}
      <span className="font-mono text-[11px] text-ink-3">
        {t("previsao.corte", { data: formatarData(data(vista.corte)) })}
      </span>
      {vista.commit === null ? null : (
        <a
          href={`${REPOSITORIO}/commit/${vista.commit}`}
          rel="noopener noreferrer"
          title={t("previsao.commitTitulo")}
          className={`font-mono text-[11px] ${LIGACAO}`}
        >
          {t("previsao.commit", { commit: vista.commit.slice(0, 7) })}
        </a>
      )}
      {vista.congelada ? null : (
        <span className="font-mono text-[11px] text-ink-3">{t("previsao.congela")}</span>
      )}
      <a href="/previsao/#alteracoes" className={`font-mono text-[11px] ${LIGACAO}`}>
        {t("previsao.alteracoes.ligacao")}
      </a>
    </div>
  );
}

/** Página da previsão da Câmara e do Senado. */
export function PaginaPrevisao({ dados }: { dados: DadosPrevisao }) {
  const { previsao: vista, evolucao } = dados;
  return (
    <div className="flex flex-col gap-4">
      <header className="flex flex-wrap items-start justify-between gap-x-6 gap-y-3">
        <div className="min-w-0">
          <p className="rotulo mb-1">{t("previsao.sobrelinha", { ano: vista.ano })}</p>
          <h1 className="font-display text-[clamp(30px,5vw,40px)] leading-[1.02] font-bold">
            {t("seccoes.previsao.titulo")}
          </h1>
          <p className="mt-1.5 max-w-[68ch] text-[15.5px] text-ink-2">
            {t("previsao.lede", { simulacoes: formatarNumero(vista.simulacoes) })}
          </p>
        </div>
        <VersaoPrevisao vista={vista} />
      </header>

      <Indicadores vista={vista} />

      <div className="grid gap-4 min-[860px]:grid-cols-2">
        <PainelLugares vista={vista} camara="camara" comLigacao />
        <PainelLugares vista={vista} camara="senado" comLigacao />
        <PainelLimiares vista={vista} comCenarios={dados.cenarios !== null} />
        <PainelEvolucao vista={vista} evolucao={evolucao} />
      </div>

      <PainelSenado vista={vista} evolucao={evolucao} />
      <PainelCamara vista={vista} evolucao={evolucao} />
      <PainelBacktests vista={vista} />
      {dados.alteracoes ? (
        <div id="alteracoes" className="scroll-mt-4">
          <PainelAlteracoes alteracoes={dados.alteracoes} />
        </div>
      ) : null}

      <section className="rounded-md border border-rule bg-sheet px-[18px] py-3.5 text-sm">
        <h2 className="rotulo mb-2">{t("previsao.notas")}</h2>
        <ul className="flex list-disc flex-col gap-1 pl-5 text-ink-2">
          {vista.notas.map((nota) => (
            <li key={nota}>{nota}</li>
          ))}
        </ul>
        <p className="mt-3">
          <a href={METODOLOGIA} rel="noopener noreferrer" className={LIGACAO}>
            {t("previsao.documentacao")}
          </a>
        </p>
      </section>
    </div>
  );
}
