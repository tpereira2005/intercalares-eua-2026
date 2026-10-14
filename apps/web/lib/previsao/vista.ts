/**
 * Vista da previsão (contrato PrevisaoCongresso) para a página /previsao/.
 *
 * Não há aqui metodologia nova: probabilidades, margens e intervalos vêm do
 * modelo (docs/metodologia/previsao.md). Esta camada só seleciona, ordena e
 * agrupa. As categorias de probabilidade são apenas uma forma de ler a tabela.
 */

import type {
  AmbienteNacional,
  Backtest,
  HistoricoPrevisao,
  PrevisaoCongresso,
  PrevisaoCorrida,
  ResumoCamara,
} from "@intercalares/contratos";

export type Camara = ResumoCamara["camara"];
export type Lado = "D" | "R";

/**
 * Quantil 90% de uma t de Student com 5 graus de liberdade, reescalada para
 * variância 1 como no modelo (pipeline/src/pipeline/modelo/simulacao.py):
 * 1,476 × √(3/5). Dá o intervalo de 80% do ambiente nacional.
 */
export const Q90_T5_UNITARIO = 1.475884 * Math.sqrt(3 / 5);

export interface ResumoVista {
  camara: Camara;
  total: number;
  maioria: number;
  probD: number;
  probR: number;
  /** Lado com maior probabilidade de controlo; `null` num empate exato. */
  favorito: Lado | null;
  media: number;
  mediana: number;
  p10: number;
  p90: number;
  independentes: number;
  foraDeJogo: { D: number; R: number };
  limiar: number | null;
  /**
   * Probabilidade de cada total de lugares do lado democrata, sem buracos e sem
   * as caudas que somam menos de 0,1% de cada lado.
   */
  distribuicao: { lugares: number; probabilidade: number }[];
}

export interface CorridaVista {
  id: string;
  camara: Camara;
  estado: PrevisaoCorrida["estado"];
  /** Número do distrito (0 em distrito único) ou `null` no Senado. */
  distrito: number | null;
  especial: boolean;
  candidatoD: string | null;
  candidatoR: string | null;
  independenteD: boolean;
  independenteR: boolean;
  incumbente: PrevisaoCorrida["incumbente_recandidato"];
  decidida: PrevisaoCorrida["decidida"];
  margem: number;
  margemP10: number;
  margemP90: number;
  probD: number;
  sondagens: { margem: number; institutos: number; peso: number } | null;
  /** Cook PVI em pontos (D+ positivo), tal como publicado. */
  pvi: number;
  /** Margem dos fundamentos (PVI, incumbência, ambiente nacional), antes das sondagens. */
  margemFundamentos: number;
}

export const CATEGORIAS = [
  "solidaD",
  "provavelD",
  "inclinadaD",
  "renhida",
  "inclinadaR",
  "provavelR",
  "solidaR",
] as const;
export type Categoria = (typeof CATEGORIAS)[number];

/** Limites de leitura: 95%, 80% e 60% para cada lado; entre 40% e 60% é renhida. */
export function categoria(probD: number): Categoria {
  if (probD >= 0.95) return "solidaD";
  if (probD >= 0.8) return "provavelD";
  if (probD > 0.6) return "inclinadaD";
  if (probD >= 0.4) return "renhida";
  if (probD > 0.2) return "inclinadaR";
  if (probD > 0.05) return "provavelR";
  return "solidaR";
}

export interface VistaPrevisao {
  ano: number;
  dataEleicao: string;
  corte: string;
  congelada: boolean;
  geradoEm: string;
  simulacoes: number;
  fontes: { nome: string; url: string }[];
  notas: string[];
  pesoVotoAntecipado: number;
  ambiente: {
    margem: number;
    desvio: number;
    p10: number;
    p90: number;
    fonte: AmbienteNacional["fonte"];
    agregadores: { nome: string; margem: number }[];
  };
  camara: ResumoVista;
  senado: ResumoVista;
  /** Corridas ao Senado, da mais renhida para a menos renhida. */
  corridasSenado: CorridaVista[];
  /** Distritos da Câmara, do mais renhido para o menos renhido. */
  corridasCamara: CorridaVista[];
  categorias: Record<Camara, Record<Categoria, number>>;
  backtests: Backtest[];
}

