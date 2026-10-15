"use client";

import Link from "next/link";
import { CorridaFalta } from "@/components/resultados/PainelFalta.tsx";
import { EstadoLigacao } from "@/components/resultados/ResultadosAoVivo.tsx";
import { TabelaResultados } from "@/components/resultados/TabelaResultados.tsx";
import { Painel } from "@/components/ui/Painel.tsx";
import { Selo } from "@/components/ui/Selo.tsx";
import { useAoVivo } from "@/lib/ao-vivo/use-ao-vivo.ts";
import type { Fase } from "@/lib/fases.ts";
import { t } from "@/lib/mensagens.ts";
import { votoQueFalta } from "@/lib/noite/falta.ts";
import type { PrevisaoResultados } from "@/lib/resultados/vista.ts";
import { useFase } from "@/lib/use-fase.ts";

const LIGACAO = "text-ink underline decoration-rule underline-offset-[3px] hover:decoration-ink-3";

function Noite({ id, previsao }: { id: string; previsao: PrevisaoResultados }) {
  const { dados, ligacao } = useAoVivo(null, previsao);
  const vista = dados?.resultados ?? null;
  // Um ensaio nunca aparece na página da corrida: só a noite de 2026.
  const linha = vista && !vista.ensaio ? vista.aoVivo.find((l) => l.id === id) : undefined;
  const falta = linha ? votoQueFalta(linha) : null;
  return (
    <Painel
      sobrelinha={t("corrida.aoVivo.sobrelinha")}
      titulo={t("corrida.aoVivo.titulo")}
      descricao={t("corrida.aoVivo.texto")}
      acessorio={<Selo variante="sinal">{t("comum.selos.aoVivo")}</Selo>}
      {...(vista ? { fontes: vista.fontes } : {})}
      metodo={t("noite.falta.metodo")}
    >
      <p className="text-[12px] text-ink-3">
        <EstadoLigacao ligacao={ligacao} instante={vista?.instante ?? null} />
      </p>
      {falta ? (
        <ul className="flex flex-col">
          <CorridaFalta v={falta} />
        </ul>
      ) : linha ? (
        <TabelaResultados linhas={[linha]} legenda={t("corrida.aoVivo.titulo")} comContagem />
      ) : (
        <p className="text-ink-2">{t("corrida.aoVivo.semContagem")}</p>
      )}
      <p className="text-sm">
        <Link href="/resultados/" className={LIGACAO}>
          {t("corrida.aoVivo.ligacao")}
        </Link>
      </p>
    </Painel>
  );
}

/**
 * Contagem e projeção desta corrida na noite e nos dias seguintes, com o intervalo a
 * encolher à medida que os votos chegam. Antes da noite não aparece nem consulta a API.
 */
export function CorridaAoVivo({
  id,
  previsao,
  faseBuild,
}: {
  id: string;
  /** A previsão reduzida a esta corrida: chega para a vista e mantém a página leve. */
  previsao: PrevisaoResultados;
  faseBuild: Fase;
}) {
  const fase = useFase(faseBuild);
  return fase === "antes" ? null : <Noite id={id} previsao={previsao} />;
}
