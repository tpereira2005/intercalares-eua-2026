import { formatarDiaCiclo } from "@/lib/formatacao.ts";

/** Dia do ciclo eleitoral (ex.: "E−21"), sempre na cor do ciclo atual. */
export function CodigoDia({ dias }: { dias: number }) {
  return (
    <span className="rounded-[2px] bg-signal-wash px-1.5 py-1 font-mono text-xs leading-none font-medium tracking-[0.04em] text-signal-ink">
      {formatarDiaCiclo(dias)}
    </span>
  );
}
