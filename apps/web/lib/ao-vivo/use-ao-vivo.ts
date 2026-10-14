"use client";

import { useEffect, useState } from "react";
import type { DadosNoiteEleitoral } from "../resultados/carregar.ts";
import type { PrevisaoResultados } from "../resultados/vista.ts";
import {
  atualizarEstado,
  consultarNoite,
  consultarResultados,
  INTERVALO_MS,
  INTERVALO_SEM_DADOS_MS,
  type EstadoAoVivo,
} from "./estado.ts";

/**
 * Hook da noite (o nome segue a regra do React). Consulta a API do Worker a cada minuto enquanto o separador está visível e mantém o
 * que está no ecrã quando a API falha. `ativo` falso não consulta (antes da noite).
 */
export function useAoVivo(
  inicial: DadosNoiteEleitoral | null,
  previsao: PrevisaoResultados | null,
  ativo = true,
): EstadoAoVivo {
  const [estado, setEstado] = useState<EstadoAoVivo>({
    dados: inicial,
    parciais: null,
    chamadas: null,
    ligacao: { tipo: "build" },
  });

  useEffect(() => {
    if (!ativo) return;
    let temporizador: ReturnType<typeof setTimeout> | undefined;
    let ultima = 0;
    let montado = true;

    async function consultar() {
      clearTimeout(temporizador);
      ultima = Date.now();
      const [resultados, noite] = await Promise.all([consultarResultados(), consultarNoite()]);
      if (!montado) return;
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
      montado = false;
      clearTimeout(temporizador);
      document.removeEventListener("visibilitychange", aoMudarVisibilidade);
    };
  }, [previsao, ativo]);

  return estado;
}
