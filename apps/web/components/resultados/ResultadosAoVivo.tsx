"use client";

import { useEffect, useState, type ReactNode } from "react";
import {
  atualizarEstado,
  consultarNoite,
  consultarResultados,
  INTERVALO_MS,
  INTERVALO_SEM_DADOS_MS,
  type EstadoAoVivo,
  type Ligacao,
} from "@/lib/ao-vivo/estado.ts";
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

function EstadoLigacao({ ligacao, instante }: { ligacao: Ligacao; instante: string | null }) {
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
  const [estado, setEstado] = useState<EstadoAoVivo>({
    dados: inicial,
    parciais: null,
    ligacao: { tipo: "build" },
  });

  useEffect(() => {
    let temporizador: ReturnType<typeof setTimeout> | undefined;
    let ultima = 0;
    let ativo = true;

    async function consultar() {
      clearTimeout(temporizador);
      ultima = Date.now();
      const [resultados, noite] = await Promise.all([consultarResultados(), consultarNoite()]);
      if (!ativo) return;
      setEstado((atual) => atualizarEstado(atual, resultados, noite, previsao));
      const semDados = resultados.tipo === "ausente" && noite.tipo === "ausente";
      agendar(semDados ? INTERVALO_SEM_DADOS_MS : INTERVALO_MS);
    }

    function agendar(espera: number) {
      clearTimeout(temporizador);
      if (document.visibilityState === "visible") {
        temporizador = setTimeout(() => void consultar(), espera);
      }
    }

    /** Separador escondido: não se consulta. Ao voltar, consulta já se passou o intervalo. */
    function aoMudarVisibilidade() {
      if (document.visibilityState !== "visible") {
        clearTimeout(temporizador);
        return;
      }
      const passou = Date.now() - ultima;
      if (passou >= INTERVALO_MS) void consultar();
      else agendar(INTERVALO_MS - passou);
    }

    if (document.visibilityState === "visible") void consultar();
    document.addEventListener("visibilitychange", aoMudarVisibilidade);
    return () => {
      ativo = false;
      clearTimeout(temporizador);
      document.removeEventListener("visibilitychange", aoMudarVisibilidade);
    };
  }, [previsao]);

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
