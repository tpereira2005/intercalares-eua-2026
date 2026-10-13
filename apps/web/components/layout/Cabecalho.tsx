import Link from "next/link";
import { faseEm } from "@/lib/fases.ts";
import { t } from "@/lib/mensagens.ts";
import { IndicadorFase } from "./IndicadorFase.tsx";
import { SeletorTema } from "./SeletorTema.tsx";

export function Cabecalho() {
  // Calculada no build; o site é reconstruído a cada atualização de dados.
  const fase = faseEm(new Date());
  return (
    <header className="border-b border-rule bg-sheet">
      <div className="contentor flex flex-wrap items-center gap-x-[22px] gap-y-3.5 py-3">
        <Link href="/" className="mr-auto flex items-center gap-2.5 no-underline">
          <span
            aria-hidden="true"
            className="relative h-4 w-[26px] flex-none rounded-[50%] border-2 border-ink after:absolute after:inset-0.5 after:rounded-[50%] after:bg-signal after:content-['']"
          />
          <span className="font-display text-[26px] leading-none font-extrabold tracking-[0.04em] uppercase">
            {t("site.nome")}
          </span>
          <span className="border-l border-rule pl-2.5 font-mono text-[11px] leading-tight font-medium tracking-[0.06em] text-ink-3 uppercase">
            {t("site.subtitulo")}
          </span>
        </Link>
        <IndicadorFase fase={fase} />
        <SeletorTema />
      </div>
      <div className="marcas-sincronizacao" aria-hidden="true" />
    </header>
  );
}
