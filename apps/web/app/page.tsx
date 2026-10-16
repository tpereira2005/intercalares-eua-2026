import type { Metadata } from "next";
import Link from "next/link";
import { FaseInicio } from "@/components/inicio/FaseInicio.tsx";
import { InicioAoVivo } from "@/components/inicio/InicioAoVivo.tsx";
import { ResumoPrevisao } from "@/components/inicio/ResumoPrevisao.tsx";
import { HorariosFecho } from "@/components/noite/HorariosFecho.tsx";
import { CodigoDia } from "@/components/ui/CodigoDia.tsx";
import { FaixaKpis, Kpi } from "@/components/ui/Kpi.tsx";
import { Painel } from "@/components/ui/Painel.tsx";
import { QualidadeDados } from "@/components/ui/QualidadeDados.tsx";
import { Selo } from "@/components/ui/Selo.tsx";
import { caminhoEstado } from "@/components/voto-antecipado/PaginaEstado.tsx";
import { QuemVotouCriterios } from "@/components/voto-antecipado/QuemVotouCriterios.tsx";
import { nomeEstado } from "@/lib/estados.ts";
import {
  DIA_DA_ELEICAO,
  diasAteEleicao,
  formatarCompacto,
  formatarData,
  formatarHora,
  formatarMargem,
  formatarNumero,
  formatarPercentagem,
  formatarPontos,
  formatarVariacao,
} from "@/lib/formatacao.ts";
import { metadadosPagina } from "@/lib/metadados.ts";
import { t } from "@/lib/mensagens.ts";
import { faseEm, INICIO_NOITE } from "@/lib/fases.ts";
import { carregarPrevisao } from "@/lib/previsao/carregar.ts";
import { carregarResultados } from "@/lib/resultados/carregar.ts";
import { previsaoParaResultados } from "@/lib/resultados/vista.ts";
import { carregarTodas } from "@/lib/voto-antecipado/carregar.ts";
import { resumirEstado, resumirTodos, type ResumoEstado } from "@/lib/voto-antecipado/resumo.ts";
import { criteriosQuemVotou } from "@/lib/voto-antecipado/criterios.ts";

export const metadata: Metadata = metadadosPagina({
  titulo: null,
  descricao: t("site.descricao"),
  caminho: "/",
  cartao: "inicio.png",
});

const LIGACAO = "text-ink underline decoration-rule underline-offset-[3px] hover:decoration-ink-3";

/**
 * Frase gerada a partir dos dados do estado principal; só com números que existem.
 * Ritmo, partido, modo, voto novo e idade, cada um com uma oração e o mesmo peso.
 */
function narrativa(resumo: ResumoEstado): string | null {
  const { anoBase, variacaoVotos } = resumo;
  if (anoBase === null || variacaoVotos === null) return null;
  const partes = [
    t("inicio.narrativa", {
      estado: nomeEstado(resumo.estado),
      votos: formatarNumero(resumo.votos),
      variacao: formatarVariacao(variacaoVotos),
      ano: anoBase,
    }),
  ];
  if (resumo.vantagemDemRep !== null && resumo.vantagemDemRepBase !== null) {
    partes.push(
      t("inicio.narrativaPartido", {
        vantagem: formatarMargem(resumo.vantagemDemRep),
        base: formatarMargem(resumo.vantagemDemRepBase),
        ano: anoBase,
      }),
    );
  }
  if (resumo.quotaCorreio !== null && resumo.quotaCorreioBase !== null) {
    partes.push(
      t("inicio.narrativaModo", {
        correio: formatarPercentagem(resumo.quotaCorreio),
        pontos: formatarPontos(resumo.quotaCorreio - resumo.quotaCorreioBase),
        ano: anoBase,
      }),
    );
  }
  if (resumo.quotaNovos !== null) {
    partes.push(t("inicio.narrativaNovos", { novos: formatarPercentagem(resumo.quotaNovos) }));
  }
  if (resumo.quota65 !== null && resumo.quota65Base !== null) {
    partes.push(
      t("inicio.narrativaIdade", {
        quota65: formatarPercentagem(resumo.quota65),
        pontos: formatarPontos(resumo.quota65 - resumo.quota65Base),
        ano: anoBase,
      }),
    );
  }
  return partes.join(" ");
}

