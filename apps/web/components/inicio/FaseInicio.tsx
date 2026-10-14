"use client";

import type { ReactNode } from "react";
import type { Fase } from "@/lib/fases.ts";
import { useFase } from "@/lib/use-fase.ts";

/** Topo da página inicial em cada fase: antes, noite e depois (plano, secção 9.4). */
export function FaseInicio({
  faseBuild,
  ...topos
}: {
  faseBuild: Fase;
} & Record<Fase, ReactNode>) {
  return <>{topos[useFase(faseBuild)]}</>;
}
