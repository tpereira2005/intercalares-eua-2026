"use client";

import { useEffect, useState } from "react";
import { faseEm, type Fase } from "./fases.ts";

/** Verifica a fase a cada minuto: a página pode ficar aberta da tarde até à madrugada. */
const PASSO = 60_000;

/**
 * Fase do ciclo no browser (o nome segue a regra dos hooks do React). O HTML traz a fase
 * do momento do build; depois de montar, passa a ser a do relógio, para o site mudar às
 * 23h00 UTC de 3 de novembro sem esperar por um novo build.
 */
export function useFase(faseBuild: Fase): Fase {
  const [fase, setFase] = useState<Fase>(faseBuild);
  useEffect(() => {
    const atualizar = () => {
      setFase(faseEm(new Date()));
    };
    atualizar();
    const temporizador = setInterval(atualizar, PASSO);
    return () => {
      clearInterval(temporizador);
    };
  }, []);
  return fase;
}
