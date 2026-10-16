import Link from "next/link";
import { Kpi } from "@/components/ui/Kpi.tsx";
import { Painel } from "@/components/ui/Painel.tsx";
import { caminhoPaginaCorrida } from "@/lib/corridas.ts";
import {
  formatarData,
  formatarDataCurta,
  formatarDecimal,
  formatarPercentagem,
} from "@/lib/formatacao.ts";
import { t } from "@/lib/mensagens.ts";
import type { CorridaAvaliada, VistaAvaliacao } from "@/lib/previsao/avaliacao.ts";
import type { VistaPrognosticos } from "@/lib/previsao/prognosticos.ts";
import type { Lado, VistaPrevisao } from "@/lib/previsao/vista.ts";
import { rotuloPosicao } from "./PainelPrognosticos.tsx";
import { VersaoPrevisao, data } from "./PaginaPrevisao.tsx";

const LIGACAO = "text-ink underline decoration-rule underline-offset-[3px]";

function MarcaLado({ lado }: { lado: Lado }) {
  return (
    <span
      aria-hidden="true"
      className={`mr-1.5 inline-block size-2.5 rounded-[1px] align-middle ${lado === "D" ? "fundo-dem" : "fundo-rep"}`}
    />
  );
}

function fontesChamadas() {
  return [{ nome: t("previsao.avaliacao.fonteChamadas") }];
}

function Indicadores({ a }: { a: VistaAvaliacao }) {
  const n = a.avaliadas.length;
  return (
    <dl className="grid overflow-hidden rounded-md border border-rule bg-sheet sm:grid-cols-3">
      <Kpi
        rotulo={t("previsao.avaliacao.kpis.acertos")}
        valor={t("previsao.avaliacao.kpis.acertosValor", { acertos: a.acertos, n })}
        detalhe={formatarPercentagem(a.acertos / n, 0)}
      />
      <Kpi
        rotulo={t("previsao.avaliacao.kpis.brier")}
        valor={a.brier === null ? "—" : formatarDecimal(a.brier, 3)}
        detalhe={t("previsao.avaliacao.kpis.brierDetalhe")}
      />
      <Kpi
        rotulo={t("previsao.avaliacao.kpis.pendentes")}
        valor={a.emJogo - n - a.outro.length}
        detalhe={t("previsao.avaliacao.kpis.pendentesDetalhe", { total: a.emJogo })}
      />
    </dl>
  );
}

