import { Painel } from "@/components/ui/Painel.tsx";
import { Selo } from "@/components/ui/Selo.tsx";
import {
  formatarCompacto,
  formatarDecimal,
  formatarHora,
  formatarMargemPontos,
  formatarNumero,
  formatarPercentagem,
} from "@/lib/formatacao.ts";
import { t } from "@/lib/mensagens.ts";
import { corridasComFalta, type VotoQueFalta } from "@/lib/noite/falta.ts";
import type { ModalidadeResultado, VistaResultados } from "@/lib/resultados/vista.ts";
import { nomeCorrida } from "./TabelaResultados.tsx";

/** Corridas mostradas: as primeiras da tabela da noite, as mais renhidas. */
const MAXIMO = 8;

/** Tom de cada modalidade na barra; a tabela por baixo dá os valores. */
type Parte = ModalidadeResultado | "semModo";

const TOM: Record<Parte, string> = {
  correio: "bg-ink/85",
  antecipado_presencial: "bg-ink/60",
  dia_eleicao: "bg-ink/40",
  provisorio: "bg-ink/25",
  outro: "bg-ink/15",
  semModo: "bg-ink-3/50",
};

function Barra({ v }: { v: VotoQueFalta }) {
  const partes = [
    ...v.modos.map((m) => ({ chave: m.modo, fracao: m.fracao })),
    ...(v.semModo > 0 ? [{ chave: "semModo" as const, fracao: v.semModo / v.esperados }] : []),
  ];
  return (
    <div aria-hidden="true" className="flex h-3.5 w-full overflow-hidden rounded-[2px]">
      {partes.map((p) => (
        <span
          key={p.chave}
          className={`h-full border-r border-sheet ${TOM[p.chave]}`}
          style={{ width: `${(p.fracao * 100).toFixed(2)}%` }}
        />
      ))}
      <span className="fundo-falta h-full flex-1 border border-dashed border-ink-3" />
    </div>
  );
}

/** Margem projetada com o intervalo de 80% e a margem contada, num eixo R ← 0 → D. */
function Intervalo({ v }: { v: VotoQueFalta }) {
  const valores = [v.margemP10, v.margemP90, v.margemContada ?? 0].map(Math.abs);
  const extremo = Math.max(5, Math.ceil(Math.max(...valores) / 5) * 5);
  const x = (m: number) =>
    `${(((Math.max(-extremo, Math.min(extremo, m)) + extremo) / (2 * extremo)) * 100).toFixed(2)}%`;
  return (
    <div className="flex items-center gap-2 font-mono text-[10.5px] text-ink-3">
      <span aria-hidden="true">{formatarMargemPontos(-extremo, 0)}</span>
      <div
        role="img"
        aria-label={t("noite.falta.intervalo", {
          margem: formatarMargemPontos(v.margem),
          de: formatarMargemPontos(v.margemP10),
          ate: formatarMargemPontos(v.margemP90),
          contada:
            v.margemContada === null
              ? t("noite.falta.semContada")
              : formatarMargemPontos(v.margemContada),
        })}
        className="relative h-4 min-w-0 flex-1"
      >
        <span className="absolute top-1/2 h-px w-full bg-rule" />
        <span className="absolute top-0 left-1/2 h-full w-px bg-ink-3" />
        <span
          className="absolute top-[3px] h-2.5 rounded-[2px] bg-ink-3/35"
          style={{ left: x(v.margemP10), width: `calc(${x(v.margemP90)} - ${x(v.margemP10)})` }}
        />
        {v.margemContada === null ? null : (
          <span
            className="absolute top-1/2 size-2.5 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 border-ink-2 bg-sheet"
            style={{ left: x(v.margemContada) }}
          />
        )}
        <span
          className="absolute top-0 h-full w-[3px] -translate-x-1/2 rounded-[1px] bg-ink"
          style={{ left: x(v.margem) }}
        />
      </div>
      <span aria-hidden="true">{formatarMargemPontos(extremo, 0)}</span>
    </div>
  );
}

/** Pontos do desenho: x de 0 a 100 pelo tempo, y de 0 a 40 pela margem (D em cima). */
function caminho(pontos: readonly { x: number; y: number }[]): string {
  return pontos.map((p, i) => `${i === 0 ? "M" : "L"}${p.x.toFixed(2)},${p.y.toFixed(2)}`).join("");
}

