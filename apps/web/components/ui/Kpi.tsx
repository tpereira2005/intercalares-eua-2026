import type { ReactNode } from "react";

/** Faixa de indicadores-chave numa única caixa, com divisórias. */
export function FaixaKpis({ children }: { children: ReactNode }) {
  return (
    <dl className="grid grid-cols-[repeat(auto-fit,minmax(min(100%,210px),1fr))] rounded-md border border-rule bg-sheet">
      {children}
    </dl>
  );
}

export function Kpi({
  rotulo,
  valor,
  detalhe,
}: {
  rotulo: string;
  valor: ReactNode;
  detalhe?: ReactNode;
}) {
  return (
    <div className="min-w-0 border-b border-rule-2 px-[18px] py-3.5 last:border-b-0 sm:border-r sm:border-b-0 sm:last:border-r-0">
      <dt className="min-h-[2.6em] text-[12.5px] leading-snug text-ink-2">{rotulo}</dt>
      <dd className="mt-1.5 font-display text-[38px] leading-none font-extrabold">{valor}</dd>
      {detalhe ? (
        <dd className="mt-1.5 font-mono text-xs leading-snug text-ink-3">{detalhe}</dd>
      ) : null}
    </div>
  );
}
