"use client";

import type { ReactNode } from "react";
import type { Ligacao } from "@/lib/ao-vivo/estado.ts";
import { useAoVivo } from "@/lib/ao-vivo/use-ao-vivo.ts";
import { formatarHora } from "@/lib/formatacao.ts";
import { t } from "@/lib/mensagens.ts";
import type { DadosNoiteEleitoral } from "@/lib/resultados/carregar.ts";
import type { PrevisaoResultados } from "@/lib/resultados/vista.ts";
import { PaginaResultados } from "./PaginaResultados.tsx";

interface Propriedades {
  /** Vistas calculadas no build; `null` quando o build não tinha dados da noite. */
  inicial: DadosNoiteEleitoral | null;
  previsao: PrevisaoResultados | null;
  /** O que se mostra enquanto não houver dados nenhuns. */
  emPreparacao: ReactNode;
}

function hora(instante: string): string {
  return formatarHora(new Date(instante));
}

export function EstadoLigacao({
  ligacao,
  instante,
}: {
  ligacao: Ligacao;
  instante: string | null;
}) {
  let texto: string;
  if (ligacao.tipo === "aoVivo" && ligacao.espelho) {
    texto = t("resultados.aoVivoApi.espelho", { hora: hora(ligacao.confirmadoEm) });
  } else if (ligacao.tipo === "aoVivo") {
    texto = t(ligacao.antiga ? "resultados.aoVivoApi.antiga" : "resultados.aoVivoApi.ativa", {
      hora: hora(ligacao.confirmadoEm),
    });
  } else if (ligacao.tipo === "falha") {
    texto = instante
      ? t("resultados.aoVivoApi.falha", { hora: hora(instante) })
      : t("resultados.aoVivoApi.falhaSemDados");
  } else {
    texto = t(
      ligacao.tipo === "semDados"
        ? "resultados.aoVivoApi.semDados"
        : "resultados.aoVivoApi.aProcurar",
    );
  }
  return <span className="max-w-[40ch] text-[12px] text-ink-3 sm:text-right">{texto}</span>;
}

/**
 * Página da noite com atualização automática: consulta a API do Worker a cada minuto
 * enquanto o separador está visível e mantém o que está no ecrã quando a API falha.
 */
export function ResultadosAoVivo({ inicial, previsao, emPreparacao }: Propriedades) {
  const estado = useAoVivo(inicial, previsao);
  const { dados, ligacao } = estado;
  if (!dados || (!dados.resultados && !dados.noite)) return emPreparacao;
  const instante = dados.resultados?.instante ?? dados.noite?.instante ?? null;
  return (
    <PaginaResultados
      resultados={dados.resultados}
      noite={dados.noite}
      ligacao={<EstadoLigacao ligacao={ligacao} instante={instante} />}
    />
  );
}
