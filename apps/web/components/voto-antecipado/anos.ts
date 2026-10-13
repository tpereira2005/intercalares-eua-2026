import {
  FAIXAS,
  type ComparacaoAno,
  type FaixaEtaria,
  type VistaVotoAntecipado,
} from "@/lib/voto-antecipado/vista.ts";

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

/** O mínimo de cada comparação que o estilo precisa (serve as duas vistas). */
export type AnoComparado = Pick<ComparacaoAno, "anoBase" | "tipo">;

export function estiloAno(
  ano: number,
  anoAtual: number,
  comparacoes: readonly AnoComparado[],
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

export interface LinhaBarra {
  faixa: FaixaEtaria;
  valor: number;
  referencias: { ano: number; valor: number }[];
}

/**
 * Linhas do gráfico por idade: o valor de 2026 de cada faixa e, como
 * referência, o mesmo valor em cada ano de comparação no mesmo dia do ciclo.
 */
export function linhasPorIdade(
  vista: VistaVotoAntecipado,
  comparacao: ComparacaoAno,
  medida: "quota" | "taxa",
): LinhaBarra[] {
  return FAIXAS.flatMap((f) => {
    const atual = comparacao.faixas.find((l) => l.faixa === f);
    const valor = atual ? atual[medida] : null;
    if (valor === null) return [];
    return [
      {
        faixa: f,
        valor,
        referencias: vista.comparacoes.flatMap((c) => {
          const l = c.faixas.find((x) => x.faixa === f);
          const v = l ? (medida === "taxa" ? l.taxaBase : l.quotaBase) : null;
          return v === null ? [] : [{ ano: c.anoBase, valor: v }];
        }),
      },
    ];
  });
}
