"use client";

import { useSyncExternalStore } from "react";
import { nomeEstado } from "@/lib/estados.ts";
import { proximoFecho, type GrupoFecho } from "@/lib/fecho.ts";
import { formatarDuracao, formatarHora } from "@/lib/formatacao.ts";
import { t } from "@/lib/mensagens.ts";

const PASSO = 30_000;

function subscrever(aviso: () => void): () => void {
  const id = setInterval(aviso, PASSO);
  return () => {
    clearInterval(id);
  };
}

/** Hora atual arredondada a 30 segundos: o mesmo valor entre leituras seguidas. */
function relogio(): number {
  return Math.floor(Date.now() / PASSO) * PASSO;
}

function semRelogio(): number | null {
  return null;
}

/**
 * Contagem decrescente até ao próximo fecho de urnas. Calcula-se no browser (o site é
 * estático); até lá, o espaço fica reservado com a mesma altura, sem deslocar a página.
 */
export function ContagemFecho({ grupos }: { grupos: readonly GrupoFecho[] }) {
  const instante = useSyncExternalStore(subscrever, relogio, semRelogio);
  const agora = instante === null ? null : new Date(instante);
  const proximo = agora ? proximoFecho(agora, grupos) : null;
  return (
    <p className="min-h-[3.2em] text-[15px]" aria-live="off">
      {agora === null ? (
        <span className="text-ink-3">{t("fecho.aCalcular")}</span>
      ) : proximo === null ? (
        t("fecho.todasFechadas")
      ) : (
        <>
          <span className="font-display text-[26px] leading-none font-bold">
            {formatarDuracao(Date.parse(proximo.instante) - agora.getTime())}
          </span>{" "}
          <span className="text-ink-2">
            {t("fecho.proximo", {
              hora: formatarHora(new Date(proximo.instante), "Europe/Lisbon"),
              estados: proximo.estados.map((f) => nomeEstado(f.estado)).join(", "),
            })}
          </span>
        </>
      )}
    </p>
  );
}
