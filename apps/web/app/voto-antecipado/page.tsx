import type { Metadata } from "next";
import { SeccaoEmPreparacao } from "@/components/layout/SeccaoEmPreparacao.tsx";
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
import { t } from "@/lib/mensagens.ts";
import { carregarVista } from "@/lib/voto-antecipado/carregar.ts";
import type { VistaVotoAntecipado } from "@/lib/voto-antecipado/vista.ts";

export const metadata: Metadata = { title: t("seccoes.votoAntecipado.titulo") };

const METODOLOGIA =
  "https://github.com/tpereira2005/intercalares-eua-2026/blob/main/docs/metodologia/voto-antecipado.md";

function nomeEstado(vista: VistaVotoAntecipado): string {
  return vista.estado === "NC" ? t("votoAntecipado.estados.NC") : vista.estado;
}

function Indicadores({ vista }: { vista: VistaVotoAntecipado }) {
  const principal = vista.comparacoes[0];
  if (!principal) return null;
  const idosos = principal.faixas.filter((f) => f.faixa === "65-74" || f.faixa === "75+");
  const quota65 = idosos.reduce((s, f) => s + f.quota, 0);
  const quota65Base = idosos.reduce((s, f) => s + f.quotaBase, 0);
  const jovens = principal.faixas.filter((f) => f.faixa === "18-24" || f.faixa === "25-29");
  const esperadoJovens = jovens.reduce((s, f) => s + f.esperado, 0);
  const desvioJovens =
    esperadoJovens > 0 ? jovens.reduce((s, f) => s + f.votos, 0) / esperadoJovens - 1 : null;
  const restantes = vista.reserva.partidos.reduce((s, p) => s + p.restantes, 0);
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
      <Kpi
        rotulo={t("votoAntecipado.kpis.quota65")}
        valor={formatarPercentagem(quota65)}
        detalhe={t("votoAntecipado.kpis.quota65Detalhe", {
          pontos: formatarPontos(quota65 - quota65Base),
          ano: principal.anoBase,
        })}
      />
      {desvioJovens === null ? null : (
        <Kpi
          rotulo={t("votoAntecipado.kpis.desvioJovens")}
          valor={formatarVariacao(desvioJovens)}
          detalhe={t("votoAntecipado.kpis.desvioJovensDetalhe", { ano: principal.anoBase })}
        />
      )}
      {vista.reserva.partidos.length > 0 && vista.anoReferenciaHistorico !== null ? (
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

export default function Pagina() {
  // Lido e validado no build; o site é reconstruído a cada atualização de dados.
  const vista = carregarVista();
  if (vista === null) {
    return (
      <SeccaoEmPreparacao
        titulo={t("seccoes.votoAntecipado.titulo")}
        descricao={t("seccoes.votoAntecipado.descricao")}
      />
    );
  }
  const estado = nomeEstado(vista);
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
          <QualidadeDados nivel="individual" comTexto />
          <span className="font-mono text-[11px] text-ink-3">
            {t("votoAntecipado.geradoEm", { data: formatarData(new Date(vista.geradoEm)) })}
          </span>
        </div>
      </header>

      <Indicadores vista={vista} />

      {vista.avisos.length > 0 ? (
        <aside
          aria-label={t("votoAntecipado.avisosTitulo")}
          className="rounded-md border border-dashed border-ink-3 bg-sheet px-[18px] py-3 text-sm"
        >
          <p className="rotulo mb-1.5">{t("votoAntecipado.avisosTitulo")}</p>
          <ul className="flex list-disc flex-col gap-1 pl-5 text-ink-2">
            {vista.avisos.map((aviso) => (
              <li key={aviso}>{aviso}</li>
            ))}
          </ul>
        </aside>
      ) : null}

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
