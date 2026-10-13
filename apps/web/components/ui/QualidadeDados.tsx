import { t } from "@/lib/mensagens.ts";

export type NivelQualidade = "individual" | "parcial" | "agregado";

const PREENCHIMENTO: Record<NivelQualidade, string> = {
  individual: "bg-ink-2",
  parcial: "bg-[linear-gradient(90deg,var(--ink-2)_50%,transparent_50%)]",
  agregado: "bg-transparent",
};

/** Ponto cheio (dados individuais), meio (parciais) ou vazio (agregados ou geográficos). */
export function QualidadeDados({
  nivel,
  comTexto = false,
}: {
  nivel: NivelQualidade;
  comTexto?: boolean;
}) {
  const texto = t(`comum.qualidade.${nivel}`);
  return (
    <span className="inline-flex items-center gap-1.5 text-[12.5px] text-ink-2">
      <span
        className={`inline-block size-2 rounded-full border-[1.5px] border-ink-2 ${PREENCHIMENTO[nivel]}`}
        aria-hidden="true"
      />
      {comTexto ? texto : <span className="sr-only">{texto}</span>}
    </span>
  );
}
