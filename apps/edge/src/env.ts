/** Recursos e variáveis disponíveis no Worker (ver wrangler.jsonc). */
export interface Env {
  ASSETS: Fetcher;
  DB: D1Database;
  AMBIENTE: string;
  /** Ficheiros da noite eleitoral servidos pela API ao vivo (docs/api-ao-vivo.md). */
  URL_PARCIAIS: string;
  URL_PROJECAO_NOITE: string;
  URL_HISTORICO_NOITE: string;
}
