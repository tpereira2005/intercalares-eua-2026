/* Ficheiro gerado por packages/contratos/scripts/gerar.mjs. Não editar à mão. */

/**
 * Código postal de duas letras de cada estado e do Distrito de Colúmbia.
 *
 * This interface was referenced by `Contratos`'s JSON-Schema
 * via the `definition` "CodigoEstado".
 */
export type CodigoEstado =
  | "AL"
  | "AK"
  | "AZ"
  | "AR"
  | "CA"
  | "CO"
  | "CT"
  | "DE"
  | "DC"
  | "FL"
  | "GA"
  | "HI"
  | "ID"
  | "IL"
  | "IN"
  | "IA"
  | "KS"
  | "KY"
  | "LA"
  | "ME"
  | "MD"
  | "MA"
  | "MI"
  | "MN"
  | "MS"
  | "MO"
  | "MT"
  | "NE"
  | "NV"
  | "NH"
  | "NJ"
  | "NM"
  | "NY"
  | "NC"
  | "ND"
  | "OH"
  | "OK"
  | "OR"
  | "PA"
  | "RI"
  | "SC"
  | "SD"
  | "TN"
  | "TX"
  | "UT"
  | "VT"
  | "VA"
  | "WA"
  | "WV"
  | "WI"
  | "WY";

/**
 * Contratos de dados da plataforma Intercalares EUA 2026.
 */
export interface Contratos {
  [k: string]: unknown | undefined;
}
/**
 * Uma eleição comparável (2026 ou um ano de referência).
 *
 * This interface was referenced by `Contratos`'s JSON-Schema
 * via the `definition` "CicloVotoAntecipado".
 */
