/** Recursos e variáveis disponíveis no Worker (ver wrangler.jsonc). */
export interface Env {
  ASSETS: Fetcher;
  DB: D1Database;
  AMBIENTE: string;
  /** Ficheiros da noite eleitoral servidos pela API ao vivo (docs/api-ao-vivo.md). */
  URL_PARCIAIS: string;
  URL_PROJECAO_NOITE: string;
  URL_HISTORICO_NOITE: string;
  /** Chamadas das redações registadas à mão (contrato ChamadasRedacoes). */
  URL_CHAMADAS: string;
  /** Intervalo de consulta sugerido aos browsers, em segundos (30 a 600; omissão 60). */
  INTERVALO_S?: string;
}
