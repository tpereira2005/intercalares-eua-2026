/**
 * Endereço público do site, usado nos metadados (Open Graph, canónicos, mapa do site).
 * `URL_SITE` substitui-o no build, por exemplo quando houver um domínio próprio.
 */
export const URL_SITE = new URL(
  process.env.URL_SITE ?? "https://intercalares-eua-2026.tomasmoraispereira-f5e.workers.dev",
);

/** Páginas públicas fixas, pela ordem da navegação (as dos estados acrescentam-se à parte). */
export const PAGINAS_FIXAS = [
  "/",
  "/voto-antecipado/",
  "/demografia/",
  "/mapa/",
  "/previsao/",
  "/sondagens/",
  "/resultados/",
  "/metodologia/",
] as const;
