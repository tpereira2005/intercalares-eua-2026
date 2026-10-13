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

/** Diferença em pontos percentuais com sinal explícito, por exemplo "+3,2 p.p.". */
export function formatarPontos(diferenca: number, casasDecimais = 1): string {
  const texto = new Intl.NumberFormat(LOCALE, {
    minimumFractionDigits: casasDecimais,
    maximumFractionDigits: casasDecimais,
    signDisplay: "exceptZero",
  }).format(diferenca * 100);
  return `${texto} p.p.`;
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
