"use client";

import type { Fase } from "@/lib/fases.ts";
import { t } from "@/lib/mensagens.ts";
import { useFase } from "@/lib/use-fase.ts";

const FASES: readonly Fase[] = ["antes", "noite", "depois"];

/** Mostra em que fase do ciclo está o painel principal; a fase depende da data. */
export function IndicadorFase({ faseBuild }: { faseBuild: Fase }) {
  const fase = useFase(faseBuild);
  return (
    <div className="flex flex-wrap items-center gap-2">
      <span className="rotulo">{t("cabecalho.fase")}</span>
      <ol
        aria-label={t("cabecalho.faseAtualAria")}
        className="inline-flex flex-wrap gap-0.5 rounded-sm bg-rule-2 p-0.5"
      >
        {FASES.map((opcao) => {
          const atual = opcao === fase;
          return (
            <li
              key={opcao}
              aria-current={atual ? "true" : undefined}
              className={`inline-flex items-center gap-[7px] rounded-[2px] px-2.5 py-1.5 text-[13px] leading-[1.1] font-medium whitespace-nowrap ${
                atual ? "bg-sheet text-ink shadow-[0_0_0_1px_var(--rule)]" : "text-ink-2"
              }`}
            >
              <span className="oval" aria-hidden="true" />
              {t(`cabecalho.fases.${opcao}`)}
            </li>
          );
        })}
      </ol>
    </div>
  );
}
