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
 * Valor de um agregador público do voto genérico usado no ambiente nacional.
 *
 * This interface was referenced by `Contratos`'s JSON-Schema
 * via the `definition` "AgregadorVotoGenerico".
 */
export interface AgregadorVotoGenerico {
  margem: number;
  nome: string;
}
/**
 * Margem nacional no voto para a Câmara (D-R) que serve de centro às simulações.
 *
 * This interface was referenced by `Contratos`'s JSON-Schema
 * via the `definition` "AmbienteNacional".
 */
export interface AmbienteNacional {
  agregadores: AgregadorVotoGenerico[];
  /**
   * Erro histórico (raiz do erro quadrático médio) das médias do voto genérico.
   */
  desvio_padrao: number;
  fonte: "agregadores" | "media_sondagens_voto_generico" | "sondagens_senado";
  margem: number;
}
/**
 * Métricas de uma câmara, calculadas só sobre corridas disputadas e já decididas.
 *
 * This interface was referenced by `Contratos`'s JSON-Schema
 * via the `definition` "AvaliacaoCamara".
 */
export interface AvaliacaoCamara {
  acertos: number;
  /**
   * Média de (probabilidade - resultado)²: 0 é perfeito, 0,25 é atirar uma moeda.
   */
  brier: number;
  calibracao: FaixaCalibracao[];
  camara: "camara" | "senado";
  cobertura_80: number | null;
  corridas_avaliadas: number;
  corridas_com_margem: number;
  corridas_erradas: string[];
  /**
   * Corridas ainda sem vencedor conhecido (contagem lenta); ficam fora das métricas.
   */
  corridas_por_decidir: string[];
  erro_absoluto_margem: number | null;
  /**
   * Média de -ln(probabilidade dada ao vencedor): pune mais a confiança errada.
   */
  log_loss: number;
  lugares_d_previstos: number;
  lugares_d_reais: number | null;
  /**
   * Probabilidade que a previsão deu a quem ficou com o controlo (se já conhecido).
   */
  prob_controlo_vencedor: number | null;
  /**
   * Média de (prevista - real), em pontos D-R: positivo sobrestimou o lado democrata.
   */
  vies_margem: number | null;
}
/**
 * Corridas cujo favorito tinha probabilidade dentro da faixa, e quantas ele ganhou.
 *
 * A faixa usa a probabilidade do favorito (sempre 50% ou mais), seja qual for o partido,
 * para que a calibração não dependa de qual lado é o democrata.
 *
 * This interface was referenced by `Contratos`'s JSON-Schema
 * via the `definition` "FaixaCalibracao".
 */
export interface FaixaCalibracao {
  corridas: number;
  /**
   * Fração das corridas da faixa em que o favorito ganhou.
   */
  frequencia: number | null;
  limite_inferior: number;
  limite_superior: number;
  /**
   * Probabilidade média atribuída ao favorito (``None`` sem corridas na faixa).
   */
  prob_media: number | null;
}
/**
 * Avaliação pública da previsão congelada face aos resultados (Fase 4 do plano).
 *
 * This interface was referenced by `Contratos`'s JSON-Schema
 * via the `definition` "AvaliacaoPrevisao".
 */
