import { t } from "@/lib/mensagens.ts";

export type NivelQualidade = "individual" | "parcial" | "agregado";

const PREENCHIMENTO: Record<NivelQualidade, string> = {
  individual: "bg-ink-2",
  parcial: "bg-[linear-gradient(90deg,var(--ink-2)_50%,transparent_50%)]",
  agregado: "bg-transparent",
};

/**
 * Ponto cheio (dados individuais), meio (parciais) ou vazio (agregados ou geográficos).
 * Uma fonte não oficial diz-se sempre por extenso, mesmo na forma compacta.
 */
export function QualidadeDados({
  nivel,
  comTexto = false,
  naoOficial = false,
}: {
  nivel: NivelQualidade;
  comTexto?: boolean;
  naoOficial?: boolean;
}) {
  const texto = t(`comum.qualidade.${nivel}`);
  return (
    <span className="inline-flex items-center gap-1.5 text-[12.5px] text-ink-2">
      <span
        className={`inline-block size-2 rounded-full border-[1.5px] border-ink-2 ${PREENCHIMENTO[nivel]}`}
        aria-hidden="true"
      />
      {comTexto ? texto : <span className="sr-only">{texto}</span>}
      {naoOficial ? (
        <span className="rounded-[2px] border border-dashed border-ink-3 px-1 font-mono text-[10px] leading-[1.4] tracking-[0.06em] whitespace-nowrap text-ink-2 uppercase">
          {t("comum.selos.naoOficial")}
        </span>
      ) : null}
    </span>
  );
}
