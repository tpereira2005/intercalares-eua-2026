import Link from "next/link";
import { QuemVotou } from "@/components/inicio/QuemVotou.tsx";
import { CodigoDia } from "@/components/ui/CodigoDia.tsx";
import { FaixaKpis, Kpi } from "@/components/ui/Kpi.tsx";
import { Painel } from "@/components/ui/Painel.tsx";
import { QualidadeDados } from "@/components/ui/QualidadeDados.tsx";
import { Selo } from "@/components/ui/Selo.tsx";
import { caminhoEstado } from "@/components/voto-antecipado/PaginaEstado.tsx";
import { nomeEstado } from "@/lib/estados.ts";
import {
  DIA_DA_ELEICAO,
  diasAteEleicao,
  formatarCompacto,
  formatarData,
  formatarNumero,
  formatarPercentagem,
  formatarPontos,
  formatarVariacao,
} from "@/lib/formatacao.ts";
import { t } from "@/lib/mensagens.ts";
import { carregarVistas } from "@/lib/voto-antecipado/carregar.ts";
import { resumirEstado, type ResumoEstado } from "@/lib/voto-antecipado/resumo.ts";
import type { VistaVotoAntecipado } from "@/lib/voto-antecipado/vista.ts";

const LIGACAO = "text-ink underline decoration-rule underline-offset-[3px] hover:decoration-ink-3";

/** Frase gerada a partir dos dados do estado principal; só com números que existem. */
function narrativa(resumo: ResumoEstado): string | null {
  const { anoBase, variacaoVotos, quota65, quota65Base } = resumo;
  const jovens = resumo.desvio.jovens;
  if (anoBase === null || variacaoVotos === null || quota65 === null || quota65Base === null) {
    return null;
  }
  if (jovens === null) return null;
  return t("inicio.narrativa", {
    estado: nomeEstado(resumo.estado),
    votos: formatarNumero(resumo.votos),
    variacao: formatarVariacao(variacaoVotos),
    ano: anoBase,
    quota65: formatarPercentagem(quota65),
    pontos: formatarPontos(quota65 - quota65Base),
    jovens: formatarVariacao(jovens),
  });
}

function Indicadores({
  vistas,
  resumos,
}: {
  vistas: readonly VistaVotoAntecipado[];
  resumos: readonly ResumoEstado[];
}) {
  const principal = resumos[0];
  if (!principal) return null;
  const anoBase = principal.anoBase;
  // Variação conjunta: soma dos votos de hoje sobre a soma dos votos no mesmo dia do ano base.
  const comBase = vistas.flatMap((v) => {
    const c = v.comparacoes.find((x) => x.anoBase === anoBase);
    return c ? [c] : [];
  });
  const votosBase = comBase.reduce((s, c) => s + c.votosBase, 0);
  const votos = comBase.reduce((s, c) => s + c.votos, 0);
  const variacao = votosBase > 0 ? votos / votosBase - 1 : null;
  const total = resumos.reduce((s, r) => s + r.votos, 0);
  return (
    <FaixaKpis>
      <Kpi
        rotulo={t("inicio.kpis.votos")}
        valor={formatarCompacto(total)}
        {...(variacao === null || anoBase === null
          ? {}
          : {
              detalhe:
                resumos.length > 1
                  ? t("inicio.kpis.votosDetalhe", {
                      n: resumos.length,
                      variacao: formatarVariacao(variacao),
                      ano: anoBase,
                    })
                  : t("inicio.kpis.votosDetalheUm", {
                      variacao: formatarVariacao(variacao),
                      ano: anoBase,
                    }),
            })}
      />
      {principal.quota65 === null || principal.quota65Base === null ? null : (
        <Kpi
          rotulo={`${t("votoAntecipado.kpis.quota65")} · ${principal.estado}`}
          valor={formatarPercentagem(principal.quota65)}
          detalhe={t("votoAntecipado.kpis.quota65Detalhe", {
            pontos: formatarPontos(principal.quota65 - principal.quota65Base),
            ano: anoBase ?? "",
          })}
        />
      )}
      {principal.desvio.jovens === null ? null : (
        <Kpi
          rotulo={`${t("votoAntecipado.kpis.desvioJovens")} · ${principal.estado}`}
          valor={formatarVariacao(principal.desvio.jovens)}
          detalhe={t("votoAntecipado.kpis.desvioJovensDetalhe", { ano: anoBase ?? "" })}
        />
      )}
      {principal.restantes === null ? null : (
        <Kpi
          rotulo={`${t("votoAntecipado.kpis.reserva")} · ${principal.estado}`}
          valor={formatarCompacto(principal.restantes)}
          detalhe={t("votoAntecipado.kpis.reservaDetalhe", {
            ano: vistas[0]?.anoReferenciaHistorico ?? anoBase ?? "",
            atual: vistas[0]?.ano ?? "",
          })}
        />
      )}
    </FaixaKpis>
  );
}