function Indicadores({
  principal,
  resumos,
}: {
  /** Estado com ficheiro de eleitores, de onde vêm os indicadores por grupo. */
  principal: ResumoEstado | undefined;
  resumos: readonly ResumoEstado[];
}) {
  const anoBase = principal?.anoBase ?? resumos.find((r) => r.anoBase !== null)?.anoBase ?? null;
  if (resumos.length === 0) return null;
  // Variação conjunta: só os estados com comparação no mesmo ano de referência,
  // cada um no seu próprio dia do ciclo. Não é um total nacional.
  const comBase = resumos.filter((r) => r.anoBase === anoBase && r.votosBase !== null);
  const votosBase = comBase.reduce((s, r) => s + (r.votosBase ?? 0), 0);
  const votos = comBase.reduce((s, r) => s + r.votos, 0);
  const variacao = votosBase > 0 ? votos / votosBase - 1 : null;
  const total = resumos.reduce((s, r) => s + r.votos, 0);
  const ano = anoBase ?? "";
  return (
    <FaixaKpis>
      <Kpi
        rotulo={t("inicio.kpis.votos")}
        valor={formatarCompacto(total)}
        {...(variacao === null || anoBase === null
          ? {}
          : {
              detalhe:
                comBase.length > 1
                  ? t("inicio.kpis.votosDetalhe", {
                      n: comBase.length,
                      variacao: formatarVariacao(variacao),
                      ano: anoBase,
                    })
                  : t("inicio.kpis.votosDetalheUm", {
                      variacao: formatarVariacao(variacao),
                      ano: anoBase,
                    }),
            })}
      />
      {principal ? (
        <>
          {principal.vantagemDemRep === null || principal.vantagemDemRepBase === null ? null : (
            <Kpi
              rotulo={`${t("votoAntecipado.kpis.vantagem")} · ${principal.estado}`}
              valor={formatarMargem(principal.vantagemDemRep)}
              detalhe={t("votoAntecipado.kpis.vantagemDetalhe", {
                base: formatarMargem(principal.vantagemDemRepBase),
                ano,
              })}
            />
          )}
          {principal.quotaCorreio === null || principal.quotaCorreioBase === null ? null : (
            <Kpi
              rotulo={`${t("votoAntecipado.kpis.correio")} · ${principal.estado}`}
              valor={formatarPercentagem(principal.quotaCorreio)}
              detalhe={t("votoAntecipado.kpis.correioDetalhe", {
                pontos: formatarPontos(principal.quotaCorreio - principal.quotaCorreioBase),
                ano,
              })}
            />
          )}
          {principal.quotaNovos === null ? null : (
            <Kpi
              rotulo={`${t("votoAntecipado.kpis.novos")} · ${principal.estado}`}
              valor={formatarPercentagem(principal.quotaNovos)}
              detalhe={t("votoAntecipado.kpis.novosDetalhe", {
                ano,
                base:
                  principal.quotaNovosBase === null
                    ? t("comum.semDados")
                    : formatarPercentagem(principal.quotaNovosBase),
              })}
            />
          )}
          {principal.quota65 === null || principal.quota65Base === null ? null : (
            <Kpi
              rotulo={`${t("votoAntecipado.kpis.quota65")} · ${principal.estado}`}
              valor={formatarPercentagem(principal.quota65)}
              detalhe={t("votoAntecipado.kpis.quota65Detalhe", {
                pontos: formatarPontos(principal.quota65 - principal.quota65Base),
                ano,
              })}
            />
          )}
        </>
      ) : null}
    </FaixaKpis>
  );
}

