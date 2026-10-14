import Link from "next/link";
import { FaixaKpis, Kpi } from "@/components/ui/Kpi.tsx";
import { QualidadeDados } from "@/components/ui/QualidadeDados.tsx";
import { Rastreador } from "@/components/voto-antecipado/Rastreador.tsx";
import {
  formatarCompacto,
  formatarData,
  formatarPercentagem,
  formatarPontos,
  formatarVariacao,
} from "@/lib/formatacao.ts";
import { nomeEstado } from "@/lib/estados.ts";
import { t } from "@/lib/mensagens.ts";
import { resumirEstado } from "@/lib/voto-antecipado/resumo.ts";
import type { VistaVotoAntecipado } from "@/lib/voto-antecipado/vista.ts";

const METODOLOGIA = "/metodologia/voto-antecipado/";

/** Endereço da página de um estado (ex.: /voto-antecipado/nc/). */
export function caminhoEstado(codigo: string): string {
  return `/voto-antecipado/${codigo.toLowerCase()}/`;
}

function Indicadores({ vista }: { vista: VistaVotoAntecipado }) {
  const principal = vista.comparacoes[0];
  if (!principal) return null;
  const resumo = resumirEstado(vista);
  const { quota65, quota65Base, restantes } = resumo;
  const desvioJovens = resumo.desvio.jovens;
  return (
    <FaixaKpis>
      <Kpi
        rotulo={t("votoAntecipado.kpis.votos")}
        valor={formatarCompacto(vista.votos)}
        {...(principal.variacaoVotos === null
          ? {}
          : {
              detalhe: t("votoAntecipado.kpis.votosDetalhe", {
                variacao: formatarVariacao(principal.variacaoVotos),
                ano: principal.anoBase,
              }),
            })}
      />
      {quota65 === null || quota65Base === null ? null : (
        <Kpi
          rotulo={t("votoAntecipado.kpis.quota65")}
          valor={formatarPercentagem(quota65)}
          detalhe={t("votoAntecipado.kpis.quota65Detalhe", {
            pontos: formatarPontos(quota65 - quota65Base),
            ano: principal.anoBase,
          })}
        />
      )}
      {desvioJovens === null ? null : (
        <Kpi
          rotulo={t("votoAntecipado.kpis.desvioJovens")}
          valor={formatarVariacao(desvioJovens)}
          detalhe={t("votoAntecipado.kpis.desvioJovensDetalhe", { ano: principal.anoBase })}
        />
      )}
      {restantes !== null && vista.anoReferenciaHistorico !== null ? (
        <Kpi
          rotulo={t("votoAntecipado.kpis.reserva")}
          valor={formatarCompacto(restantes)}
          detalhe={t("votoAntecipado.kpis.reservaDetalhe", {
            ano: vista.anoReferenciaHistorico,
            atual: vista.ano,
          })}
        />
      ) : null}
    </FaixaKpis>
  );
}

/** Escolha do estado, quando há mais de um com dados. */
export function EscolhaEstado({
  atual,
  estados,
}: {
  atual: VistaVotoAntecipado["estado"];
  estados: readonly VistaVotoAntecipado["estado"][];
}) {
  if (estados.length < 2) return null;
  return (
    <nav aria-label={t("votoAntecipado.escolhaEstadoAria")} className="flex flex-wrap gap-1.5">
      {estados.map((codigo) => (
        <Link
          key={codigo}
          href={caminhoEstado(codigo)}
          aria-current={codigo === atual ? "page" : undefined}
          className={`rounded-[2px] border px-2 py-1 text-[13px] leading-none ${
            codigo === atual
              ? "border-signal bg-signal-wash text-signal-ink"
              : "border-rule text-ink-2 hover:text-ink"
          }`}
        >
          {nomeEstado(codigo)}
        </Link>
      ))}
    </nav>
  );
}

