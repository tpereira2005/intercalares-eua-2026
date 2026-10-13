"use client";

import { useSyncExternalStore } from "react";
import { ControloSegmentado } from "@/components/ui/ControloSegmentado.tsx";
import { t } from "@/lib/mensagens.ts";
import { escolherTema, lerTema, subscreverTema, TEMAS, type Tema } from "@/lib/tema.ts";

const OPCOES = TEMAS.map((tema) => ({ valor: tema, rotulo: t(`cabecalho.temas.${tema}`) }));

function lerTemaAtual(): Tema {
  return lerTema(window.localStorage);
}

function temaNoServidor(): Tema {
  return "sistema";
}

export function SeletorTema() {
  const tema = useSyncExternalStore(subscreverTema, lerTemaAtual, temaNoServidor);
  return (
    <div className="flex flex-wrap items-center gap-2">
      <span className="rotulo">{t("cabecalho.tema")}</span>
      <ControloSegmentado
        rotuloGrupo={t("cabecalho.temaAria")}
        opcoes={OPCOES}
        valor={tema}
        aoMudar={escolherTema}
      />
    </div>
  );
}
