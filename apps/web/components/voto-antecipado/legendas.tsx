import type { ReactNode } from "react";
import type { VistaVotoAntecipado } from "@/lib/voto-antecipado/vista.ts";
import { estiloAno } from "./anos.ts";

export function Legenda({ children }: { children: ReactNode }) {
  return (
    <div className="flex flex-wrap items-center gap-x-4 gap-y-1.5 text-[12.5px] text-ink-2">
      {children}
    </div>
  );
}

export function ItemLegenda({ amostra, children }: { amostra: ReactNode; children: ReactNode }) {
  return (
    <span className="inline-flex items-center gap-1.5">
      <span aria-hidden="true" className="inline-flex">
        {amostra}
      </span>
      {children}
    </span>
  );
}

export function AmostraAno({
  ano,
  anoAtual,
  vista,
  forma = "traco",
}: {
  ano: number;
  anoAtual: number;
  vista: VistaVotoAntecipado;
  forma?: "traco" | "linha";
}) {
  const estilo = estiloAno(ano, anoAtual, vista.comparacoes);
  if (ano === anoAtual && forma === "traco") {
    return <span className="inline-block h-2.5 w-3.5 rounded-[1px] bg-signal" />;
  }
  return (
    <svg width={forma === "traco" ? 6 : 16} height={12}>
      {forma === "traco" ? (
        <line
          x1={3}
          x2={3}
          y1={0}
          y2={12}
          strokeWidth={2}
          strokeDasharray={estilo.tracejado ? "3 2" : undefined}
          className={estilo.classe}
        />
      ) : (
        <line
          x1={0}
          x2={16}
          y1={6}
          y2={6}
          strokeWidth={Math.min(estilo.largura, 2.5)}
          strokeDasharray={estilo.tracejado}
          className={estilo.classe}
        />
      )}
    </svg>
  );
}

export function Amostra({ className, fill }: { className?: string; fill?: string }) {
  return (
    <svg width={14} height={10}>
      <rect width={14} height={10} className={className} fill={fill} />
    </svg>
  );
}