/** Limitações conhecidas desta atualização, como o pipeline as escreve. */
export function Avisos({ avisos }: { avisos: readonly string[] }) {
  if (avisos.length === 0) return null;
  return (
    <aside
      aria-label={t("votoAntecipado.avisosTitulo")}
      className="rounded-md border border-dashed border-ink-3 bg-sheet px-[18px] py-3 text-sm"
    >
      <p className="rotulo mb-1.5">{t("votoAntecipado.avisosTitulo")}</p>
      <ul className="flex list-disc flex-col gap-1 pl-5 text-ink-2">
        {avisos.map((aviso) => (
          <li key={aviso}>{aviso}</li>
        ))}
      </ul>
    </aside>
  );
}

const ITENS_LEITURA = [
  "composicao",
  "partido",
  "antecipacao",
  "mesmoDia",
  "regras",
  "presidenciais",
] as const;

/** O que os números dizem e o que não dizem, antes dos gráficos. */
export function ComoLer() {
  return (
    <section className="rounded-md border border-rule bg-sheet px-[18px] py-3.5 text-sm">
      <h2 className="rotulo mb-2">{t("votoAntecipado.leitura.titulo")}</h2>
      <ul className="grid list-disc gap-x-8 gap-y-1.5 pl-5 text-ink-2 md:grid-cols-2">
        {ITENS_LEITURA.map((item) => (
          <li key={item}>{t(`votoAntecipado.leitura.itens.${item}`)}</li>
        ))}
      </ul>
    </section>
  );
}

/** Página completa do rastreador de um estado. */
export function PaginaEstado({
  vista,
  estados,
}: {
  vista: VistaVotoAntecipado;
  estados: readonly VistaVotoAntecipado["estado"][];
}) {
  const qualidade = resumirEstado(vista).qualidade;
  const estado = nomeEstado(vista.estado);
  const fontes = vista.fontes
    .filter((f, i, todas) => todas.findIndex((g) => g.nome === f.nome) === i)
    .map((f) => ({ nome: f.nome, url: f.url }));
  const notas = vista.ciclos.filter((c) => c.notas.length > 0);

  return (
    <div className="flex flex-col gap-4">
      <header className="flex flex-wrap items-start justify-between gap-x-6 gap-y-3">
        <div className="min-w-0">
          <p className="rotulo mb-1">{t("votoAntecipado.sobrelinha", { estado })}</p>
          <h1 className="font-display text-[clamp(30px,5vw,40px)] leading-[1.02] font-bold">
            {t("votoAntecipado.titulo", { estado })}
          </h1>
          <p className="mt-1.5 max-w-[68ch] text-[15.5px] text-ink-2">{t("votoAntecipado.lede")}</p>
        </div>
        <div className="flex flex-col items-start gap-1.5 sm:items-end">
          <QualidadeDados nivel={qualidade} comTexto />
          <span className="font-mono text-[11px] text-ink-3">
            {t("votoAntecipado.geradoEm", { data: formatarData(new Date(vista.geradoEm)) })}
          </span>
        </div>
      </header>

      <EscolhaEstado atual={vista.estado} estados={estados} />

      <Indicadores vista={vista} />

      <Avisos avisos={vista.avisos} />

      <ComoLer />

      <Rastreador
        vista={vista}
        fontes={fontes}
        rodape={
          <section className="self-start rounded-md border border-rule bg-sheet px-[18px] py-3.5 text-sm">
            <h2 className="rotulo mb-2">{t("votoAntecipado.notasCiclos")}</h2>
            {notas.length > 0 ? (
              <dl className="grid gap-x-4 gap-y-1.5 sm:grid-cols-[auto_minmax(0,1fr)]">
                {notas.map((ciclo) => (
                  <div key={ciclo.ano} className="contents">
                    <dt className="font-mono text-ink">{ciclo.ano}</dt>
                    <dd className="text-ink-2">{ciclo.notas.join(" ")}</dd>
                  </div>
                ))}
              </dl>
            ) : null}
            <p className="mt-3">
              <a
                href={METODOLOGIA}
                rel="noopener noreferrer"
                className="text-ink underline decoration-rule underline-offset-[3px]"
              >
                {t("votoAntecipado.documentacao")}
              </a>
            </p>
          </section>
        }
      />
    </div>
  );
}
