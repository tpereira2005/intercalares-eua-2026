"use client";

import { useEffect, useState } from "react";
import type { DadosNoiteEleitoral } from "../resultados/carregar.ts";
import type { PrevisaoResultados } from "../resultados/vista.ts";
import {
  atualizarEstado,
  consultaFalhou,
  consultarAoVivo,
  INTERVALO_MS,
  INTERVALO_SEM_DADOS_MS,
  proximaEspera,
  type EstadoAoVivo,
} from "./estado.ts";

/**
 * Hook da noite (o nome segue a regra do React). Consulta a API do Worker (um só pedido por vez) ao ritmo que ela sugerir, 60 s por omissão, enquanto o separador está visível; recua se falhar e mantém o
 * que está no ecrã. `ativo` falso não consulta (antes da noite).
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
    /** Espera calculada depois da última consulta; usada ao voltar ao separador. */
    let espera = INTERVALO_MS;
    let falhasSeguidas = 0;
    let montado = true;

    async function consultar() {
      clearTimeout(temporizador);
      ultima = Date.now();
      const { resultados, noite, intervaloMs } = await consultarAoVivo();
      if (!montado) return;
      setEstado((atual) => atualizarEstado(atual, resultados, noite, previsao));
      falhasSeguidas = consultaFalhou(resultados, noite) ? falhasSeguidas + 1 : 0;
      const semDados = resultados.tipo === "ausente" && noite.tipo === "ausente";
      espera = proximaEspera({
        base: semDados ? INTERVALO_SEM_DADOS_MS : (intervaloMs ?? INTERVALO_MS),
        falhasSeguidas,
        aleatorio: Math.random(),
      });
      agendar(espera);
    }

    function agendar(depoisDe: number) {
      clearTimeout(temporizador);
      if (document.visibilityState === "visible") {
        temporizador = setTimeout(() => void consultar(), depoisDe);
      }
    }

    /** Separador escondido: não se consulta. Ao voltar, consulta já se passou a espera. */
    function aoMudarVisibilidade() {
      if (document.visibilityState !== "visible") {
        clearTimeout(temporizador);
        return;
      }
      const passou = Date.now() - ultima;
      if (passou >= espera) void consultar();
      else agendar(espera - passou);
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
