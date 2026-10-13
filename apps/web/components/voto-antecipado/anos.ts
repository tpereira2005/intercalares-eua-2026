import type { ComparacaoAno, FaixaEtaria } from "@/lib/voto-antecipado/vista.ts";

/**
 * Traço de cada ano nos gráficos (docs/design.md): o ano atual a ocre, a
 * intercalar de referência a tinta cheia, a presidencial tracejada e as
 * intercalares mais antigas na cor da régua.
 */
export interface EstiloAno {
  classe: string;
  largura: number;
  tracejado?: string;
}

export function estiloAno(
  ano: number,
  anoAtual: number,
  comparacoes: readonly ComparacaoAno[],
): EstiloAno {
  if (ano === anoAtual) return { classe: "stroke-signal", largura: 3 };
  const comparacao = comparacoes.find((c) => c.anoBase === ano);
  if (comparacao?.tipo === "presidencial") {
    return { classe: "stroke-ink-3", largura: 1.75, tracejado: "4 3" };
  }
  if (comparacao === comparacoes[0]) return { classe: "stroke-ink", largura: 1.75 };
  return { classe: "stroke-rule", largura: 1.75 };
}

/** Rótulo de uma faixa etária com traço de intervalo ("18–24"). */
export function rotuloFaixa(faixa: FaixaEtaria): string {
  return faixa.replace("-", "–");
}
