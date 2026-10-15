import Link from "next/link";
import { Painel } from "@/components/ui/Painel.tsx";
import { Selo } from "@/components/ui/Selo.tsx";
import { caminhoPaginaCorrida } from "@/lib/corridas.ts";
import { nomeEstado } from "@/lib/estados.ts";
import { formatarDataCurta, formatarPercentagem } from "@/lib/formatacao.ts";
import { t } from "@/lib/mensagens.ts";
import {
  CENTRO,
  corDe,
  type ClassificacaoVista,
  type ComparacaoCorrida,
  type ResumoComparacao,
  type VistaPrognosticos,
} from "@/lib/previsao/prognosticos.ts";
import { CATEGORIAS, type Categoria, type CorridaVista } from "@/lib/previsao/vista.ts";
import { ESTILO_CATEGORIA, data } from "./PaginaPrevisao.tsx";

const LIGACAO = "text-ink underline decoration-rule underline-offset-[3px]";

function Amostra({ cor, tamanho = "size-3" }: { cor: Categoria; tamanho?: string }) {
  return (
    <span
      aria-hidden="true"
      className={`inline-block shrink-0 rounded-[2px] ${tamanho} ${ESTILO_CATEGORIA[cor].className}`}
      style={ESTILO_CATEGORIA[cor].style}
    />
  );
}

/** "Provável R", "Ligeira D" ou "Empate". */
export function rotuloClassificacao(c: Pick<ClassificacaoVista, "categoria" | "lado">): string {
  if (c.categoria === "empate" || c.lado === null) return t("previsao.prognosticos.empate");
  return t(`previsao.prognosticos.categorias.${c.categoria}`, { lado: c.lado });
}

/** Categoria na escala do Escrutínio; a meio caminho entre duas, "Entre X e Y". */
export function rotuloPosicao(posicao: number): string {
  const exata = CATEGORIAS[posicao];
  if (Number.isInteger(posicao) && exata) return t(`previsao.categorias.${exata}`);
  const a = CATEGORIAS[Math.floor(posicao)] ?? "renhida";
  const b = CATEGORIAS[Math.ceil(posicao)] ?? "renhida";
  return t("previsao.prognosticos.entre", {
    a: t(`previsao.categorias.${a}`),
    b: t(`previsao.categorias.${b}`),
  });
}

function textoDivergencia(c: ComparacaoCorrida): string | null {
  if (c.divergencia === "favorito") return t("previsao.prognosticos.divergeFavorito");
  if (c.divergencia === "confianca") {
    return t(
      Math.abs(c.nossaPosicao - CENTRO) > Math.abs(c.consenso - CENTRO)
        ? "previsao.prognosticos.divergeMais"
        : "previsao.prognosticos.divergeMenos",
    );
  }
  return null;
}

function metodo(vista: VistaPrognosticos): string {
  return t(
    vista.congelado ? "previsao.prognosticos.metodoCongelado" : "previsao.prognosticos.metodo",
    {
      data: formatarDataCurta(new Date(vista.recolhidoEm)),
    },
  );
}

/** As classificações de uma corrida em quadrados, da mais democrata à mais republicana. */
function Faixa({ classificacoes }: { classificacoes: readonly ClassificacaoVista[] }) {
  const ordenadas = [...classificacoes].sort((a, b) => a.posicao - b.posicao);
  const lista = ordenadas.map((c) => `${c.nome}: ${rotuloClassificacao(c)}`).join("; ");
  return (
    <span
      role="img"
      aria-label={t("previsao.prognosticos.faixaAria", { lista })}
      className="mt-1 flex flex-wrap gap-0.5"
    >
      {ordenadas.map((c) => (
        <Amostra key={c.chave} cor={c.cor} />
      ))}
    </span>
  );
}

function nomeCorrida(c: CorridaVista): string {
  if (c.camara === "camara") return c.id;
  const estado = nomeEstado(c.estado);
  return c.especial ? t("previsao.caminho.especial", { estado }) : estado;
}

function LinhaComparacao({ c }: { c: ComparacaoCorrida }) {
  const nota = textoDivergencia(c);
  return (
    <tr className="border-t border-rule-2 align-top">
      <th scope="row" className="py-2 pr-2 text-left font-normal">
        <Link href={caminhoPaginaCorrida(c.corrida.id)} className={`font-semibold ${LIGACAO}`}>
          {nomeCorrida(c.corrida)}
        </Link>
        <Faixa classificacoes={c.classificacoes} />
        {nota ? <span className="mt-1 block text-[12px] text-ink-2">{nota}</span> : null}
      </th>
      <td className="py-2 pl-2 text-right align-top">
        <span className="flex items-center justify-end gap-1.5 text-[13px] whitespace-nowrap">
          <Amostra cor={c.nossa} />
          {t(`previsao.categorias.${c.nossa}`)}
        </span>
        <span className="block font-mono text-[11.5px] text-ink-3">
          {t("previsao.prognosticos.probD", { p: formatarPercentagem(c.corrida.probD, 0) })}
        </span>
      </td>
      <td className="py-2 pl-2 text-right align-top">
        <span className="flex items-center justify-end gap-1.5 text-right text-[13px]">
          <Amostra cor={corDe(c.consenso)} />
          {rotuloPosicao(c.consenso)}
        </span>
      </td>
    </tr>
  );
}

