/**
 * Padrões SVG partilhados pelos gráficos, ligados por omissão para leitores
 * com daltonismo: republicanos tracejado a 45°, não filiados pontilhado.
 * Usar com fill="url(#padrao-rep)" ou fill="url(#padrao-una)".
 */
export function PadroesSvg() {
  return (
    <svg width="0" height="0" className="absolute" aria-hidden="true" focusable="false">
      <defs>
        <pattern
          id="padrao-rep"
          width="6"
          height="6"
          patternUnits="userSpaceOnUse"
          patternTransform="rotate(45)"
        >
          <rect
            width="6"
            height="6"
            style={{ fill: "color-mix(in oklab, var(--rep) 30%, var(--sheet))" }}
          />
          <rect width="3" height="6" style={{ fill: "var(--rep)" }} />
        </pattern>
        <pattern id="padrao-una" width="5" height="5" patternUnits="userSpaceOnUse">
          <rect
            width="5"
            height="5"
            style={{ fill: "color-mix(in oklab, var(--una) 30%, var(--sheet))" }}
          />
          <circle cx="2.5" cy="2.5" r="1.4" style={{ fill: "var(--una)" }} />
        </pattern>
      </defs>
    </svg>
  );
}