/**
 * Margem projetada e intervalo de 80% em cada projeção guardada da noite: a faixa
 * encolhe à medida que se contam votos. Só aparece com dois pontos ou mais.
 */
function EvolucaoIntervalo({ v }: { v: VotoQueFalta }) {
  const pontos = v.evolucao;
  const primeiro = pontos[0];
  const ultimo = pontos.at(-1);
  if (!primeiro || !ultimo || pontos.length < 2) return null;
  const inicio = Date.parse(primeiro.instante);
  const duracao = Math.max(1, Date.parse(ultimo.instante) - inicio);
  const extremo = Math.max(
    5,
    Math.ceil(Math.max(...pontos.flatMap((p) => [Math.abs(p.p10), Math.abs(p.p90)])) / 5) * 5,
  );
  const x = (instante: string) => ((Date.parse(instante) - inicio) / duracao) * 100;
  const y = (m: number) => 20 - (Math.max(-extremo, Math.min(extremo, m)) / extremo) * 20;
  const cima = pontos.map((p) => ({ x: x(p.instante), y: y(p.p90) }));
  const baixo = pontos.map((p) => ({ x: x(p.instante), y: y(p.p10) })).reverse();
  const largura = (p: (typeof pontos)[number]) => formatarDecimal(p.p90 - p.p10, 1);
  return (
    <figure className="flex flex-col gap-1">
      <div className="flex items-stretch gap-2 font-mono text-[10.5px] text-ink-3">
        <span aria-hidden="true" className="flex flex-col justify-between py-px">
          <span>{formatarMargemPontos(extremo, 0)}</span>
          <span>{formatarMargemPontos(-extremo, 0)}</span>
        </span>
        <svg
          role="img"
          aria-label={t("noite.falta.evolucao", {
            n: pontos.length,
            de: largura(primeiro),
            ate: largura(ultimo),
            inicio: formatarHora(new Date(primeiro.instante)),
            fim: formatarHora(new Date(ultimo.instante)),
          })}
          viewBox="0 0 100 40"
          preserveAspectRatio="none"
          className="h-16 min-w-0 flex-1 overflow-visible"
        >
          <path d={`${caminho([...cima, ...baixo])}Z`} className="fill-ink-3/35" />
          <line
            x1="0"
            x2="100"
            y1="20"
            y2="20"
            vectorEffect="non-scaling-stroke"
            strokeDasharray="2 3"
            className="stroke-ink-3"
          />
          <path
            d={caminho(pontos.map((p) => ({ x: x(p.instante), y: y(p.margem) })))}
            vectorEffect="non-scaling-stroke"
            strokeWidth="2"
            fill="none"
            className="stroke-ink"
          />
        </svg>
      </div>
      <figcaption className="flex justify-between gap-2 font-mono text-[10.5px] text-ink-3">
        <span>{formatarHora(new Date(primeiro.instante))}</span>
        <span>{t("noite.falta.evolucaoLegenda")}</span>
        <span>{formatarHora(new Date(ultimo.instante))}</span>
      </figcaption>
    </figure>
  );
}

function Leitura({ v }: { v: VotoQueFalta }) {
  if (v.lider === null) return <>{t("noite.falta.empate")}</>;
  const atras = v.lider === "D" ? "R" : "D";
  if (v.precisa === null) return null;
  if (v.precisa > 100) return <>{t(`noite.falta.inalcancavel.${atras}`)}</>;
  return (
    <>
      {t(`noite.falta.precisa.${atras}`, {
        pontos: v.precisa.toLocaleString("pt-PT", {
          minimumFractionDigits: 1,
          maximumFractionDigits: 1,
        }),
      })}
    </>
  );
}