export interface AvaliacaoPrevisao {
  ambiente_previsto: number;
  ambiente_real: number | null;
  ano: number;
  camaras: AvaliacaoCamara[];
  /**
   * Data de corte da previsão avaliada (1 de novembro em 2026).
   */
  corte: string;
  metadados: Metadados;
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
 * O mesmo modelo aplicado a uma eleição passada, só com dados anteriores ao corte.
 *
 * This interface was referenced by `Contratos`'s JSON-Schema
 * via the `definition` "Backtest".
 */
export interface Backtest {
  ambiente_previsto: number;
  ambiente_real: number;
  ano: number;
  brier: number;
  camara: "camara" | "senado";
  /**
   * Fração das margens reais dentro do intervalo de 80% (o ideal é 0,8).
   */
  cobertura_80: number;
  controlo_real: "D" | "R";
  corridas_avaliadas: number;
  corridas_erradas: string[];
  corte: string;
  erro_absoluto_competitivas: number;
  fonte_ambiente: "agregadores" | "media_sondagens_voto_generico" | "sondagens_senado";
  lugares_d_mediana: number;
  lugares_d_p10: number;
  lugares_d_p90: number;
  lugares_d_reais: number;
  prob_controlo_d: number;
  prob_controlo_r: number;
  /**
   * Média de (previsto - real) nas corridas com margem prevista abaixo de 15 pontos.
   */
  vies_competitivas: number;
}
/**
 * This interface was referenced by `Contratos`'s JSON-Schema
 * via the `definition` "Candidatura".
 */
export interface Candidatura {
  /**
   * Identificador estável dentro da corrida (o da fonte, ou o nome normalizado).
   */
  id: string;
  nome: string;
  partido: "dem" | "rep" | "outro";
  /**
   * Rótulo do partido tal como a fonte o escreve (ex.: "LIB", "Green").
   */
  partido_fonte: string | null;
  /**
   * Votos no estado por tipo de voto, quando a fonte os separa (vazio se não).
   */
  por_modalidade: VotosModalidade[];
  votos: number;
}
/**
 * This interface was referenced by `Contratos`'s JSON-Schema
 * via the `definition` "VotosModalidade".
 */
export interface VotosModalidade {
  modalidade: "dia_eleicao" | "antecipado_presencial" | "correio" | "provisorio" | "outro";
  votos: number;
}
/**
 * This interface was referenced by `Contratos`'s JSON-Schema
 * via the `definition` "CicloAgregado".
 */
export interface CicloAgregado {
  ano: number;
  data_eleicao: string;
  notas: string[];
  /**
   * Boletins por correspondência pedidos até ao mesmo dia, quando a fonte os tem.
   */
  pedidos: number | null;
  tipo: "intercalar" | "presidencial";
  /**
   * Final nos anos anteriores; acumulado até ``dias_antes`` em 2026.
   */
  votos: number;
  /**
   * Votos até ao mesmo dia do ciclo que o ano atual (só nos anos de comparação).
   */
  votos_mesmo_dia: number | null;
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
 * Estado de que só se acompanham alguns condados.
 *
 * This interface was referenced by `Contratos`'s JSON-Schema
 * via the `definition` "CoberturaParcial".
 */
export interface CoberturaParcial {
  /**
   * FIPS dos condados com fonte. Os outros condados do estado não têm dados: não estão
   * por apurar, estão fora da recolha.
   *
   * @minItems 1
   */
  condados: [string, ...string[]];
  estado: CodigoEstado;
  nota: string;
}
/**
 * This interface was referenced by `Contratos`'s JSON-Schema
 * via the `definition` "ContagemModo".
 */
export interface ContagemModo {
  modo: "dia_eleicao" | "antecipado_presencial" | "correio" | "provisorio" | "outro";
  votos_d: number;
  votos_outros: number;
  votos_r: number;
}
/**
 * This interface was referenced by `Contratos`'s JSON-Schema
 * via the `definition` "Corrida".
 */
export interface Corrida {
  /**
   * @minItems 1
   */
  candidatos: [Candidatura, ...Candidatura[]];
  cargo: "senado" | "camara" | "governador";
  /**
   * Distrito da Câmara (0 nos estados com um só distrito); ``None`` nos outros cargos.
   */
  distrito: number | null;
  especial: boolean;
  estado: CodigoEstado;
  geografia: ResultadoGeografico[];
  /**
   * Os mesmos identificadores da previsão (``PrevisaoCongresso``): ``NC-S``, ``PA-08``,
   * ``AK-00``, ``OH-S-especial``; e ``XX-G`` para governador.
   */
  id: string;
  /**
   * Nome da corrida tal como a fonte o escreve.
   */
  nome_fonte: string;
  notas: string[];
  tipo_unidade: ("seccao" | "condado" | "municipio") | null;
  /**
   * Total de votos válidos na corrida, incluindo candidatos não nomeados (write-in).
   */
  total: number;
  unidades_reportadas: number | null;
  unidades_totais: number | null;
}
/**
 * Resultado de uma corrida num condado (ou município) do estado.
 *
 * This interface was referenced by `Contratos`'s JSON-Schema
 * via the `definition` "ResultadoGeografico".
 */
export interface ResultadoGeografico {
  /**
   * FIPS de 5 dígitos para condados; código da fonte para municípios.
   */
  codigo: string;
  nivel: "condado" | "municipio";
  nome: string;
  total: number;
  unidades_reportadas: number | null;
  unidades_totais: number | null;
  votos: VotosCandidato[];
}
/**
 * This interface was referenced by `Contratos`'s JSON-Schema
 * via the `definition` "VotosCandidato".
 */
export interface VotosCandidato {
  /**
   * ``Candidatura.id``.
   */
  candidato: string;
  votos: number;
}
/**
 * Quanto os votos contados se afastam, em média, da previsão congelada.
 *
 * This interface was referenced by `Contratos`'s JSON-Schema
 * via the `definition` "DesvioNacionalNoite".
 */
export interface DesvioNacionalNoite {
  corridas_informativas: number;
  desvio_padrao: number;
  /**
   * Desvio nacional estimado em pontos de margem D-R (positivo: melhor para D).
   */
  media: number;
}
/**
 * A previsão de um dia, reduzida ao necessário para desenhar a evolução.
 *
 * This interface was referenced by `Contratos`'s JSON-Schema
 * via the `definition` "DiaHistorico".
 */
export interface DiaHistorico {
  ambiente_margem: number;
  camara: PontoHistoricoCamara;
  congelada: boolean;
  corridas: PontoHistoricoCorrida[];
  corte: string;
  senado: PontoHistoricoCamara;
}
/**
 * Resumo de uma câmara numa data de corte.
 *
 * This interface was referenced by `Contratos`'s JSON-Schema
 * via the `definition` "PontoHistoricoCamara".
 */
export interface PontoHistoricoCamara {
  lugares_d_mediana: number;
  lugares_d_p10: number;
  lugares_d_p90: number;
  prob_controlo_d: number;
  prob_controlo_r: number;
}
/**
 * Probabilidade e margem prevista de uma corrida numa data de corte.
 *
 * This interface was referenced by `Contratos`'s JSON-Schema
 * via the `definition` "PontoHistoricoCorrida".
 */
export interface PontoHistoricoCorrida {
  id: string;
  margem_prevista: number;
  prob_d: number;
}
/**
 * Estado prioritário que o site não acompanha, e porquê.
 *
 * This interface was referenced by `Contratos`'s JSON-Schema
 * via the `definition` "EstadoSemDados".
 */
export interface EstadoSemDados {
  estado: CodigoEstado;
  /**
   * ``bloqueado``: a fonte oficial existe, mas recusa pedidos automáticos (não contornamos
   * o bloqueio). ``sem_fonte_gratuita``: não há dados oficiais gratuitos.
   */
  motivo: "bloqueado" | "sem_fonte_gratuita";
  /**
   * Explicação curta em PT-PT, para mostrar no site.
   */
  nota: string;
}
/**
 * Pontos por ordem cronológica (o mais recente no fim), um por projeção guardada.
 *
 * Para o ficheiro não crescer sem limite ao longo da noite, dois pontos guardados
 * seguidos distam pelo menos ``intervalo_minutos``, exceto os dois últimos: o último
 * ponto é sempre a projeção mais recente e substitui-se até haver um intervalo completo.
 *
 * This interface was referenced by `Contratos`'s JSON-Schema
 * via the `definition` "HistoricoNoite".
 */
export interface HistoricoNoite {
  ano: number;
  corte_prior: string;
  intervalo_minutos: number;
  metadados: Metadados;
  /**
   * @minItems 1
   */
  pontos: [PontoNoite, ...PontoNoite[]];
  prior_congelado: boolean;
  reconstruido: boolean;
}
/**
 * Uma projeção reduzida ao necessário para desenhar a evolução da noite.
 *
 * This interface was referenced by `Contratos`'s JSON-Schema
 * via the `definition` "PontoNoite".
 */
export interface PontoNoite {
  camara: PontoNoiteCamara;
  /**
   * Só as corridas que já têm votos contados.
   */
  corridas: PontoNoiteCorrida[];
  desvio_nacional: number;
  gerado_em: string;
  /**
   * Instante dos resultados usados (o mesmo de ``ProjecaoNoite.instante``).
   */
  instante: string;
  senado: PontoNoiteCamara;
  votos_contados: number;
}
/**
 * Resumo de uma câmara num instante da noite.
 *
 * This interface was referenced by `Contratos`'s JSON-Schema
 * via the `definition` "PontoNoiteCamara".
 */
export interface PontoNoiteCamara {
  corridas_com_votos: number;
  lugares_d_mediana: number;
  lugares_d_p10: number;
  lugares_d_p90: number;
  prob_controlo_d: number;
  prob_controlo_r: number;
}
/**
 * Uma corrida com votos contados num instante da noite.
 *
 * This interface was referenced by `Contratos`'s JSON-Schema
 * via the `definition` "PontoNoiteCorrida".
 */
export interface PontoNoiteCorrida {
  fracao_contada: number | null;
  id: string;
  margem_projetada: number;
  prob_d: number;
}
/**
 * Uma entrada por data de corte, por ordem cronológica (a mais recente no fim).
 *
 * This interface was referenced by `Contratos`'s JSON-Schema
 * via the `definition` "HistoricoPrevisao".
 */
export interface HistoricoPrevisao {
  ano: number;
  dias: DiaHistorico[];
  metadados: Metadados;
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
 * Uma categoria em 2026 face ao ano de referência, no mesmo dia do ciclo.
 *
 * This interface was referenced by `Contratos`'s JSON-Schema
 * via the `definition` "LinhaComparacaoAgregada".
 */
export interface LinhaComparacaoAgregada {
  ano_base: number;
  categoria: string;
  dimensao: "faixa" | "partido" | "modalidade";
  /**
   * Quota da categoria nos votos antecipados de 2026 (composição).
   */
  quota: number | null;
  quota_base: number | null;
  /**
   * votos / votos_base - 1: positivo quando a categoria vai à frente do ano de referência.
   */
  ritmo: number | null;
  votos: number;
  votos_base: number;
}
/**
 * Resumo de uma corrida para o painel da noite eleitoral.
 *
 * This interface was referenced by `Contratos`'s JSON-Schema
 * via the `definition` "LinhaCorridaNacional".
 */
export interface LinhaCorridaNacional {
  /**
   * Unidades reportadas / unidades totais, quando a fonte as indica.
   */
  apuramento: number | null;
  atualizado_fonte: string | null;
  cargo: "senado" | "camara" | "governador";
  /**
   * ``condados``: os votos são só dos condados acompanhados, não do estado inteiro.
   */
  cobertura?: "estado" | "condados";
  distrito: number | null;
  estado: CodigoEstado;
  /**
   * Ficheiro do estado com o detalhe (ex.: ``nc.json``).
   */
  ficheiro: string;
  id: string;
  total: number;
  votos_dem: number;
  votos_outros: number;
  votos_rep: number;
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
 * Resumo de um estado para a página inicial.
 *
 * This interface was referenced by `Contratos`'s JSON-Schema
 * via the `definition` "LinhaEstadoNacional".
 */
export interface LinhaEstadoNacional {
  ano_base: number | null;
  dados_ate: string;
  dias_antes: number;
  estado: CodigoEstado;
  /**
   * Nome do ficheiro completo do estado, publicado ao lado deste.
   */
  ficheiro: string;
  granularidade: "boletim" | "condado";
  modalidades: ("correio" | "presencial")[];
  /**
   * Quota de eleitores com 65 ou mais anos (só nos estados com idade).
   */
  quota_65_mais: number | null;
  quota_65_mais_base: number | null;
  /**
   * Quota de eleitores registados como democratas nos votos (registo, não voto).
   */
  quota_dem: number | null;
  quota_dem_base: number | null;
  quota_rep: number | null;
  quota_rep_base: number | null;
  ritmo: number | null;
  votos: number;
  /**
   * Votos do ano de referência até ao mesmo dia do ciclo.
   */
  votos_base: number | null;
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
 * This interface was referenced by `Contratos`'s JSON-Schema
 * via the `definition` "LinhaGeografiaAgregada".
 */
export interface LinhaGeografiaAgregada {
  ano: number;
  /**
   * FIPS de cinco dígitos (condado) ou número do distrito em vigor em 2026.
   */
  codigo: string;
  /**
   * Faixa larga, nos estados com idade (Pensilvânia). As linhas por faixa têm
   * ``partido = "total"``; as linhas por partido têm ``faixa = "total"``.
   */
  faixa?: "18-29" | "30-49" | "50-64" | "65+" | "desconhecida" | "total";
  nivel: "condado" | "distrito";
  nome: string;
  partido: "dem" | "rep" | "nao_afiliado" | "outro" | "total";
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
 * Contributo de um grupo histórico para a participação de uma unidade geográfica e
 * faixa larga até ao dia (o mesmo dia do ciclo em todos os anos, com o mapa de 2026).
 *
 * This interface was referenced by `Contratos`'s JSON-Schema
 * via the `definition` "LinhaHistoricoGeografia".
 */
export interface LinhaHistoricoGeografia {
  ano: number;
  ano_referencia: number;
  /**
   * FIPS de cinco dígitos (condado) ou número do distrito no mapa de 2026.
   */
  codigo: string;
  /**
   * votos / registados: a soma dos grupos dá a taxa de participação da unidade e faixa.
   */
  contributo: number | null;
  faixa: "18-29" | "30-49" | "50-64" | "65+" | "desconhecida" | "total";
  grupo:
    | "antecipado_na_referencia"
    | "dia_eleicao_na_referencia"
    | "absteve_se_na_referencia"
    | "recenseado_apos_referencia"
    | "sem_historico";
  nivel: "condado" | "distrito";
  nome: string;
  /**
   * Recenseados da unidade e faixa (todos os grupos).
   */
  registados: number;
  votos: number;
}
/**
 * Boletins por correspondência pedidos, devolvidos e por devolver até ao dia.
 *
 * This interface was referenced by `Contratos`'s JSON-Schema
 * via the `definition` "LinhaPedidos".
 */
export interface LinhaPedidos {
  ano: number;
  devolvidos: number;
  faixa: "18-24" | "25-29" | "30-39" | "40-49" | "50-64" | "65-74" | "75+" | "desconhecida" | "total";
  partido: "dem" | "rep" | "nao_afiliado" | "outro" | "total";
  pedidos: number;
  pendentes: number;
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
 * Parâmetros da média de sondagens, para o site os poder explicar.
 *
 * This interface was referenced by `Contratos`'s JSON-Schema
 * via the `definition` "MetodoMedia".
 */
export interface MetodoMedia {
  amostra_maxima: number;
  amostra_referencia: number;
  janela_dias: number;
  meia_vida_dias: number;
  peso_partidaria: number;
}
/**
 * Erro histórico das médias de sondagens do Senado.
 *
 * This interface was referenced by `Contratos`'s JSON-Schema
 * via the `definition` "ParametrosErroSondagens".
 */
export interface ParametrosErroSondagens {
  desvio_ano: number;
  erro_base: number;
  erro_por_instituto: number;
  /**
   * Parte do erro do voto genérico que se transmite às sondagens do Senado.
   */
  ligacao_nacional: number;
  observacoes: number;
}
/**
 * Parâmetros da regressão de fundamentos de uma câmara (anos anteriores apenas).
 *
 * This interface was referenced by `Contratos`'s JSON-Schema
 * via the `definition` "ParametrosFundamentos".
 */
export interface ParametrosFundamentos {
  anos_treino: number[];
  camara: "camara" | "senado";
  desvio_ano: number;
  desvio_corrida: number;
  desvio_regiao: number;
  inclinacao_pvi: number;
  incumbencia: number;
  intercepto: number;
  observacoes: number;
  persistencia: number;
}
/**
 * Probabilidade de o lado democrata ficar com exatamente ``lugares`` lugares.
 *
 * This interface was referenced by `Contratos`'s JSON-Schema
 * via the `definition` "PontoDistribuicao".
 */
export interface PontoDistribuicao {
  lugares: number;
  probabilidade: number;
}
/**
 * Média de sondagens de uma corrida num dia.
 *
 * This interface was referenced by `Contratos`'s JSON-Schema
 * via the `definition` "PontoMedia".
 */
export interface PontoMedia {
  data: string;
  institutos: number;
  margem: number;
  sondagens: number;
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
 * Votos acumulados até um dia do ciclo.
 *
 * This interface was referenced by `Contratos`'s JSON-Schema
 * via the `definition` "PontoSerieAgregado".
 */
export interface PontoSerieAgregado {
  ano: number;
  dias_antes: number;
  faixa:
    | "18-24"
    | "25-29"
    | "30-39"
    | "40-49"
    | "50-64"
    | "65-74"
    | "75+"
    | "25-34"
    | "35-44"
    | "45-54"
    | "55-64"
    | "desconhecida"
    | "total";
  modalidade: "correio" | "presencial" | "total";
  partido: "dem" | "rep" | "nao_afiliado" | "outro" | "total";
  votos: number;
}
/**
 * Valores dos agregadores do voto genérico lidos num dia, e a sua média simples.
 *
 * This interface was referenced by `Contratos`'s JSON-Schema
 * via the `definition` "PontoVotoGenerico".
 */
export interface PontoVotoGenerico {
  /**
   * @minItems 1
   */
  agregadores: [ValorAgregador, ...ValorAgregador[]];
  data: string;
  margem: number;
}
/**
 * This interface was referenced by `Contratos`'s JSON-Schema
 * via the `definition` "ValorAgregador".
 */
export interface ValorAgregador {
  margem: number;
  nome: string;
}
/**
 * Previsão completa: ambiente, câmaras, corridas, parâmetros e backtests.
 *
 * This interface was referenced by `Contratos`'s JSON-Schema
 * via the `definition` "PrevisaoCongresso".
 */
export interface PrevisaoCongresso {
  ambiente: AmbienteNacional;
  ano: number;
  backtests: Backtest[];
  camara: ResumoCamara;
  /**
   * Verdadeiro quando ``corte`` é a data final (dois dias antes da eleição).
   */
  congelada: boolean;
  corridas: PrevisaoCorrida[];
  /**
   * Só entram dados até este dia (exclusive).
   */
  corte: string;
  data_eleicao: string;
  erro_sondagens: ParametrosErroSondagens;
  fundamentos: ParametrosFundamentos[];
  metadados: Metadados;
  notas: string[];
  /**
   * Peso do voto antecipado na previsão (0: só diagnóstico, ver a metodologia).
   */
  peso_voto_antecipado: number;
  semente: number;
  senado: ResumoCamara;
  simulacoes: number;
}
/**
 * Controlo e distribuição de lugares de uma câmara.
 *
 * ``lugares_d_*`` contam o lado democrata, incluindo independentes que ocupam esse lado
 * e, no Senado, os lugares que não vão a votos. O lado republicano é o complemento.
 *
 * This interface was referenced by `Contratos`'s JSON-Schema
 * via the `definition` "ResumoCamara".
 */
export interface ResumoCamara {
  camara: "camara" | "senado";
  distribuicao: PontoDistribuicao[];
  /**
   * Margem nacional a partir da qual o lado democrata passa a favorito ao controlo
   * (abaixo dela o favorito é o lado republicano). ``None`` se nunca muda nas simulações.
   */
  limiar_nacional: number | null;
  lugares_d_media: number;
  lugares_d_mediana: number;
  lugares_d_p10: number;
  lugares_d_p5: number;
  lugares_d_p90: number;
  lugares_d_p95: number;
  lugares_fora_de_jogo_d: number;
  lugares_fora_de_jogo_r: number;
  /**
   * Lugares ganhos por independentes (de qualquer lado), em média.
   */
  lugares_independentes_media: number;
  lugares_total: number;
  maioria: number;
  prob_controlo_d: number;
  /**
   * No Senado, 50-50 decide-se pelo partido do vice-presidente.
   */
  prob_controlo_r: number;
}
/**
 * Previsão de uma corrida: um distrito da Câmara ou um lugar do Senado.
 *
 * This interface was referenced by `Contratos`'s JSON-Schema
 * via the `definition` "PrevisaoCorrida".
 */
export interface PrevisaoCorrida {
  camara: "camara" | "senado";
  /**
   * Candidato do lado democrata (pode ser um independente, ver ``lado_d_independente``).
   */
  candidato_d: string | null;
  candidato_r: string | null;
  /**
   * Vencedor já certo (sem candidato de um dos lados).
   */
  decidida: ("D" | "R" | "I") | null;
  estado: CodigoEstado;
  /**
   * ``NC-01``, ``AK-00`` (distrito único), ``TX-S`` ou ``OH-S-especial``.
   */
  id: string;
  /**
   * Partido do incumbente quando se recandidata; ``None`` em lugar aberto.
   */
  incumbente_recandidato: ("D" | "R" | "I") | null;
  /**
   * Número de institutos com sondagens na média (só no Senado).
   */
  institutos: number;
  lado_d_independente: boolean;
  lado_r_independente: boolean;
  margem_fundamentos: number;
  margem_p10: number;
  margem_p90: number;
  margem_prevista: number;
  margem_sondagens: number | null;
  peso_sondagens: number;
  /**
   * Probabilidade de vitória do lado democrata.
   */
  prob_d: number;
  /**
   * Cook PVI em pontos (D+ positivo), tal como publicado: a margem é o dobro.
   */
  pvi: number;
}
/**
 * Projeção de uma corrida num instante da contagem.
 *
 * This interface was referenced by `Contratos`'s JSON-Schema
 * via the `definition` "ProjecaoCorridaNoite".
 */
export interface ProjecaoCorridaNoite {
  camara: "camara" | "senado";
  /**
   * Corrida sem disputa entre os dois lados na previsão (fica com o vencedor certo).
   */
  decidida: boolean;
  /**
   * Votos contados a dividir pelos votos esperados.
   */
  fracao_contada: number | null;
  id: string;
  /**
   * Margem D-R dos votos já contados; ``None`` sem votos.
   */
  margem_contada: number | null;
  margem_p10: number;
  margem_p90: number;
  /**
   * Margem prevista na previsão congelada.
   */
  margem_prior: number;
  margem_projetada: number;
  prob_d: number;
  prob_d_prior: number;
  unidades_com_votos: number;
  votos_contados: number;
  /**
   * Estimativa do total final de votos (contados mais por contar); ``None`` quando a
   * fonte não diz quanto falta e não há eleição de referência para o estimar.
   */
  votos_esperados: number | null;
}
/**
 * Projeção completa num instante: corridas, câmaras e desvio nacional.
 *
 * This interface was referenced by `Contratos`'s JSON-Schema
 * via the `definition` "ProjecaoNoite".
 */
export interface ProjecaoNoite {
  ano: number;
  camara: ResumoCamaraNoite;
  corridas: ProjecaoCorridaNoite[];
  /**
   * Data de corte da previsão congelada usada como ponto de partida.
   */
  corte_prior: string;
  desvio_nacional: DesvioNacionalNoite;
  /**
   * Instante dos resultados usados (o da recolha, ou o original numa repetição).
   */
  instante: string;
  metadados: Metadados;
  notas: string[];
  /**
   * ``False`` quando o ponto de partida é uma previsão ainda não congelada (por exemplo,
   * um ensaio antes de 1 de novembro).
   */
  prior_congelado: boolean;
  /**
   * ``True`` quando os resultados parciais são uma reconstrução (ensaio ou repetição) e
   * não a contagem real da noite.
   */
  reconstruido: boolean;
  semente: number;
  senado: ResumoCamaraNoite;
  simulacoes: number;
}
/**
 * Controlo e lugares de uma câmara, incluindo os lugares que não vão a votos.
 *
 * This interface was referenced by `Contratos`'s JSON-Schema
 * via the `definition` "ResumoCamaraNoite".
 */
export interface ResumoCamaraNoite {
  camara: "camara" | "senado";
  corridas_com_votos: number;
  distribuicao: PontoDistribuicao[];
  lugares_d_media: number;
  lugares_d_mediana: number;
  lugares_d_p10: number;
  lugares_d_p90: number;
  lugares_total: number;
  maioria: number;
  prob_controlo_d: number;
  prob_controlo_d_prior: number;
  prob_controlo_r: number;
}
/**
 * This interface was referenced by `Contratos`'s JSON-Schema
 * via the `definition` "ResultadosEstado".
 */
export interface ResultadosEstado {
  /**
   * Hora da última atualização declarada pela fonte, quando a fonte a indica.
   */
  atualizado_fonte: string | null;
  avisos: string[];
  cobertura?: "estado" | "condados";
  /**
   * FIPS dos condados incluídos, quando ``cobertura = "condados"``.
   */
  condados_cobertos?: string[];
  corridas: Corrida[];
  data_eleicao: string;
  estado: CodigoEstado;
  metadados: Metadados;
}
/**
 * This interface was referenced by `Contratos`'s JSON-Schema
 * via the `definition` "ResultadosNacional".
 */
export interface ResultadosNacional {
  avisos: string[];
  corridas: LinhaCorridaNacional[];
  data_eleicao: string;
  metadados: Metadados;
}
/**
 * Um instante da contagem em todos os estados acompanhados (entrada do Modelo C).
 *
 * This interface was referenced by `Contratos`'s JSON-Schema
 * via the `definition` "ResultadosParciais".
 */
export interface ResultadosParciais {
  ano: number;
  /**
   * Estados com só alguns condados: as suas unidades são esses condados (FIPS), sem
   * ``total`` do estado.
   */
  cobertura_parcial?: CoberturaParcial[];
  instante: string;
  metadados: Metadados;
  /**
   * ``True`` no ensaio: a ordem de chegada dos condados foi reconstruída a partir do
   * resultado final, porque as fontes não guardam os retratos intermédios.
   */
  reconstruido: boolean;
  unidades: UnidadeContagem[];
}
/**
 * Votos de uma corrida numa unidade geográfica, no formato do estimador ao vivo.
 *
 * This interface was referenced by `Contratos`'s JSON-Schema
 * via the `definition` "UnidadeContagem".
 */
export interface UnidadeContagem {
  atualizado_em: string | null;
  /**
   * Identificador da previsão (só Senado e Câmara).
   */
  corrida: string;
  /**
   * Só quando a fonte publica a fração do voto esperado (nenhuma das atuais o faz).
   */
  percentagem_contada: number | null;
  por_modo: ContagemModo[];
  seccoes_reportadas: number | null;
  seccoes_totais: number | null;
  /**
   * FIPS do condado, código do município, ou ``total`` quando a fonte só dá o total.
   * Um condado partido por vários distritos aparece uma vez em cada distrito.
   */
  unidade: string;
  /**
   * Candidatos com o rótulo democrata.
   */
  votos_d: number;
  votos_outros: number;
  votos_r: number;
}
/**
 * Uma sondagem entre os dois candidatos da corrida.
 *
 * This interface was referenced by `Contratos`'s JSON-Schema
 * via the `definition` "SondagemPublicada".
 */
export interface SondagemPublicada {
  amostra: number | null;
  /**
   * Último dia do trabalho de campo.
   */
  fim: string;
  instituto: string;
  margem: number;
  /**
   * Encomendada por um partido ou campanha (de qualquer lado).
   */
  partidaria: boolean;
  percentagem_d: number;
  percentagem_r: number;
  /**
   * Peso relativo na média atual (os pesos das sondagens de uma corrida somam 1); 0
   * quando a sondagem não entra (fora da janela ou substituída por outra população da
   * mesma sondagem).
   */
  peso: number;
  populacao: "lv" | "rv" | "a" | "?";
}
/**
 * This interface was referenced by `Contratos`'s JSON-Schema
 * via the `definition` "SondagensCongresso".
 */
export interface SondagensCongresso {
  ano: number;
  corridas: SondagensCorrida[];
  corte: string;
  metadados: Metadados;
  metodo: MetodoMedia;
  /**
   * Por ordem cronológica (o mais recente no fim).
   */
  voto_generico: PontoVotoGenerico[];
}
/**
 * This interface was referenced by `Contratos`'s JSON-Schema
 * via the `definition` "SondagensCorrida".
 */
export interface SondagensCorrida {
  camara: "camara" | "senado";
  candidato_d: string | null;
  candidato_r: string | null;
  estado: CodigoEstado;
  id: string;
  /**
   * Média no dia do corte (``None`` sem sondagens na janela).
   */
  media: PontoMedia | null;
  /**
   * Média dia a dia, só nos dias com sondagens na janela.
   */
  serie: PontoMedia[];
  /**
   * Da mais recente para a mais antiga.
   */
  sondagens: SondagemPublicada[];
}
/**
 * This interface was referenced by `Contratos`'s JSON-Schema
 * via the `definition` "VotoAntecipadoAgregado".
 */
export interface VotoAntecipadoAgregado {
  ano: number;
  avisos: string[];
  ciclos: CicloAgregado[];
  comparacao: LinhaComparacaoAgregada[];
  dados_ate: string;
  dias_antes: number;
  /**
   * Dimensões que a fonte permite analisar neste estado.
   */
  dimensoes: ("faixa" | "partido" | "modalidade" | "condado" | "distrito")[];
  estado: CodigoEstado;
  geografia: LinhaGeografiaAgregada[];
  granularidade: "boletim" | "condado";
  metadados: Metadados;
  /**
   * Modalidades que a fonte cobre (na Pensilvânia, por exemplo, só há correio).
   */
  modalidades: ("correio" | "presencial")[];
  pedidos: LinhaPedidos[];
  serie: PontoSerieAgregado[];
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
  /**
   * Histórico de voto (habituais, antecipação, voto novo) por condado e distrito e por
   * faixa larga. Vazio nos anos sem histórico individual de referência.
   */
  historico_geografia?: LinhaHistoricoGeografia[];
  metadados: Metadados;
  reserva: LinhaReserva[];
  serie: PontoSerie[];
}
/**
 * This interface was referenced by `Contratos`'s JSON-Schema
 * via the `definition` "VotoAntecipadoNacional".
 */
export interface VotoAntecipadoNacional {
  ano: number;
  avisos: string[];
  estados: LinhaEstadoNacional[];
  /**
   * Estados prioritários sem ficheiro, para o site não os mostrar como "ainda sem dados".
   */
  estados_sem_dados?: EstadoSemDados[];
  metadados: Metadados;
  /**
   * Soma dos estados acompanhados (não é um total nacional).
   */
  votos: number;
}
