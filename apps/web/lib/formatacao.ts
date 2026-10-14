/**
 * Formatação de números, percentagens e datas em português de Portugal.
 * Todo o site usa estas funções para garantir consistência (ex.: "12,4%").
 */

const LOCALE = "pt-PT";
const FUSO_ELEICAO = "America/New_York";

const numeroInteiro = new Intl.NumberFormat(LOCALE, { maximumFractionDigits: 0 });

export function formatarNumero(valor: number): string {
  return numeroInteiro.format(valor);
}

export function formatarPercentagem(fracao: number, casasDecimais = 1): string {
  return new Intl.NumberFormat(LOCALE, {
    style: "percent",
    minimumFractionDigits: casasDecimais,
    maximumFractionDigits: casasDecimais,
  }).format(fracao);
}

/** Diferença em pontos percentuais com sinal explícito, por exemplo "+2,1 pp". */
export function formatarPontos(diferenca: number, casasDecimais = 1): string {
  const texto = new Intl.NumberFormat(LOCALE, {
    minimumFractionDigits: casasDecimais,
    maximumFractionDigits: casasDecimais,
    signDisplay: "exceptZero",
  }).format(diferenca * 100);
  return `${texto} pp`;
}

/** Data por extenso, por exemplo "3 de novembro de 2026", no fuso da costa leste. */
export function formatarData(data: Date, fuso: string = FUSO_ELEICAO): string {
  return new Intl.DateTimeFormat(LOCALE, { dateStyle: "long", timeZone: fuso }).format(data);
}

export const DIA_DA_ELEICAO = new Date("2026-11-03T12:00:00Z");

/** Dias inteiros que faltam até ao dia da eleição (0 no próprio dia e depois). */
export function diasAteEleicao(agora: Date, eleicao: Date = DIA_DA_ELEICAO): number {
  const umDia = 24 * 60 * 60 * 1000;
  return Math.max(0, Math.ceil((eleicao.getTime() - agora.getTime()) / umDia));
}

/**
 * Margem entre partidos a partir da diferença D − R (em fração), por exemplo
 * "D +1,2" ou "R +0,6". Uma diferença nula escreve-se "Empate".
 */
export function formatarMargem(diferencaDemRep: number, casasDecimais = 1): string {
  const pontos = Math.abs(diferencaDemRep * 100);
  const texto = new Intl.NumberFormat(LOCALE, {
    minimumFractionDigits: casasDecimais,
    maximumFractionDigits: casasDecimais,
  }).format(pontos);
  if (Number(pontos.toFixed(casasDecimais)) === 0) return "Empate";
  return `${diferencaDemRep > 0 ? "D" : "R"} +${texto}`;
}

/**
 * Dia do ciclo em relação à eleição, com o sinal menos tipográfico (U+2212):
 * "E−21" faltando 21 dias, "Dia E" no próprio dia, "E+2" depois.
 */
export function formatarDiaCiclo(diasParaEleicao: number): string {
  if (diasParaEleicao === 0) return "Dia E";
  return diasParaEleicao > 0 ? `E\u2212${diasParaEleicao}` : `E+${-diasParaEleicao}`;
}

/** Variação relativa com sinal explícito, por exemplo "+12%" ou "-37%". */
export function formatarVariacao(fracao: number, casasDecimais = 0): string {
  return new Intl.NumberFormat(LOCALE, {
    style: "percent",
    minimumFractionDigits: casasDecimais,
    maximumFractionDigits: casasDecimais,
    signDisplay: "exceptZero",
  }).format(fracao);
}

/** Número curto para valores grandes, por exemplo "1,12 M" ou "29,7 mil". */
export function formatarCompacto(valor: number): string {
  return new Intl.NumberFormat(LOCALE, {
    notation: "compact",
    maximumSignificantDigits: 3,
  }).format(valor);
}

/** Data curta para eixos e tabelas, por exemplo "13 out.", no fuso da costa leste. */
export function formatarDataCurta(data: Date, fuso: string = FUSO_ELEICAO): string {
  const dia = new Intl.DateTimeFormat(LOCALE, { day: "numeric", timeZone: fuso }).format(data);
  const mes = new Intl.DateTimeFormat(LOCALE, { month: "short", timeZone: fuso }).format(data);
  return `${dia} ${mes}`;
}

/** Margem já em pontos percentuais (D − R), como nos ficheiros da previsão: "D +8,4". */
export function formatarMargemPontos(pontos: number, casasDecimais = 1): string {
  return formatarMargem(pontos / 100, casasDecimais);
}

/** Dia e hora na costa leste, por exemplo "3 de novembro, 21:34". */
export function formatarDataHora(data: Date, fuso: string = FUSO_ELEICAO): string {
  const dia = new Intl.DateTimeFormat(LOCALE, {
    day: "numeric",
    month: "long",
    timeZone: fuso,
  }).format(data);
  const hora = new Intl.DateTimeFormat(LOCALE, {
    hour: "2-digit",
    minute: "2-digit",
    hourCycle: "h23",
    timeZone: fuso,
  }).format(data);
  return `${dia}, ${hora}`;
}

/** Hora na costa leste, em 24 horas, por exemplo "21:34". */
export function formatarHora(data: Date, fuso: string = FUSO_ELEICAO): string {
  return new Intl.DateTimeFormat(LOCALE, {
    hour: "2-digit",
    minute: "2-digit",
    hourCycle: "h23",
    timeZone: fuso,
  }).format(data);
}

/** Tempo até um instante, curto: "3 d 4 h", "2 h 14 min", "9 min" ou "menos de 1 min". */
export function formatarDuracao(milissegundos: number): string {
  const minutos = Math.floor(milissegundos / 60_000);
  if (minutos < 1) return "menos de 1 min";
  const dias = Math.floor(minutos / 1440);
  const horas = Math.floor((minutos % 1440) / 60);
  const resto = minutos % 60;
  if (dias > 0) return horas > 0 ? `${String(dias)} d ${String(horas)} h` : `${String(dias)} d`;
  if (horas > 0)
    return resto > 0 ? `${String(horas)} h ${String(resto)} min` : `${String(horas)} h`;
  return `${String(resto)} min`;
}

/** Mês e ano para eixos longos, por exemplo "nov. 2025", no fuso da costa leste. */
export function formatarMesAno(data: Date, fuso: string = FUSO_ELEICAO): string {
  const mes = new Intl.DateTimeFormat(LOCALE, { month: "short", timeZone: fuso }).format(data);
  const ano = new Intl.DateTimeFormat(LOCALE, { year: "numeric", timeZone: fuso }).format(data);
  return `${mes} ${ano}`;
}