/** Painel das páginas do Senado e da Câmara: onde o Escrutínio e os outros divergem. */
export function PainelPrognosticosCamara({
  vista,
  resumo,
}: {
  vista: VistaPrognosticos;
  resumo: ResumoComparacao;
}) {
  if (resumo.corridas.length === 0) return null;
  // No Senado mostram-se todas as corridas que alguém não dá como sólidas; na Câmara,
  // com mais de cem distritos classificados, só as que divergem.
  const linhas =
    resumo.camara === "senado"
      ? resumo.corridas.filter(
          (c) =>
            c.divergencia !== null ||
            Math.abs(c.nossaPosicao - CENTRO) < 3 ||
            c.classificacoes.some((x) => Math.abs(x.posicao - CENTRO) < 3),
        )
      : [...resumo.corridas]
          .filter((c) => c.divergencia !== null)
          .sort(
            (a, b) => Number(b.divergencia === "favorito") - Number(a.divergencia === "favorito"),
          );
  const nomes = resumo.prognosticadores.map((p) => p.nome).join(", ");
  return (
    <Painel
      sobrelinha={t("previsao.prognosticos.sobrelinha")}
      titulo={t("previsao.prognosticos.titulo")}
      descricao={t(`previsao.prognosticos.texto.${resumo.camara}`, {
        n: resumo.corridas.length,
        iguais: resumo.mesmoFavorito,
        diferentes: resumo.favoritoDiferente,
      })}
      acessorio={
        vista.congelado ? (
          <Selo variante="solido">{t("previsao.prognosticos.congelado")}</Selo>
        ) : null
      }
      fontes={resumo.fontes}
      metodo={metodo(vista)}
    >
      <p className="text-[12.5px] text-ink-2">{t("previsao.prognosticos.quem", { nomes })}</p>
      {linhas.length > 0 ? (
        <table className="w-full border-collapse text-sm">
          <caption className="sr-only">
            {t(`previsao.prognosticos.legenda.${resumo.camara}`)}
          </caption>
          <thead>
            <tr className="rotulo">
              <th scope="col" className="pb-1.5 text-left font-medium">
                {t("previsao.prognosticos.corrida")}
              </th>
              <th scope="col" className="pb-1.5 pl-2 text-right font-medium">
                {t("previsao.prognosticos.escrutinio")}
              </th>
              <th scope="col" className="pb-1.5 pl-2 text-right font-medium">
                {t("previsao.prognosticos.consenso")}
              </th>
            </tr>
          </thead>
          <tbody>
            {linhas.map((c) => (
              <LinhaComparacao key={c.corrida.id} c={c} />
            ))}
          </tbody>
        </table>
      ) : (
        <p className="text-sm text-ink-2">{t("previsao.prognosticos.semDivergencias")}</p>
      )}
    </Painel>
  );
}

/** Painel da página de cada corrida: a classificação de cada prognosticador. */
export function PainelPrognosticosCorrida({
  vista,
  comparacao: c,
}: {
  vista: VistaPrognosticos;
  comparacao: ComparacaoCorrida;
}) {
  const datas = new Map(
    vista[c.corrida.camara].prognosticadores.map((p) => [p.chave, p.data] as const),
  );
  const ordenadas = [...c.classificacoes].sort((a, b) => a.posicao - b.posicao);
  const nota = textoDivergencia(c);
  return (
    <Painel
      sobrelinha={t("previsao.prognosticos.sobrelinha")}
      titulo={t("previsao.prognosticos.tituloCorrida")}
      descricao={t("previsao.prognosticos.textoCorrida", {
        nossa: t(`previsao.categorias.${c.nossa}`),
        consenso: rotuloPosicao(c.consenso),
        n: c.classificacoes.length,
      })}
      acessorio={
        vista.congelado ? (
          <Selo variante="solido">{t("previsao.prognosticos.congelado")}</Selo>
        ) : null
      }
      fontes={vista[c.corrida.camara].fontes}
      metodo={metodo(vista)}
    >
      {nota ? <p className="text-sm font-semibold">{nota}</p> : null}
      <ul className="flex flex-col text-sm">
        <li className="flex items-center gap-2 border-b border-ink-3 py-1.5">
          <span className="min-w-0 flex-1 font-semibold">
            {t("previsao.prognosticos.escrutinio")}
          </span>
          <span className="flex items-center gap-1.5 whitespace-nowrap">
            <Amostra cor={c.nossa} />
            {t(`previsao.categorias.${c.nossa}`)}
          </span>
          <span className="w-[4.5rem] text-right font-mono text-[11.5px] text-ink-3">
            {t("previsao.prognosticos.probD", { p: formatarPercentagem(c.corrida.probD, 0) })}
          </span>
        </li>
        {ordenadas.map((x) => {
          const dia = datas.get(x.chave);
          return (
            <li key={x.chave} className="flex items-center gap-2 border-b border-rule-2 py-1.5">
              <span className="min-w-0 flex-1 [overflow-wrap:anywhere]">{x.nome}</span>
              <span className="flex items-center gap-1.5 whitespace-nowrap">
                <Amostra cor={x.cor} />
                {rotuloClassificacao(x)}
              </span>
              <span className="w-[4.5rem] text-right font-mono text-[11.5px] text-ink-3">
                {dia ? formatarDataCurta(data(dia)) : null}
              </span>
            </li>
          );
        })}
      </ul>
    </Painel>
  );
}
