"use client";

import Link from "next/link";
import type { ReactNode } from "react";
import { DestaqueNoite } from "@/components/inicio/DestaqueNoite.tsx";
import { EstadoLigacao } from "@/components/resultados/ResultadosAoVivo.tsx";
import { Chamada, TabelaResultados } from "@/components/resultados/TabelaResultados.tsx";
import { Painel } from "@/components/ui/Painel.tsx";
import { Selo } from "@/components/ui/Selo.tsx";
import { useAoVivo } from "@/lib/ao-vivo/use-ao-vivo.ts";
import { formatarDecimal, formatarPercentagem } from "@/lib/formatacao.ts";
import { avaliarPrevisao } from "@/lib/inicio/avaliacao.ts";
import { t } from "@/lib/mensagens.ts";
import type { DadosNoiteEleitoral } from "@/lib/resultados/carregar.ts";
import type { PrevisaoResultados, VistaResultados } from "@/lib/resultados/vista.ts";

const LIGACAO = "text-ink underline decoration-rule underline-offset-[3px] hover:decoration-ink-3";
/** Corridas com contagem mostradas no início; as outras ficam na página da noite. */
const CORRIDAS = 6;
const CHAMADAS = 6;

function Corridas({ vista }: { vista: VistaResultados }) {
  return (
    <Painel
      sobrelinha={t("inicio.aoVivo.corridasSobrelinha")}
      titulo={t("inicio.aoVivo.corridasTitulo")}
      descricao={t("inicio.aoVivo.corridasTexto")}
      acessorio={<Selo variante="solido">{t("comum.selos.oficial")}</Selo>}
      fontes={vista.fontes}
      metodo={t("resultados.aoVivo.metodo")}
    >
      {vista.aoVivo.length > 0 ? (
        <TabelaResultados
          linhas={vista.aoVivo.slice(0, CORRIDAS)}
          legenda={t("inicio.aoVivo.corridasTitulo")}
          comContagem
        />
      ) : (
        <p className="text-ink-2">{t("resultados.aoVivo.vazio")}</p>
      )}
      <p className="text-sm">
        <Link href="/resultados/" className={LIGACAO}>
          {t("inicio.aoVivo.todas")}
        </Link>
      </p>
    </Painel>
  );
}

function Chamadas({ vista }: { vista: VistaResultados }) {
  const lado = (l: "D" | "R") => vista.chamadas.filter((c) => c.vencedor === l).length;
  return (
    <Painel
      sobrelinha={t("inicio.aoVivo.chamadasSobrelinha")}
      titulo={t("resultados.chamadas.titulo")}
      descricao={t("resultados.chamadas.nota")}
    >
      {vista.chamadas.length === 0 ? (
        <p className="text-ink-2">{t("resultados.chamadas.nenhuma")}</p>
      ) : (
        <>
          <p className="text-ink-2">
            {t("resultados.chamadas.resumo", {
              n: vista.chamadas.length,
              d: lado("D"),
              r: lado("R"),
            })}
          </p>
          <ul className="flex flex-col gap-1.5 text-sm">
            {vista.chamadas.slice(0, CHAMADAS).map((c) => (
              <li key={c.corrida}>
                <span className="font-semibold">{c.corrida}</span>
                <Chamada c={c} />
              </li>
            ))}
          </ul>
        </>
      )}
    </Painel>
  );
}

function Avaliacao({
  vista,
  probD,
}: {
  vista: VistaResultados;
  probD: Readonly<Record<string, number>>;
}) {
  const a = avaliarPrevisao(vista.chamadas, probD);
  return (
    <Painel
      sobrelinha={t("inicio.avaliacao.sobrelinha")}
      titulo={t("inicio.avaliacao.titulo")}
      descricao={t("inicio.avaliacao.texto")}
      fontes={[
        { nome: t("inicio.avaliacao.fonteChamadas") },
        { nome: t("inicio.previsao.fonte"), url: "/previsao/" },
      ]}
      metodo={t("inicio.avaliacao.metodo")}
    >
      {a.avaliadas === 0 ? (
        <p className="text-ink-2">{t("inicio.avaliacao.vazia")}</p>
      ) : (
        <>
          <dl className="grid grid-cols-2 gap-4">
            <div className="flex flex-col gap-1">
              <dt className="rotulo">{t("inicio.avaliacao.acertos")}</dt>
              <dd className="font-display text-[28px] leading-none font-bold">
                {t("inicio.avaliacao.acertosValor", { acertos: a.acertos, n: a.avaliadas })}
              </dd>
            </div>
            {a.brier === null ? null : (
              <div className="flex flex-col gap-1">
                <dt className="rotulo">{t("inicio.avaliacao.brier")}</dt>
                <dd className="font-display text-[28px] leading-none font-bold">
                  {formatarDecimal(a.brier, 3)}
                </dd>
              </div>
            )}
          </dl>
          <p className="text-sm">
            <Link href="/previsao/avaliacao/" prefetch={false} className={LIGACAO}>
              {t("previsao.avaliacao.ligacao")}
            </Link>
          </p>
          {a.surpresas.length === 0 ? (
            <p className="text-sm text-ink-2">{t("inicio.avaliacao.semSurpresas")}</p>
          ) : (
            <ul className="flex flex-col gap-1 text-sm">
              {a.surpresas.map((s) => (
                <li key={s.corrida}>
                  {t(`inicio.avaliacao.surpresa.${s.vencedor}`, {
                    corrida: s.corrida,
                    prob: formatarPercentagem(s.probVencedor, 0),
                  })}
                </li>
              ))}
            </ul>
          )}
        </>
      )}
    </Painel>
  );
}

/**
 * Topo da página inicial na noite e nos dias da contagem: a projeção, as corridas mais
 * renhidas com contagem e as chamadas das redações (ou, depois da noite, a avaliação da
 * previsão congelada). Atualiza-se com a API do Worker, como a página da noite.
 */
export function InicioAoVivo({
  inicial,
  previsao,
  probD,
  depois,
  emPreparacao,
}: {
  inicial: DadosNoiteEleitoral | null;
  previsao: PrevisaoResultados | null;
  /** Probabilidade democrata de cada corrida na previsão, para a avaliação. */
  probD: Readonly<Record<string, number>>;
  depois: boolean;
  /** O que se mostra enquanto não houver contagem nem projeção. */
  emPreparacao: ReactNode;
}) {
  const { dados, ligacao } = useAoVivo(inicial, previsao);
  const resultados = dados?.resultados ?? null;
  const noite = dados?.noite ?? null;
  // Um ensaio nunca aparece no início: só a noite de 2026.
  const real = resultados && !resultados.ensaio ? resultados : null;
  if (!real && (!noite || noite.ensaio)) return emPreparacao;
  const instante = real?.instante ?? noite?.instante ?? null;
  return (
    <div className="flex flex-col gap-4">
      {noite && !noite.ensaio ? (
        <DestaqueNoite
          noite={noite}
          depois={depois}
          ligacao={<EstadoLigacao ligacao={ligacao} instante={instante} />}
        />
      ) : (
        <p className="text-[12px] text-ink-3">
          <EstadoLigacao ligacao={ligacao} instante={instante} />
        </p>
      )}
      {real ? (
        <div className="grid gap-4 min-[860px]:grid-cols-[minmax(0,1.4fr)_minmax(0,1fr)]">
          <Corridas vista={real} />
          {depois ? <Avaliacao vista={real} probD={probD} /> : <Chamadas vista={real} />}
        </div>
      ) : null}
    </div>
  );
}
