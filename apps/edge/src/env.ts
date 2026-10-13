/** Recursos e variáveis disponíveis no Worker (ver wrangler.jsonc). */
export interface Env {
  ASSETS: Fetcher;
  DB: D1Database;
  AMBIENTE: string;
}