/** Fração de cada cauda da distribuição de lugares que fica fora do gráfico. */
export const CAUDA = 0.001;

/** Distribuição contígua, do primeiro ao último total de lugares fora das caudas. */
export function aparar(
  distribuicao: readonly { lugares: number; probabilidade: number }[],
  cauda: number = CAUDA,
): { lugares: number; probabilidade: number }[] {
  const ordenada = [...distribuicao].sort((a, b) => a.lugares - b.lugares);
  const total = ordenada.reduce((s, p) => s + p.probabilidade, 0);
  let acumulado = 0;
  let minimo: number | null = null;
  let maximo: number | null = null;
  for (const p of ordenada) {
    const antes = acumulado;
    acumulado += p.probabilidade;
    if (minimo === null && acumulado > cauda * total) minimo = p.lugares;
    if (antes < (1 - cauda) * total) maximo = p.lugares;
  }
  if (minimo === null || maximo === null) return [];
  const pontos = new Map(ordenada.map((p) => [p.lugares, p.probabilidade]));
  return Array.from({ length: maximo - minimo + 1 }, (_, i) => ({
    lugares: minimo + i,
    probabilidade: pontos.get(minimo + i) ?? 0,
  }));
}

function resumir(r: ResumoCamara): ResumoVista {
  const distribuicao = aparar(r.distribuicao);
  return {
    camara: r.camara,
    total: r.lugares_total,
    maioria: r.maioria,
    probD: r.prob_controlo_d,
    probR: r.prob_controlo_r,
    favorito:
      r.prob_controlo_d > r.prob_controlo_r
        ? "D"
        : r.prob_controlo_r > r.prob_controlo_d
          ? "R"
          : null,
    media: r.lugares_d_media,
    mediana: r.lugares_d_mediana,
    p10: r.lugares_d_p10,
    p90: r.lugares_d_p90,
    independentes: r.lugares_independentes_media,
    foraDeJogo: { D: r.lugares_fora_de_jogo_d, R: r.lugares_fora_de_jogo_r },
    limiar: r.limiar_nacional,
    distribuicao,
  };
}

function corrida(c: PrevisaoCorrida): CorridaVista {
  const distrito = /^[A-Z]{2}-(\d{2})$/.exec(c.id)?.[1];
  return {
    id: c.id,
    camara: c.camara,
    estado: c.estado,
    distrito: distrito === undefined ? null : Number(distrito),
    especial: c.id.endsWith("-especial"),
    candidatoD: c.candidato_d,
    candidatoR: c.candidato_r,
    independenteD: c.lado_d_independente,
    independenteR: c.lado_r_independente,
    incumbente: c.incumbente_recandidato,
    decidida: c.decidida,
    margem: c.margem_prevista,
    margemP10: c.margem_p10,
    margemP90: c.margem_p90,
    probD: c.prob_d,
    sondagens:
      c.margem_sondagens === null
        ? null
        : { margem: c.margem_sondagens, institutos: c.institutos, peso: c.peso_sondagens },
    pvi: c.pvi,
    margemFundamentos: c.margem_fundamentos,
  };
}

/** Mais renhida primeiro: probabilidade mais perto de 50%, depois margem mais pequena. */
function porRenhida(a: CorridaVista, b: CorridaVista): number {
  return (
    Math.abs(a.probD - 0.5) - Math.abs(b.probD - 0.5) ||
    Math.abs(a.margem) - Math.abs(b.margem) ||
    a.id.localeCompare(b.id)
  );
}

function contar(corridas: readonly CorridaVista[]): Record<Categoria, number> {
  const contagem = Object.fromEntries(CATEGORIAS.map((c) => [c, 0])) as Record<Categoria, number>;
  for (const c of corridas) contagem[categoria(c.probD)] += 1;
  return contagem;
}

