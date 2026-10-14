import { DistribuicaoLugares, EvolucaoControlo } from "@/components/previsao/graficos.tsx";
import { Painel } from "@/components/ui/Painel.tsx";
import { Selo } from "@/components/ui/Selo.tsx";
import {
  formatarData,
  formatarHora,
  formatarMargemPontos,
  formatarNumero,
  formatarPercentagem,
  formatarPontos,
} from "@/lib/formatacao.ts";
import { t } from "@/lib/mensagens.ts";
import type { CamaraNoite, VistaNoite } from "@/lib/noite/vista.ts";

const METODOLOGIA = "/metodologia/noite-eleitoral/";

/** Probabilidade de um lado, com a cor do partido (republicano sempre tracejado). */
export function Probabilidade({ lado, valor }: { lado: "D" | "R"; valor: number }) {
  return (
    <span
      className={`inline-block rounded-[2px] p-0.5 font-mono font-semibold ${
        lado === "D" ? "bg-dem px-1.5 text-sheet" : "fundo-rep text-ink"
      }`}
    >
      <span className={lado === "R" ? "block rounded-[1px] bg-sheet px-1" : undefined}>
        {`${lado} ${formatarPercentagem(valor, 0)}`}
      </span>
    </span>
  );
}

/** Selos de um ficheiro da projeção: ensaio e previsão de partida provisória ficam sempre à vista. */
export function SelosNoite({ noite }: { noite: VistaNoite }) {
  return (
    <span className="flex flex-wrap gap-1.5">
      {noite.reconstruido ? <Selo variante="tracejado">{t("noite.selos.ensaio")}</Selo> : null}
      {noite.priorCongelado ? null : (
        <Selo variante="tracejado">{t("noite.selos.provisoria")}</Selo>
      )}
      {noite.ensaio ? null : <Selo variante="sinal">{t("comum.selos.aoVivo")}</Selo>}
      <Selo variante="tracejado">{t("comum.selos.estimativa")}</Selo>
    </span>
  );
}

function Camara({ r, noite }: { r: CamaraNoite; noite: VistaNoite }) {
  const lider = r.probD >= r.probR ? "D" : "R";
  const nome = t(`previsao.camaraNome.${r.camara}`);
  const pontos = noite.evolucao?.[r.camara];
  return (
    <section className="flex min-w-0 flex-col gap-2.5">
      <h3 className="font-display text-[22px] leading-none font-bold">{nome}</h3>
      <p className="flex flex-wrap items-center gap-2 text-[15px]">
        <span className="text-[20px]">
          <Probabilidade lado={lider} valor={lider === "D" ? r.probD : r.probR} />
        </span>
        <span className="text-ink-2">
          {t("noite.camara.controlo", {
            outro: lider === "D" ? "R" : "D",
            prob: formatarPercentagem(lider === "D" ? r.probR : r.probD, 0),
          })}
        </span>
      </p>
      <p className="font-mono text-[12px] text-ink-3">
        {t("noite.camara.prior", {
          prob: formatarPercentagem(r.probDPrior, 0),
          data: formatarData(new Date(`${noite.cortePrior}T12:00:00Z`)),
        })}
      </p>
      <p className="text-sm text-ink-2">
        {t("noite.camara.lugares", {
          mediana: r.mediana,
          de: r.p10,
          ate: r.p90,
          maioria: r.maioria,
          corridas: r.corridasComVotos,
        })}
      </p>
      <DistribuicaoLugares resumo={r} />
      {pontos && pontos.length > 1 ? (
        <figure className="flex flex-col gap-1">
          <figcaption className="rotulo">{t("noite.camara.evolucao")}</figcaption>
          <EvolucaoControlo
            pontos={pontos}
            escala="hora"
            titulo={t("previsao.evolucao.aria", {
              camara: t(`previsao.camaraNa.${r.camara}`),
              de: formatarPercentagem(pontos[0]?.probD ?? 0, 0),
              ate: formatarPercentagem(pontos.at(-1)?.probD ?? 0, 0),
            })}
          />
        </figure>
      ) : null}
    </section>
  );
}

/** Controlo da Câmara e do Senado projetado a partir dos votos contados. */
export function PainelProjecao({ noite }: { noite: VistaNoite }) {
  const { desvio } = noite;
  return (
    <Painel
      sobrelinha={t("noite.sobrelinha", { hora: formatarHora(new Date(noite.instante)) })}
      titulo={t("noite.titulo")}
      descricao={t("noite.texto")}
      acessorio={<SelosNoite noite={noite} />}
      fontes={noite.fontes}
      metodo={t("noite.metodo", { simulacoes: formatarNumero(noite.simulacoes) })}
    >
      {noite.reconstruido ? (
        <p
          role="note"
          className="rounded-[3px] border border-dashed border-ink-3 px-3 py-2 text-sm"
        >
          {t("noite.avisoEnsaio", { ano: noite.ano })}
        </p>
      ) : null}
      {noite.priorCongelado ? null : (
        <p
          role="note"
          className="rounded-[3px] border border-dashed border-ink-3 px-3 py-2 text-sm"
        >
          {t("noite.avisoProvisoria", {
            data: formatarData(new Date(`${noite.cortePrior}T12:00:00Z`)),
          })}
        </p>
      )}
      <div className="grid gap-6 md:grid-cols-2">
        <Camara r={noite.camara} noite={noite} />
        <Camara r={noite.senado} noite={noite} />
      </div>
      <p className="max-w-[70ch] text-sm text-ink-2">
        {desvio.corridas === 0
          ? t("noite.desvioSemDados")
          : t("noite.desvio", {
              margem: formatarMargemPontos(desvio.media),
              dp: formatarPontos(desvio.desvioPadrao / 100).replace("+", ""),
              n: desvio.corridas,
            })}
      </p>
      <p className="text-sm">
        <a
          href={METODOLOGIA}
          rel="noopener noreferrer"
          className="text-ink underline decoration-rule underline-offset-[3px]"
        >
          {t("noite.documentacao")}
        </a>
      </p>
    </Painel>
  );
}