function Corrida({ v }: { v: VotoQueFalta }) {
  const nome = nomeCorrida(v.linha);
  return (
    <li className="flex min-w-0 flex-col gap-2 border-t border-rule-2 pt-3">
      <div className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-0.5">
        <h3 className="text-[15px] font-semibold">{nome}</h3>
        <p className="font-mono text-[12px] text-ink-2">
          {t("noite.falta.contado", {
            pct: formatarPercentagem(v.fracaoContada, 0),
            falta: formatarCompacto(v.falta),
          })}
        </p>
      </div>
      <Barra v={v} />
      {v.modos.length > 0 || v.semModo > 0 ? (
        <table className="w-full border-collapse text-[12.5px]">
          <caption className="sr-only">{t("noite.falta.legendaModos", { corrida: nome })}</caption>
          <thead className="sr-only">
            <tr>
              <th scope="col">{t("noite.falta.colunas.modo")}</th>
              <th scope="col">{t("noite.falta.colunas.votos")}</th>
              <th scope="col">{t("noite.falta.colunas.parte")}</th>
              <th scope="col">{t("noite.falta.colunas.margem")}</th>
            </tr>
          </thead>
          <tbody>
            {[
              ...v.modos.map((m) => ({ chave: m.modo, votos: m.votos, margem: m.margem })),
              ...(v.semModo > 0
                ? [{ chave: "semModo" as const, votos: v.semModo, margem: null }]
                : []),
            ].map((m) => (
              <tr key={m.chave}>
                <th scope="row" className="py-0.5 pr-2 text-left font-normal text-ink-2">
                  <span
                    aria-hidden="true"
                    className={`mr-1.5 inline-block size-2.5 rounded-[1px] align-[-1px] ${TOM[m.chave]}`}
                  />
                  {t(`noite.falta.modos.${m.chave}`)}
                </th>
                <td className="py-0.5 pr-2 text-right font-mono">{formatarNumero(m.votos)}</td>
                <td className="py-0.5 pr-2 text-right font-mono text-ink-3">
                  {formatarPercentagem(m.votos / v.esperados, 0)}
                </td>
                <td className="py-0.5 text-right font-mono">
                  {m.margem === null ? "—" : formatarMargemPontos(m.margem)}
                </td>
              </tr>
            ))}
            <tr>
              <th scope="row" className="py-0.5 pr-2 text-left font-normal text-ink-2">
                <span
                  aria-hidden="true"
                  className="fundo-falta mr-1.5 inline-block size-2.5 rounded-[1px] border border-dashed border-ink-3 align-[-1px]"
                />
                {t("noite.falta.modos.falta")}
              </th>
              <td className="py-0.5 pr-2 text-right font-mono">
                {formatarNumero(Math.round(v.falta))}
              </td>
              <td className="py-0.5 pr-2 text-right font-mono text-ink-3">
                {formatarPercentagem(v.falta / v.esperados, 0)}
              </td>
              <td className="py-0.5 text-right font-mono text-ink-3">?</td>
            </tr>
          </tbody>
        </table>
      ) : (
        <p className="text-[12.5px] text-ink-3">{t("noite.falta.semModos")}</p>
      )}
      <Intervalo v={v} />
      <EvolucaoIntervalo v={v} />
      <p className="text-[13px] text-ink-2">
        <Leitura v={v} />
      </p>
    </li>
  );
}

/** Voto contado por modalidade e voto que falta nas corridas em aberto com contagem. */
export function PainelFalta({ vista }: { vista: VistaResultados }) {
  const todas = corridasComFalta(vista.aoVivo);
  if (todas.length === 0) return null;
  const mostradas = todas.slice(0, MAXIMO);
  return (
    <Painel
      sobrelinha={t("noite.falta.sobrelinha")}
      titulo={t("noite.falta.titulo")}
      descricao={
        todas.length > MAXIMO
          ? `${t("noite.falta.texto")} ${t("noite.falta.mais", { n: MAXIMO, total: todas.length })}`
          : t("noite.falta.texto")
      }
      acessorio={<Selo variante="tracejado">{t("comum.selos.estimativa")}</Selo>}
      fontes={vista.fontes}
      metodo={t("noite.falta.metodo")}
    >
      <p className="font-mono text-[11px] text-ink-3">{t("noite.falta.leituraGrafico")}</p>
      <ul className="grid gap-x-6 gap-y-3 min-[860px]:grid-cols-2">
        {mostradas.map((v) => (
          <Corrida key={v.linha.id} v={v} />
        ))}
      </ul>
    </Painel>
  );
}