function EstadosAcompanhados({
  resumos,
  comPagina,
}: {
  resumos: readonly ResumoEstado[];
  /** Estados com página própria. */
  comPagina: ReadonlySet<string>;
}) {
  const anoBase = resumos[0]?.anoBase ?? 2022;
  return (
    <Painel
      sobrelinha={t("inicio.estados.sobrelinha")}
      titulo={t("inicio.estados.titulo")}
      descricao={t("inicio.estados.texto", { ano: anoBase })}
      metodo={t("inicio.estados.metodo", { ano: anoBase })}
    >
      <div
        aria-hidden="true"
        className="rotulo grid grid-cols-[minmax(0,1fr)_auto_4.5rem_4.5rem] gap-3 text-right"
      >
        <span />
        <span />
        <span>{t("inicio.estados.colunaRitmo")}</span>
        <span>{t("inicio.estados.colunaVantagem")}</span>
      </div>
      <ol className="-mt-2 flex flex-col">
        {resumos.map((r) => (
          <li
            key={r.estado}
            className="grid grid-cols-[minmax(0,1fr)_auto_4.5rem_4.5rem] items-center gap-3 border-t border-rule-2 py-2.5 text-sm first:border-t-0"
          >
            {comPagina.has(r.estado) ? (
              <Link href={caminhoEstado(r.estado)} prefetch={false} className={LIGACAO}>
                {nomeEstado(r.estado)}
              </Link>
            ) : (
              <span>{nomeEstado(r.estado)}</span>
            )}
            <QualidadeDados nivel={r.qualidade} naoOficial={r.naoOficial} />
            <span className="text-right font-mono text-[13px] font-medium">
              <span className="sr-only">{t("inicio.estados.colunaRitmo")}: </span>
              {r.variacaoVotos === null ? t("comum.semDados") : formatarVariacao(r.variacaoVotos)}
            </span>
            <span className="text-right font-mono text-[13px] text-ink-2">
              <span className="sr-only">{t("inicio.estados.colunaVantagem")}: </span>
              {r.vantagemDemRep === null ? t("comum.semDados") : formatarMargem(r.vantagemDemRep)}
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

/** Topo da noite antes de haver contagem ou projeção publicadas. */
function AguardaNoite() {
  return (
    <Painel
      sobrelinha={t("noite.inicio.sobrelinha")}
      titulo={t("inicio.aoVivo.aguardaTitulo")}
      acessorio={<Selo variante="sinal">{t("comum.selos.aoVivo")}</Selo>}
    >
      <p className="max-w-[62ch] text-ink-2">
        {t("inicio.aoVivo.aguardaTexto", {
          lisboa: formatarHora(INICIO_NOITE, "Europe/Lisbon"),
          washington: formatarHora(INICIO_NOITE),
        })}
      </p>
      <p className="text-sm">
        <Link href="/resultados/" className={LIGACAO}>
          {t("noite.inicio.ligacao")}
        </Link>
      </p>
    </Painel>
  );
}

export default function Inicio() {
  // Calculado no momento do build; o site é reconstruído a cada atualização de dados.
  // A fase volta a ser calculada no browser (FaseInicio), para mudar sem novo build.
  const agora = new Date();
  const dias = diasAteEleicao(agora);
  const todas = carregarTodas();
  const resumos = resumirTodos(todas);
  // A narrativa e "Quem já votou" usam o estado com ficheiro de eleitores e mais votos.
  const principal = todas.individuais[0];
  const resumoPrincipal = principal ? resumirEstado(principal) : undefined;
  const frase = resumoPrincipal ? narrativa(resumoPrincipal) : null;
  const previsao = carregarPrevisao()?.previsao ?? null;
  const noite = carregarResultados();
  const previsaoNoite = previsao ? previsaoParaResultados(previsao) : null;
  // Só as corridas em jogo: as decididas antes da eleição não avaliam a previsão.
  const probD = Object.fromEntries(
    (previsao ? [...previsao.corridasSenado, ...previsao.corridasCamara] : [])
      .filter((c) => c.decidida === null)
      .map((c) => [c.id, c.probD]),
  );

  const contagem = (
    <Painel
      sobrelinha={t("inicio.sobrelinha")}
      titulo={formatarData(DIA_DA_ELEICAO)}
      acessorio={<CodigoDia dias={dias} />}
      metodo={t("inicio.metodo")}
    >
      {/* Sem quebra de linha entre o número e a etiqueta: com a letra de reserva, mais larga,
          a etiqueta quebra dentro da sua coluna e a altura não muda quando a letra chega (CLS). */}
      <div className="flex items-end gap-4">
        <span className="font-display text-[clamp(76px,11vw,128px)] leading-[0.82] font-black tracking-[-0.01em]">
          {dias}
        </span>
        <span className="min-w-0 pb-1.5 font-display text-[22px] leading-[1.05] font-bold tracking-[0.03em] uppercase">
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
            <Link href={caminhoEstado(resumoPrincipal.estado)} prefetch={false} className={LIGACAO}>
              {t("inicio.verRastreador")}
            </Link>
          </p>
        </>
      ) : null}
    </Painel>
  );

  return (
    <>
      <h1 className="sr-only">{t("inicio.titulo")}</h1>
      <div className="flex flex-col gap-4">
        <FaseInicio
          faseBuild={faseEm(agora)}
          antes={
            <>
              {/* Nos últimos três dias, o início mostra os horários de fecho. */}
              {dias <= 3 ? <HorariosFecho previsao={previsao} /> : null}
              <div className="grid gap-4 min-[860px]:grid-cols-[minmax(0,1.05fr)_minmax(0,1fr)]">
                {contagem}
                <ResumoPrevisao vista={previsao} />
              </div>
            </>
          }
          noite={
            <>
              <InicioAoVivo
                inicial={noite}
                previsao={previsaoNoite}
                probD={probD}
                depois={false}
                emPreparacao={<AguardaNoite />}
              />
              <HorariosFecho previsao={previsao} />
            </>
          }
          depois={
            <>
              <InicioAoVivo
                inicial={noite}
                previsao={previsaoNoite}
                probD={probD}
                depois
                emPreparacao={null}
              />
              <ResumoPrevisao vista={previsao} depois />
            </>
          }
        />

        <Indicadores principal={resumoPrincipal} resumos={resumos} />

        <div className="flex flex-col gap-4">
          {principal ? (
            <Painel
              sobrelinha={t("inicio.quemVotou.sobrelinha", {
                estado: nomeEstado(principal.estado),
              })}
              titulo={t("inicio.quemVotou.titulo")}
              fontes={principal.fontes.slice(0, 1)}
              metodo={t("votoAntecipado.criterios.metodo")}
            >
              <QuemVotouCriterios blocos={criteriosQuemVotou(principal)} ano={principal.ano} />
              <p className="text-sm">
                <Link href={caminhoEstado(principal.estado)} prefetch={false} className={LIGACAO}>
                  {t("inicio.quemVotou.ligacao")}
                </Link>
              </p>
            </Painel>
          ) : null}
          {resumos.length > 0 ? (
            <EstadosAcompanhados
              resumos={resumos}
              comPagina={new Set(resumos.map((r) => r.estado))}
            />
          ) : (
            <OQueVemAi />
          )}
        </div>
      </div>
    </>
  );
}