function PainelCalibracao({ a }: { a: VistaAvaliacao }) {
  return (
    <Painel
      sobrelinha={t("previsao.avaliacao.calibracao.sobrelinha")}
      titulo={t("previsao.avaliacao.calibracao.titulo")}
      descricao={t("previsao.avaliacao.calibracao.texto")}
      fontes={fontesChamadas()}
      metodo={t("previsao.avaliacao.calibracao.metodo")}
    >
      <table className="w-full border-collapse text-sm">
        <caption className="sr-only">{t("previsao.avaliacao.calibracao.legenda")}</caption>
        <thead>
          <tr className="rotulo">
            <th scope="col" className="pb-1.5 pr-2 text-left font-medium">
              {t("previsao.avaliacao.calibracao.grupo")}
            </th>
            <th scope="col" className="pb-1.5 pl-2 text-right font-medium">
              {t("previsao.avaliacao.calibracao.corridas")}
            </th>
            <th scope="col" className="pb-1.5 pl-2 text-right font-medium">
              {t("previsao.avaliacao.calibracao.esperado")}
            </th>
            <th scope="col" className="pb-1.5 pl-2 text-right font-medium">
              {t("previsao.avaliacao.calibracao.observado")}
            </th>
          </tr>
        </thead>
        <tbody className="font-mono text-[13px]">
          {a.calibracao.map((g) => (
            <tr key={g.de} className="border-t border-rule-2">
              <th scope="row" className="py-1.5 pr-2 text-left font-sans font-normal">
                {t("previsao.avaliacao.calibracao.intervalo", {
                  de: formatarPercentagem(g.de, 0),
                  ate: formatarPercentagem(g.ate, 0),
                })}
              </th>
              <td className="py-1.5 pl-2 text-right">{g.n}</td>
              <td className="py-1.5 pl-2 text-right">
                {g.esperado === null
                  ? t("previsao.avaliacao.calibracao.vazio")
                  : formatarPercentagem(g.esperado, 0)}
              </td>
              <td className="py-1.5 pl-2 text-right">
                {g.n === 0
                  ? t("previsao.avaliacao.calibracao.vazio")
                  : formatarPercentagem(g.acertos / g.n, 0)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </Painel>
  );
}

function PainelPrognosticadores({
  a,
  prognosticos,
}: {
  a: VistaAvaliacao;
  prognosticos: VistaPrognosticos;
}) {
  return (
    <Painel
      sobrelinha={t("previsao.avaliacao.prognosticadores.sobrelinha")}
      titulo={t("previsao.avaliacao.prognosticadores.titulo")}
      descricao={t("previsao.avaliacao.prognosticadores.texto")}
      fontes={[...fontesChamadas(), ...prognosticos.fontes]}
      metodo={t("previsao.avaliacao.prognosticadores.metodo")}
    >
      {a.prognosticadores.length === 0 ? (
        <p className="text-sm text-ink-2">{t("previsao.avaliacao.prognosticadores.vazio")}</p>
      ) : (
        <table className="w-full border-collapse text-sm">
          <caption className="sr-only">{t("previsao.avaliacao.prognosticadores.legenda")}</caption>
          <thead>
            <tr className="rotulo">
              <th scope="col" className="pb-1.5 pr-2 text-left font-medium">
                {t("previsao.avaliacao.prognosticadores.nome")}
              </th>
              <th scope="col" className="hidden pb-1.5 pl-2 text-right font-medium sm:table-cell">
                {t("previsao.avaliacao.prognosticadores.classificadas")}
              </th>
              <th scope="col" className="pb-1.5 pl-2 text-right font-medium">
                {t("previsao.avaliacao.prognosticadores.acertos")}
              </th>
              <th scope="col" className="hidden pb-1.5 pl-2 text-right font-medium sm:table-cell">
                {t("previsao.avaliacao.prognosticadores.empates")}
              </th>
              <th scope="col" className="pb-1.5 pl-2 text-right font-medium">
                {t("previsao.avaliacao.prognosticadores.escrutinio")}
              </th>
            </tr>
          </thead>
          <tbody className="font-mono text-[13px]">
            {a.prognosticadores.map((p) => (
              <tr key={p.chave} className="border-t border-rule-2">
                <th
                  scope="row"
                  className="py-1.5 pr-2 text-left font-sans font-normal [overflow-wrap:anywhere]"
                >
                  {p.nome}
                  <span className="block font-mono text-[11.5px] text-ink-3 sm:hidden">
                    {t("previsao.avaliacao.prognosticadores.n", { n: p.classificadas })}
                  </span>
                </th>
                <td className="hidden py-1.5 pl-2 text-right sm:table-cell">{p.classificadas}</td>
                <td className="py-1.5 pl-2 text-right">{p.acertos}</td>
                <td className="hidden py-1.5 pl-2 text-right sm:table-cell">{p.empates}</td>
                <td className="py-1.5 pl-2 text-right">{p.acertosEscrutinio}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </Painel>
  );
}

/** Favoritos a menos disto, e as falhas, mostram-se sempre; os outros ficam recolhidos. */
const DESTAQUE = 0.8;

function TabelaCorridas({ corridas }: { corridas: readonly CorridaAvaliada[] }) {
  return (
    <table className="w-full border-collapse text-sm">
      <caption className="sr-only">{t("previsao.avaliacao.corridas.legenda")}</caption>
      <thead>
        <tr className="rotulo">
          <th scope="col" className="pb-1.5 pr-2 text-left font-medium">
            {t("previsao.avaliacao.corridas.corrida")}
          </th>
          <th scope="col" className="pb-1.5 pl-2 text-left font-medium">
            {t("previsao.avaliacao.corridas.vencedor")}
          </th>
          <th scope="col" className="pb-1.5 pl-2 text-right font-medium">
            {t("previsao.avaliacao.corridas.prob")}
          </th>
          <th scope="col" className="hidden pb-1.5 pl-2 text-right font-medium sm:table-cell">
            {t("previsao.avaliacao.corridas.consenso")}
          </th>
        </tr>
      </thead>
      <tbody>
        {corridas.map((c) => (
          <tr key={c.corrida.id} className="border-t border-rule-2 align-top">
            <th scope="row" className="py-1.5 pr-2 text-left font-normal">
              <Link
                href={caminhoPaginaCorrida(c.corrida.id)}
                className={`font-semibold ${LIGACAO}`}
              >
                {c.corrida.id}
              </Link>
              {c.acertou ? null : (
                <span className="block text-[12px] text-ink-2">
                  {t("previsao.avaliacao.corridas.falhou")}
                </span>
              )}
            </th>
            <td className="py-1.5 pl-2 whitespace-nowrap">
              <MarcaLado lado={c.vencedor} />
              {c.vencedor}
            </td>
            <td className="py-1.5 pl-2 text-right font-mono text-[13px]">
              {formatarPercentagem(c.probVencedor, 0)}
            </td>
            <td className="hidden py-1.5 pl-2 text-right text-[13px] sm:table-cell">
              {c.consenso === null ? "—" : rotuloPosicao(c.consenso)}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function PainelCorridas({ a }: { a: VistaAvaliacao }) {
  const ordenadas: CorridaAvaliada[] = [...a.avaliadas].sort(
    (x, y) => x.probVencedor - y.probVencedor || x.corrida.id.localeCompare(y.corrida.id),
  );
  const destaque = ordenadas.filter((c) => !c.acertou || c.probVencedor < DESTAQUE);
  const resto = ordenadas.filter((c) => c.acertou && c.probVencedor >= DESTAQUE);
  return (
    <Painel
      sobrelinha={t("previsao.avaliacao.corridas.sobrelinha")}
      titulo={t("previsao.avaliacao.corridas.titulo")}
      descricao={t("previsao.avaliacao.corridas.texto")}
      fontes={fontesChamadas()}
      metodo={t("previsao.avaliacao.corridas.metodo")}
    >
      {destaque.length > 0 ? <TabelaCorridas corridas={destaque} /> : null}
      {resto.length > 0 ? (
        <details>
          <summary className={`cursor-pointer text-sm ${LIGACAO}`}>
            {t("previsao.avaliacao.corridas.mais", { n: resto.length })}
          </summary>
          <div className="mt-2">
            <TabelaCorridas corridas={resto} />
          </div>
        </details>
      ) : null}
      {a.outro.length > 0 ? (
        <p className="text-[12.5px] text-ink-2">
          {t("previsao.avaliacao.corridas.outro", { corridas: a.outro.join(", ") })}
        </p>
      ) : null}
    </Painel>
  );
}

/** Página /previsao/avaliacao/: a previsão congelada contra as chamadas das redações. */
export function PaginaAvaliacao({
  vista,
  avaliacao: a,
  prognosticos,
}: {
  vista: VistaPrevisao;
  avaliacao: VistaAvaliacao;
  prognosticos: VistaPrognosticos | null;
}) {
  return (
    <div className="flex flex-col gap-4">
      <header className="flex flex-wrap items-start justify-between gap-x-6 gap-y-3">
        <div className="min-w-0">
          <p className="rotulo mb-1">{t("previsao.avaliacao.sobrelinha", { ano: vista.ano })}</p>
          <h1 className="font-display text-[clamp(30px,5vw,40px)] leading-[1.02] font-bold">
            {t("previsao.avaliacao.titulo")}
          </h1>
          <p className="mt-1.5 max-w-[68ch] text-[15.5px] text-ink-2">
            {t("previsao.avaliacao.lede")}
          </p>
          {vista.congelada ? null : (
            <p className="mt-1.5 max-w-[68ch] text-sm text-ink-2">
              {t("previsao.avaliacao.provisoria", { data: formatarData(data(vista.corte)) })}
            </p>
          )}
          {prognosticos && !prognosticos.congelado ? (
            <p className="mt-1.5 max-w-[68ch] text-sm text-ink-2">
              {t("previsao.avaliacao.prognosticosProvisorios", {
                data: formatarDataCurta(new Date(prognosticos.recolhidoEm)),
              })}
            </p>
          ) : null}
        </div>
        <VersaoPrevisao vista={vista} />
      </header>

      {a.avaliadas.length === 0 ? (
        <Painel
          titulo={t("previsao.avaliacao.aguarda.titulo")}
          descricao={t("previsao.avaliacao.aguarda.texto")}
          fontes={fontesChamadas()}
        >
          <p className="text-sm">
            <Link href="/previsao/" className={LIGACAO}>
              {t("previsao.avaliacao.aguarda.ligacao")}
            </Link>
          </p>
        </Painel>
      ) : (
        <>
          <Indicadores a={a} />
          <div className="grid gap-4 min-[860px]:grid-cols-2">
            <PainelCalibracao a={a} />
            {prognosticos ? <PainelPrognosticadores a={a} prognosticos={prognosticos} /> : null}
          </div>
          <PainelCorridas a={a} />
        </>
      )}
    </div>
  );
}
