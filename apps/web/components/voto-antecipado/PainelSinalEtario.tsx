import { Painel } from "@/components/ui/Painel.tsx";
import { Selo } from "@/components/ui/Selo.tsx";
import {
  formatarData,
  formatarDecimal,
  formatarMargemPontos,
  formatarNumero,
  formatarPercentagem,
  formatarPontos,
} from "@/lib/formatacao.ts";
import { t } from "@/lib/mensagens.ts";
import type { VistaIdade } from "@/lib/voto-antecipado/idade.ts";
import { rotuloFaixa } from "./anos.ts";

const CELULA = "py-1.5 pr-2 text-right font-mono text-[12.5px] sm:pr-3 sm:text-[13px]";
const CABECALHO = "pr-2 pb-1.5 text-right font-medium sm:pr-3";

function data(dia: string): Date {
  return new Date(`${dia}T12:00:00Z`);
}

function Selos() {
  return (
    <span className="flex flex-wrap gap-1.5">
      <Selo variante="tracejado">{t("comum.selos.estimativa")}</Selo>
      <Selo variante="tracejado">{t("votoAntecipado.sinalEtario.pesoZero")}</Selo>
    </span>
  );
}

function TabelaFaixas({ vista }: { vista: VistaIdade }) {
  return (
    <table className="w-full border-collapse text-sm">
      <caption className="sr-only">
        {t("votoAntecipado.sinalEtario.legendaFaixas", { ano: vista.anoReferencia })}
      </caption>
      <thead>
        <tr className="rotulo">
          <th scope="col" className="pr-3 pb-1.5 text-left font-medium">
            {t("votoAntecipado.sinalEtario.colunas.faixa")}
          </th>
          <th scope="col" className={CABECALHO}>
            {t("votoAntecipado.sinalEtario.colunas.projetada")}
          </th>
          <th scope="col" className={CABECALHO}>
            {t("votoAntecipado.sinalEtario.colunas.referencia", { ano: vista.anoReferencia })}
          </th>
          <th scope="col" className="pb-1.5 text-right font-medium">
            {t("votoAntecipado.sinalEtario.colunas.diferenca")}
          </th>
        </tr>
      </thead>
      <tbody>
        {vista.faixas.map((f) => (
          <tr key={f.faixa} className="border-t border-rule-2">
            <th scope="row" className="py-1.5 pr-3 text-left font-semibold">
              {rotuloFaixa(f.faixa)}
            </th>
            <td className={CELULA}>{formatarPercentagem(f.quotaProjetada)}</td>
            <td className={`${CELULA} text-ink-2`}>{formatarPercentagem(f.quotaReferencia)}</td>
            <td className="py-1.5 text-right font-mono text-[12.5px] sm:text-[13px]">
              {formatarPontos(f.quotaProjetada - f.quotaReferencia)}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function TabelaPartidos({ vista }: { vista: VistaIdade }) {
  return (
    <details className="text-sm">
      <summary className="cursor-pointer text-ink underline decoration-rule underline-offset-[3px]">
        {t("votoAntecipado.sinalEtario.porPartido")}
      </summary>
      <div className="mt-2 overflow-x-auto">
        <table className="w-full border-collapse">
          <caption className="sr-only">{t("votoAntecipado.sinalEtario.legendaPartidos")}</caption>
          <thead>
            <tr className="rotulo">
              <th scope="col" className="pr-3 pb-1.5 text-left font-medium">
                {t("votoAntecipado.sinalEtario.colunas.grupo")}
              </th>
              <th scope="col" className={CABECALHO}>
                {t("votoAntecipado.sinalEtario.colunas.projetada")}
              </th>
              <th scope="col" className={CABECALHO}>
                {t("votoAntecipado.sinalEtario.colunas.referencia", { ano: vista.anoReferencia })}
              </th>
              <th scope="col" className="pb-1.5 text-right font-medium">
                {t("votoAntecipado.sinalEtario.colunas.margem")}
              </th>
            </tr>
          </thead>
          <tbody>
            {vista.faixas.flatMap((f) =>
              f.partidos.map((p) => (
                <tr key={`${f.faixa}-${p.partido}`} className="border-t border-rule-2">
                  <th scope="row" className="py-1.5 pr-3 text-left font-normal">
                    <span className="font-semibold">{rotuloFaixa(f.faixa)}</span>{" "}
                    <span className="text-ink-2">{t(`votoAntecipado.partidos.${p.partido}`)}</span>
                  </th>
                  <td className={CELULA}>{formatarPercentagem(p.quotaProjetada)}</td>
                  <td className={`${CELULA} text-ink-2`}>
                    {formatarPercentagem(p.quotaReferencia)}
                  </td>
                  <td className="py-1.5 text-right font-mono text-[12.5px] sm:text-[13px]">
                    {formatarMargemPontos(p.margem, 0)}
                    <span className="block text-[11px] whitespace-nowrap text-ink-3">
                      {t("votoAntecipado.sinalEtario.entre", {
                        de: formatarMargemPontos(p.margemMinima, 0),
                        ate: formatarMargemPontos(p.margemMaxima, 0),
                      })}
                    </span>
                  </td>
                </tr>
              )),
            )}
          </tbody>
        </table>
      </div>
    </details>
  );
}

function Backtests({ vista }: { vista: VistaIdade }) {
  if (vista.backtests.length === 0) return null;
  return (
    <div className="flex flex-col gap-1.5">
      <h3 className="rotulo">{t("votoAntecipado.sinalEtario.backtestsTitulo")}</h3>
      <table className="w-full border-collapse text-sm">
        <caption className="sr-only">
          {t("votoAntecipado.sinalEtario.backtestsLegenda", { dias: vista.diasAntes })}
        </caption>
        <thead>
          <tr className="rotulo">
            <th scope="col" className="pr-3 pb-1.5 text-left font-medium">
              {t("votoAntecipado.sinalEtario.colunas.eleicao")}
            </th>
            <th scope="col" className={CABECALHO}>
              {t("votoAntecipado.sinalEtario.colunas.real")}
            </th>
            <th scope="col" className="pb-1.5 text-right font-medium">
              {t("votoAntecipado.sinalEtario.colunas.projetadaBacktest")}
            </th>
          </tr>
        </thead>
        <tbody>
          {vista.backtests.map((b) => (
            <tr key={b.ano} className="border-t border-rule-2">
              <th scope="row" className="py-1.5 pr-3 text-left font-normal">
                <span className="font-semibold">{b.ano}</span>{" "}
                <span className="text-[12px] text-ink-3">
                  {t("votoAntecipado.sinalEtario.com", { anos: b.referencias.join(", ") })}
                </span>
              </th>
              <td className={CELULA}>{formatarMargemPontos(b.real)}</td>
              <td className="py-1.5 text-right font-mono text-[12.5px] sm:text-[13px]">
                {formatarMargemPontos(b.projetada)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <p className="text-[12px] text-ink-3">
        {t("votoAntecipado.sinalEtario.erro", { erro: formatarDecimal(vista.erroBacktest, 1) })}
      </p>
    </div>
  );
}

/**
 * Sinal etário do voto antecipado: quanto o eleitorado projetado, pela idade e pelo
 * partido de registo, puxa a margem face à intercalar anterior. Peso zero na previsão.
 * `null`: o modelo ainda não publicou o ficheiro (é cedo).
 */
export function PainelSinalEtario({ vista }: { vista: VistaIdade | null }) {
  const comum = {
    sobrelinha: t("votoAntecipado.sinalEtario.sobrelinha"),
    titulo: t("votoAntecipado.sinalEtario.titulo"),
    acessorio: <Selos />,
    metodo: t("votoAntecipado.sinalEtario.metodo"),
  };
  if (!vista) {
    return (
      <Painel {...comum} descricao={t("votoAntecipado.sinalEtario.texto")}>
        <p className="max-w-[62ch] text-ink-2">{t("votoAntecipado.sinalEtario.cedo")}</p>
      </Painel>
    );
  }
  return (
    <Painel
      {...comum}
      descricao={t("votoAntecipado.sinalEtario.textoDados", {
        data: formatarData(data(vista.dataDados)),
        votos: formatarNumero(vista.votos),
        dias: vista.diasAntes,
      })}
      fontes={vista.fontes}
    >
      <div className="grid grid-cols-[minmax(0,1fr)] gap-5 min-[860px]:grid-cols-[minmax(0,1fr)_minmax(0,1.3fr)]">
        <div className="flex min-w-0 flex-col gap-3">
          <dl className="flex flex-col gap-1">
            <dt className="rotulo">
              {t("votoAntecipado.sinalEtario.efeito", { ano: vista.anoReferencia })}
            </dt>
            <dd className="font-display text-[40px] leading-none font-bold">
              {formatarMargemPontos(vista.efeito)}
            </dd>
            <dd className="font-mono text-[12px] text-ink-3">
              {t("votoAntecipado.sinalEtario.intervalo", {
                de: formatarMargemPontos(vista.efeitoP10),
                ate: formatarMargemPontos(vista.efeitoP90),
              })}
            </dd>
          </dl>
          <p className="max-w-[52ch] text-[14px] text-ink-2">
            {t("votoAntecipado.sinalEtario.leitura", {
              projetada: formatarMargemPontos(vista.inclinacaoProjetada),
              referencia: formatarMargemPontos(vista.inclinacaoReferencia),
              ano: vista.anoReferencia,
            })}
          </p>
          <p className="max-w-[52ch] text-[13px] text-ink-3">
            {t("votoAntecipado.sinalEtario.notaPeso")}
          </p>
          <Backtests vista={vista} />
        </div>
        <div className="flex min-w-0 flex-col gap-3">
          <TabelaFaixas vista={vista} />
          <TabelaPartidos vista={vista} />
          {vista.notas.length > 0 ? (
            <ul className="flex list-disc flex-col gap-1 pl-5 text-[12.5px] text-ink-2">
              {vista.notas.map((n) => (
                <li key={n}>{n}</li>
              ))}
            </ul>
          ) : null}
        </div>
      </div>
    </Painel>
  );
}