export interface CicloVotoAntecipado {
  ano: number;
  /**
   * Eleição usada para classificar o histórico de voto de cada eleitor.
   */
  ano_referencia_historico: number | null;
  data_eleicao: string;
  fim_presencial_dias_antes: number | null;
  /**
   * Primeiro dia do voto antecipado presencial, em dias antes da eleição.
   */
  inicio_presencial_dias_antes: number | null;
  /**
   * Diferenças de regras ou de contexto que afetam a comparação.
   */
  notas: string[];
  registados: number;
  tipo: "intercalar" | "presidencial";
  /**
   * Total de votos antecipados: final nos anos anteriores, acumulado até agora em 2026.
   */
  votos_antecipados: number;
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
 * 2026 face a um ano de referência, no mesmo dia do ciclo, para uma faixa etária.
 *
 * This interface was referenced by `Contratos`'s JSON-Schema
 * via the `definition` "LinhaComparacao".
 */
export interface LinhaComparacao {
  ano_base: number;
  /**
   * Votos observados / esperados - 1. Positivo: acima do ritmo do ano de referência.
   */
  desvio: number | null;
  /**
   * Parte da variação da quota explicada por a faixa votar mais ou menos até este dia.
   */
  efeito_participacao: number;
  /**
   * Parte da variação da quota explicada por haver mais ou menos recenseados da faixa.
   */
  efeito_recenseamento: number;
  /**
   * Votos esperados: recenseados de hoje x taxa do ano de referência no mesmo dia.
   */
  esperado: number;
  faixa: "18-24" | "25-29" | "30-39" | "40-49" | "50-64" | "65-74" | "75+" | "desconhecida" | "total";
  /**
   * Quota da faixa no voto antecipado (composição).
   */
  quota: number;
  quota_base: number;
  /**
   * Quota da faixa nos eleitores recenseados.
   */
  quota_recenseamento: number;
  quota_recenseamento_base: number;
  registados: number;
  registados_base: number;
  /**
   * Percentagem dos recenseados da faixa que já votou (participação).
   */
  taxa: number | null;
  taxa_base: number | null;
  votos: number;
  votos_base: number;
}
/**
 * This interface was referenced by `Contratos`'s JSON-Schema
 * via the `definition` "LinhaCruzamento".
 */
export interface LinhaCruzamento {
  ano: number;
  categoria: string;
  dimensao: "partido" | "raca" | "etnia" | "genero" | "modalidade";
  faixa: "18-24" | "25-29" | "30-39" | "40-49" | "50-64" | "65-74" | "75+" | "desconhecida" | "total";
  /**
   * Para a modalidade, o denominador é o total da faixa.
   */
  registados: number;
  votos: number;
}
/**
 * This interface was referenced by `Contratos`'s JSON-Schema
 * via the `definition` "LinhaGeografia".
 */
export interface LinhaGeografia {
  ano: number;
  /**
   * FIPS de cinco dígitos (condado) ou número do distrito no mapa de 2026.
   */
  codigo: string;
  faixa: "18-29" | "30-49" | "50-64" | "65+" | "desconhecida" | "total";
  nivel: "condado" | "distrito";
  nome: string;
  registados: number;
  votos: number;
}
/**
 * Contributo de um grupo histórico para a participação de uma faixa até ao dia.
 *
 * This interface was referenced by `Contratos`'s JSON-Schema
 * via the `definition` "LinhaHistorico".
 */
export interface LinhaHistorico {
  ano: number;
  ano_referencia: number;
  /**
   * votos / registados: a soma dos grupos dá a taxa de participação da faixa.
   */
  contributo: number | null;
  faixa: "18-24" | "25-29" | "30-39" | "40-49" | "50-64" | "65-74" | "75+" | "desconhecida" | "total";
  grupo:
    | "antecipado_na_referencia"
    | "dia_eleicao_na_referencia"
    | "absteve_se_na_referencia"
    | "recenseado_apos_referencia"
    | "sem_historico";
  /**
   * Recenseados da faixa (todos os grupos).
   */
  registados: number;
  votos: number;
}
/**
 * Eleitores que votaram na eleição de referência e ainda não votaram até ao dia.
 *
 * This interface was referenced by `Contratos`'s JSON-Schema
 * via the `definition` "LinhaReserva".
 */
export interface LinhaReserva {
  ano: number;
  faixa: "18-24" | "25-29" | "30-39" | "40-49" | "50-64" | "65-74" | "75+" | "desconhecida" | "total";
  habituais: number;
  ja_votaram: number;
  partido: "dem" | "rep" | "nao_afiliado" | "outro" | "total";
  restantes: number;
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
/**
 * Votos acumulados até um dia do ciclo.
 *
 * This interface was referenced by `Contratos`'s JSON-Schema
 * via the `definition` "PontoSerie".
 */
export interface PontoSerie {
  ano: number;
  dias_antes: number;
  faixa: "18-24" | "25-29" | "30-39" | "40-49" | "50-64" | "65-74" | "75+" | "desconhecida" | "total";
  modalidade: "correio" | "presencial" | "total";
  partido: "dem" | "rep" | "nao_afiliado" | "outro" | "total";
  registados: number;
  votos: number;
}
/**
 * Rastreador de voto antecipado de um estado, com a análise por idade.
 *
 * This interface was referenced by `Contratos`'s JSON-Schema
 * via the `definition` "VotoAntecipadoEstado".
 */
export interface VotoAntecipadoEstado {
  ano: number;
  /**
   * Limitações conhecidas desta atualização, em PT-PT, para mostrar no site.
   */
  avisos: string[];
  ciclos: CicloVotoAntecipado[];
  comparacao: LinhaComparacao[];
  cruzamentos: LinhaCruzamento[];
  /**
   * Último dia com votos no ficheiro da fonte.
   */
  dados_ate: string;
  /**
   * Dias entre ``dados_ate`` e a eleição: o ponto do ciclo usado nas comparações.
   */
  dias_antes: number;
  estado: CodigoEstado;
  geografia: LinhaGeografia[];
  historico: LinhaHistorico[];
  metadados: Metadados;
  reserva: LinhaReserva[];
  serie: PontoSerie[];
}