export function construirVistaPrevisao(dados: PrevisaoCongresso): VistaPrevisao {
  const todas = dados.corridas.map(corrida);
  const corridasSenado = todas.filter((c) => c.camara === "senado").sort(porRenhida);
  const corridasCamara = todas.filter((c) => c.camara === "camara").sort(porRenhida);
  const { margem, desvio_padrao: desvio } = dados.ambiente;
  return {
    ano: dados.ano,
    dataEleicao: dados.data_eleicao,
    corte: dados.corte,
    congelada: dados.congelada,
    geradoEm: dados.metadados.gerado_em,
    simulacoes: dados.simulacoes,
    fontes: dados.metadados.fontes.map((f) => ({ nome: f.nome, url: f.url })),
    notas: [...dados.notas],
    pesoVotoAntecipado: dados.peso_voto_antecipado,
    ambiente: {
      margem,
      desvio,
      p10: margem - Q90_T5_UNITARIO * desvio,
      p90: margem + Q90_T5_UNITARIO * desvio,
      fonte: dados.ambiente.fonte,
      agregadores: dados.ambiente.agregadores
        .map((a) => ({ nome: a.nome, margem: a.margem }))
        .sort((a, b) => a.nome.localeCompare(b.nome)),
    },
    camara: resumir(dados.camara),
    senado: resumir(dados.senado),
    corridasSenado,
    corridasCamara,
    categorias: { camara: contar(corridasCamara), senado: contar(corridasSenado) },
    backtests: [...dados.backtests].sort(
      (a, b) => b.ano - a.ano || (a.camara === b.camara ? 0 : a.camara === "camara" ? -1 : 1),
    ),
  };
}

export interface PontoEvolucao {
  corte: string;
  probD: number;
  probR: number;
  mediana: number;
  p10: number;
  p90: number;
}

export interface VistaEvolucao {
  /** Datas de corte por ordem cronológica. */
  cortes: string[];
  ambiente: { corte: string; margem: number }[];
  camara: PontoEvolucao[];
  senado: PontoEvolucao[];
  /** Probabilidade democrata de cada corrida na última entrada com pelo menos 7 dias. */
  semanaAnterior: { corte: string; probD: Map<string, number> } | null;
  /** Evolução de cada corrida, por ordem cronológica (só no servidor: é um Map). */
  corridas: Map<string, PontoCorrida[]>;
}

export interface PontoCorrida {
  corte: string;
  probD: number;
  margem: number;
}

const UM_DIA = 24 * 60 * 60 * 1000;

function diasEntre(de: string, ate: string): number {
  return Math.round((Date.parse(`${ate}T12:00:00Z`) - Date.parse(`${de}T12:00:00Z`)) / UM_DIA);
}

/**
 * Evolução até ao corte da previsão mostrada. Entradas posteriores (um
 * histórico mais recente do que o ficheiro principal) ficam de fora, para os
 * dois nunca se contradizerem.
 */
export function construirEvolucao(historico: HistoricoPrevisao, corte: string): VistaEvolucao {
  const dias = [...historico.dias]
    .filter((d) => d.corte <= corte)
    .sort((a, b) => a.corte.localeCompare(b.corte));
  const ponto = (d: (typeof dias)[number], camara: Camara): PontoEvolucao => {
    const c = d[camara];
    return {
      corte: d.corte,
      probD: c.prob_controlo_d,
      probR: c.prob_controlo_r,
      mediana: c.lugares_d_mediana,
      p10: c.lugares_d_p10,
      p90: c.lugares_d_p90,
    };
  };
  const anterior = dias.filter((d) => diasEntre(d.corte, corte) >= 7).at(-1);
  return {
    cortes: dias.map((d) => d.corte),
    ambiente: dias.map((d) => ({ corte: d.corte, margem: d.ambiente_margem })),
    camara: dias.map((d) => ponto(d, "camara")),
    senado: dias.map((d) => ponto(d, "senado")),
    semanaAnterior: anterior
      ? { corte: anterior.corte, probD: new Map(anterior.corridas.map((c) => [c.id, c.prob_d])) }
      : null,
    corridas: dias.reduce((porCorrida, d) => {
      for (const c of d.corridas) {
        const ponto = { corte: d.corte, probD: c.prob_d, margem: c.margem_prevista };
        const lista = porCorrida.get(c.id);
        if (lista) lista.push(ponto);
        else porCorrida.set(c.id, [ponto]);
      }
      return porCorrida;
    }, new Map<string, PontoCorrida[]>()),
  };
}
