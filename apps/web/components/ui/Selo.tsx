import type { ReactNode } from "react";

/**
 * Selo de estado de um número ou painel.
 * - ilustrativo / estimativa: contorno tracejado (valor não observado diretamente);
 * - solido: valor oficial;
 * - sinal: ciclo atual ou ao vivo;
 * - geografico: inferência geográfica (contorno pontilhado).
 */
export type VarianteSelo = "tracejado" | "solido" | "sinal" | "geografico";

const ESTILOS: Record<VarianteSelo, string> = {
  tracejado: "border-dashed border-ink-3 text-ink-2",
  solido: "border-solid border-ink-3 text-ink-2",
  sinal: "border-solid border-signal bg-signal-wash text-signal-ink",
  geografico: "border-dotted border-ink-3 text-ink-2",
};

export function Selo({
  variante = "tracejado",
  children,
}: {
  variante?: VarianteSelo;
  children: ReactNode;
}) {
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-[2px] border px-1.5 py-1 font-mono text-[10.5px] leading-none tracking-[0.07em] whitespace-nowrap uppercase ${ESTILOS[variante]}`}
    >
      {children}
    </span>
  );
}
