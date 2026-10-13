/* Ficheiro gerado por packages/contratos/scripts/gerar.mjs. Não editar à mão. */

/**
 * Contratos de dados da plataforma Intercalares EUA 2026.
 */
export interface Contratos {
  [k: string]: unknown | undefined;
}
/**
 * Origem de um conjunto de dados, citada em cada número publicado.
 *
 * This interface was referenced by `Contratos`'s JSON-Schema
 * via the `definition` "Fonte".
 */
export interface Fonte {
  /**
   * Licença ou termos de utilização, quando conhecidos.
   */
  licenca: string | null;
  /**
   * Nome legível da fonte, por exemplo "North Carolina State Board of Elections".
   */
  nome: string;
  /**
   * Momento da recolha, sempre com fuso horário.
   */
  obtida_em: string;
  /**
   * Endereço exato de onde os dados foram obtidos.
   */
  url: string;
}
/**
 * Cabeçalho comum a todos os ficheiros de dados publicados.
 *
 * This interface was referenced by `Contratos`'s JSON-Schema
 * via the `definition` "Metadados".
 */
export interface Metadados {
  /**
   * Todas as fontes usadas para produzir o ficheiro.
   *
   * @minItems 1
   */
  fontes: [Fonte, ...Fonte[]];
  /**
   * Momento em que o pipeline gerou o ficheiro.
   */
  gerado_em: string;
  /**
   * Versão dos contratos com que o ficheiro foi produzido.
   */
  versao_esquema: string;
}
