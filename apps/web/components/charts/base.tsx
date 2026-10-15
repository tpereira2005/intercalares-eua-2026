"use client";

import {
  useEffect,
  useRef,
  useState,
  type KeyboardEvent,
  type ReactNode,
  type RefObject,
} from "react";

/** Largura disponível de um contentor, atualizada quando o ecrã muda. */
export function useLargura<T extends HTMLElement>(
  inicial = 640,
): [RefObject<T | null>, number, boolean] {
  const ref = useRef<T>(null);
  const [largura, setLargura] = useState(inicial);
  const [medida, setMedida] = useState(false);
  useEffect(() => {
    const elemento = ref.current;
    if (!elemento) return;
    const medir = () => {
      setLargura(Math.max(260, Math.floor(elemento.clientWidth)));
      setMedida(true);
    };
    medir();
    const observador = new ResizeObserver(medir);
    observador.observe(elemento);
    return () => {
      observador.disconnect();
    };
  }, []);
  return [ref, largura, medida];
}

const PASSOS = [0.0005, 0.001, 0.0025, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10];

/** Escala de eixo de 0 até um máximo redondo, com marcas em passos redondos (no máximo 5). */
export function escala(valor: number): { maximo: number; marcas: number[] } {
  const passo = PASSOS.find((p) => valor / p <= 5) ?? valor / 5;
  const divisoes = Math.max(1, Math.ceil(valor / passo - 1e-9));
  return {
    maximo: divisoes * passo,
    marcas: Array.from({ length: divisoes + 1 }, (_, i) => Number((i * passo).toPrecision(6))),
  };
}

/** Afasta rótulos verticais que se sobrepõem, mantendo a ordem. */
export function afastarRotulos(posicoes: readonly number[], distancia = 12): number[] {
  const ordem = posicoes.map((y, i) => ({ y, i })).sort((a, b) => a.y - b.y);
  for (let k = 1; k < ordem.length; k++) {
    const anterior = ordem[k - 1];
    const atual = ordem[k];
    if (anterior && atual && atual.y - anterior.y < distancia) atual.y = anterior.y + distancia;
  }
  const resultado = [...posicoes];
  for (const { y, i } of ordem) resultado[i] = y;
  return resultado;
}

/**
 * Contentor de um gráfico SVG com largura medida e título acessível. Um
 * gráfico com elementos que se escolhem é um grupo, para os leitores de ecrã
 * chegarem a esses elementos; os outros são uma imagem com título.
 */
export function Grafico({
  titulo,
  altura,
  alturaPorLargura,
  interativo = false,
  children,
}: {
  titulo: string;
  altura: number;
  /** Altura calculada a partir da largura medida, para gráficos que crescem com ela. */
  alturaPorLargura?: (largura: number) => number;
  interativo?: boolean;
  children: (largura: number) => ReactNode;
}) {
  const [ref, largura, medida] = useLargura<HTMLDivElement>();
  const alturaFinal = alturaPorLargura ? alturaPorLargura(largura) : altura;
  return (
    <div ref={ref} className="w-full min-w-0">
      <svg
        width={largura}
        height={alturaFinal}
        viewBox={`0 0 ${String(largura)} ${String(alturaFinal)}`}
        role={interativo ? "group" : "img"}
        aria-label={titulo}
        // Antes da medição o SVG escala com o contentor, na mesma proporção: a altura
        // quase não muda quando a largura real chega (sem salto de esquema).
        className={`block max-w-full overflow-visible font-sans ${medida ? "" : "h-auto w-full"}`}
      >
        <title>{titulo}</title>
        {children(largura)}
      </svg>
    </div>
  );
}

/** Propriedades de uma linha de gráfico que se pode escolher com o rato ou o teclado. */
export function linhaEscolhivel(rotulo: string, aoEscolher?: () => void, ativa?: boolean) {
  if (!aoEscolher) return {};
  return {
    role: "button",
    tabIndex: 0,
    "aria-label": rotulo,
    // Estado escolhido também por palavras, não só pelo fundo ocre.
    "aria-pressed": ativa ?? false,
    className: "cursor-pointer outline-none [&:focus-visible>rect:first-child]:stroke-signal",
    onClick: aoEscolher,
    onKeyDown: (evento: KeyboardEvent) => {
      if (evento.key === "Enter" || evento.key === " ") {
        evento.preventDefault();
        aoEscolher();
      }
    },
  } as const;
}

/** Fundo de uma linha: ocre suave quando é a faixa em foco. */
export function FundoLinha({
  y,
  largura,
  altura,
  ativa,
}: {
  y: number;
  largura: number;
  altura: number;
  ativa: boolean;
}) {
  return (
    <rect
      x={0}
      y={y + 1}
      width={largura}
      height={altura - 2}
      rx={3}
      strokeWidth={1.5}
      className={
        ativa ? "fill-signal-wash stroke-transparent" : "fill-transparent stroke-transparent"
      }
    />
  );
}

/** Texto com contorno da cor da folha, legível sobre qualquer preenchimento. */
export const HALO = {
  paintOrder: "stroke",
  stroke: "var(--sheet)",
  strokeWidth: 3,
  strokeLinejoin: "round",
} as const;