function EstadosAcompanhados({ resumos }: { resumos: readonly ResumoEstado[] }) {
  const anoBase = resumos[0]?.anoBase ?? 2022;
  return (
    <Painel
      sobrelinha={t("inicio.estados.sobrelinha")}
      titulo={t("inicio.estados.titulo")}
      descricao={t("inicio.estados.texto", { ano: anoBase })}
      metodo={t("votoAntecipado.metodo.desvio", { ano: anoBase })}
    >
      <ol className="flex flex-col">
        {resumos.map((r) => (
          <li
            key={r.estado}
            className="grid grid-cols-[minmax(0,1fr)_auto_auto] items-center gap-3 border-t border-rule-2 py-2.5 text-sm first:border-t-0"
          >
            <Link href={caminhoEstado(r.estado)} className={LIGACAO}>
              {nomeEstado(r.estado)}
            </Link>
            <QualidadeDados nivel={r.qualidade} />
            <span className="font-mono text-[13px] font-medium">
              {r.desvio.todos === null ? t("comum.semDados") : formatarVariacao(r.desvio.todos)}
            </span>
          </li>
        ))}
      </ol>
      <p className="text-sm">
        <Link href="/mapa/" className={LIGACAO}>
          {t("inicio.estados.ligacao")}
        </Link>
      </p>
    </Painel>
  );
}

function OQueVemAi() {
  return (
    <Painel titulo={t("inicio.proximosTitulo")} descricao={t("inicio.proximosDescricao")}>
      <ol className="flex flex-col">
        {(["votoAntecipado", "previsao", "noite"] as const).map((chave, indice) => (
          <li
            key={chave}
            className="grid grid-cols-[auto_minmax(0,1fr)] gap-3 border-t border-rule-2 py-2.5 text-sm first:border-t-0"
          >
            <span className="font-mono text-xs text-ink-3">
              {String(indice + 1).padStart(2, "0")}
            </span>
            <span>{t(`inicio.proximos.${chave}`)}</span>
          </li>
        ))}
      </ol>
    </Painel>
  );
}

export default function Inicio() {
  // Calculado no momento do build; o site é reconstruído a cada atualização de dados.
  const dias = diasAteEleicao(new Date());
  const vistas = carregarVistas();
  const resumos = vistas.map(resumirEstado);
  const principal = vistas[0];
  const resumoPrincipal = resumos[0];
  const frase = resumoPrincipal ? narrativa(resumoPrincipal) : null;

  return (
    <>
      <h1 className="sr-only">{t("inicio.titulo")}</h1>
      <div className="flex flex-col gap-4">
        <div className="grid gap-4 min-[860px]:grid-cols-[minmax(0,1.05fr)_minmax(0,1fr)]">
          <Painel
            sobrelinha={t("inicio.sobrelinha")}
            titulo={formatarData(DIA_DA_ELEICAO)}
            acessorio={<CodigoDia dias={dias} />}
            metodo={t("inicio.metodo")}
          >
            <div className="flex flex-wrap items-end gap-4">
              <span className="font-display text-[clamp(76px,11vw,128px)] leading-[0.82] font-black tracking-[-0.01em]">
                {dias}
              </span>
              <span className="pb-1.5 font-display text-[22px] leading-[1.05] font-bold tracking-[0.03em] uppercase">
                {dias > 0 ? t("inicio.diasParaEleicao") : t("inicio.diaDaEleicao")}
              </span>
            </div>
            <p className="max-w-[62ch] text-[16.5px] leading-relaxed">{t("inicio.emJogo")}</p>
            {frase && resumoPrincipal ? (
              <>
                <p className="max-w-[62ch] border-t border-rule-2 pt-3 text-[16.5px] leading-relaxed">
                  {frase}
                </p>
                <p className="flex flex-wrap justify-between gap-2 font-mono text-[11px] text-ink-3">
                  <span>
                    {t("inicio.geradoDados", {
                      data: formatarData(new Date(`${resumoPrincipal.dadosAte}T12:00:00Z`)),
                    })}
                  </span>
                  <Link href={caminhoEstado(resumoPrincipal.estado)} className={LIGACAO}>
                    {t("inicio.verRastreador")}
                  </Link>
                </p>
              </>
            ) : null}
          </Painel>
          <Painel
            sobrelinha={t("inicio.previsao.sobrelinha")}
            titulo={t("inicio.previsao.titulo")}
            acessorio={<Selo variante="tracejado">{t("comum.emPreparacao")}</Selo>}
          >
            <p className="max-w-[62ch] text-ink-2">{t("inicio.previsao.texto")}</p>
            <p className="text-sm">
              <Link href="/previsao/" className={LIGACAO}>
                {t("inicio.previsao.ligacao")}
              </Link>
            </p>
          </Painel>
        </div>

        <Indicadores vistas={vistas} resumos={resumos} />

        <div className="grid gap-4 min-[860px]:grid-cols-2">
          {principal ? (
            <Painel
              sobrelinha={t("inicio.quemVotou.sobrelinha", {
                estado: nomeEstado(principal.estado),
              })}
              titulo={t("inicio.quemVotou.titulo")}
              fontes={principal.fontes.slice(0, 1)}
              metodo={t("votoAntecipado.metodo.composicao")}
            >
              <QuemVotou vista={principal} />
              <p className="text-sm">
                <Link href={caminhoEstado(principal.estado)} className={LIGACAO}>
                  {t("inicio.quemVotou.ligacao")}
                </Link>
              </p>
            </Painel>
          ) : null}
          {resumos.length > 0 ? <EstadosAcompanhados resumos={resumos} /> : <OQueVemAi />}
        </div>
      </div>
    </>
  );
}
