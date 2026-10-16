/**
 * Guia da noite eleitoral: o que seguir a cada hora de fecho das urnas, em hora de Lisboa.
 *
 * Não há aqui modelo novo. Junta-se o que o site já publica: os horários de fecho
 * (`lib/fecho.ts`), a previsão congelada (categorias e caminho para a maioria) e, quando
 * existe, o consenso de outros prognosticadores. A ordem de contagem por estado é a do
 * Modelo C (docs/metodologia/noite-eleitoral.md, secção "Ordem de contagem por estado").
 */

import type { CodigoEstado } from "@intercalares/contratos";
import { FECHOS, gruposFecho, type FechoEstado } from "../fecho.ts";
import { caminhoMaioria } from "../previsao/cenarios.ts";
import { CENTRO, comparacaoDaCorrida, type VistaPrognosticos } from "../previsao/prognosticos.ts";
import {
  categoria,
  type Camara,
  type Categoria,
  type CorridaVista,
  type Lado,
  type VistaPrevisao,
} from "../previsao/vista.ts";

/**
 * `antecipadoPrimeiro`: o voto antecipado de cada condado publica-se inteiro logo a seguir
 * ao fecho, antes do voto do dia; `correioDepois`: o correio conta-se depois do voto do
 * dia, ou ao longo de dias. Nos outros estados a ordem não é clara e não se diz nada.
 */
export type OrdemContagem = "antecipadoPrimeiro" | "correioDepois";

const ANTECIPADO_PRIMEIRO: ReadonlySet<CodigoEstado> = new Set(["NC", "GA", "FL", "TX", "OH"]);
const CORREIO_DEPOIS: ReadonlySet<CodigoEstado> = new Set(["PA", "AZ", "MI", "WI", "NV"]);

export function ordemContagem(estado: CodigoEstado): OrdemContagem | null {
  if (ANTECIPADO_PRIMEIRO.has(estado)) return "antecipadoPrimeiro";
  if (CORREIO_DEPOIS.has(estado)) return "correioDepois";
  return null;
}

export interface CorridaGuia {
  corrida: CorridaVista;
  categoria: Categoria;
  /** Posição do consenso dos outros prognosticadores (0 a 6); `null` sem classificações. */
  consenso: number | null;
  /** Lados para os quais esta corrida é a decisiva (o ponto de viragem) na sua câmara. */
  decisivaPara: Lado[];
  /** Perto da linha da maioria de algum dos lados (a decisiva ou as vizinhas). */
  pertoDaLinha: boolean;
}

export interface EstadoGuia {
  estado: CodigoEstado;
  /** Fecho das últimas urnas, quando o estado tem dois fusos. */
  todas: string | null;
  contagem: OrdemContagem | null;
  corridas: CorridaGuia[];
}

export interface BlocoGuia {
  /** Fecho da maior parte das urnas (ISO, UTC). */
  instante: string;
  /** Estados com corridas a seguir, pela corrida mais renhida. */
  estados: EstadoGuia[];
  /** Estados que fecham a esta hora sem nenhuma corrida a seguir. */
  semCorridas: CodigoEstado[];
}

export interface Decisiva {
  camara: Camara;
  lado: Lado;
  corrida: CorridaVista;
  /** Probabilidade de o lado ganhar a corrida. */
  prob: number;
  /** Fecho das urnas no estado da corrida (ISO, UTC); `null` sem horário. */
  fecho: string | null;
}

export interface VistaGuia {
  decisivas: Decisiva[];
  blocos: BlocoGuia[];
  /** Número de corridas a seguir na noite inteira. */
  total: number;
}

const LADOS: readonly Lado[] = ["D", "R"];
const CAMARAS: readonly Camara[] = ["senado", "camara"];

/** Inclinada ou renhida: a previsão dá ao favorito menos de 80%. */
function emJogo(cat: Categoria): boolean {
  return cat === "inclinadaD" || cat === "renhida" || cat === "inclinadaR";
}

/** Distância ao empate: 0,5 é o mais renhido possível. */
function renhida(c: CorridaVista): number {
  return Math.abs(c.probD - 0.5);
}

/**
 * Uma corrida segue-se se a previsão a dá como inclinada ou renhida, se fica perto da linha
 * da maioria, ou se o consenso dos outros prognosticadores a dá como inclinada ou renhida.
 */
export function construirGuia(
  previsao: VistaPrevisao,
  prognosticos: VistaPrognosticos | null,
  fechos: readonly FechoEstado[] = FECHOS,
): VistaGuia {
  const decisivas: Decisiva[] = [];
  const decisivaPara = new Map<string, Lado[]>();
  const perto = new Set<string>();
  const fechoDe = new Map(fechos.map((f) => [f.estado, f.primeiro]));
  for (const camara of CAMARAS) {
    for (const lado of LADOS) {
      const caminho = caminhoMaioria(previsao, camara, lado);
      if (!caminho) continue;
      for (const c of caminho.corridas) {
        perto.add(c.corrida.id);
        if (!c.decisiva) continue;
        decisivaPara.set(c.corrida.id, [...(decisivaPara.get(c.corrida.id) ?? []), lado]);
        decisivas.push({
          camara,
          lado,
          corrida: c.corrida,
          prob: c.prob,
          fecho: fechoDe.get(c.corrida.estado) ?? null,
        });
      }
    }
  }

  const todas = [...previsao.corridasSenado, ...previsao.corridasCamara];
  const porEstado = new Map<CodigoEstado, CorridaGuia[]>();
  for (const corrida of todas) {
    if (corrida.decidida !== null) continue;
    const cat = categoria(corrida.probD);
    const consenso = prognosticos
      ? (comparacaoDaCorrida(prognosticos, corrida)?.consenso ?? null)
      : null;
    const consensoEmJogo = consenso !== null && Math.abs(consenso - CENTRO) <= 1;
    const proxima = perto.has(corrida.id);
    if (!emJogo(cat) && !proxima && !consensoEmJogo) continue;
    const lista = porEstado.get(corrida.estado) ?? [];
    lista.push({
      corrida,
      categoria: cat,
      consenso,
      decisivaPara: decisivaPara.get(corrida.id) ?? [],
      pertoDaLinha: proxima,
    });
    porEstado.set(corrida.estado, lista);
  }

  const blocos = gruposFecho(fechos).map((g): BlocoGuia => {
    const estados: EstadoGuia[] = [];
    const semCorridas: CodigoEstado[] = [];
    for (const f of g.estados) {
      const corridas = (porEstado.get(f.estado) ?? []).sort(
        (a, b) =>
          // O Senado primeiro; dentro de cada câmara, da mais renhida para a menos.
          Number(a.corrida.camara === "camara") - Number(b.corrida.camara === "camara") ||
          renhida(a.corrida) - renhida(b.corrida) ||
          a.corrida.id.localeCompare(b.corrida.id),
      );
      if (corridas.length === 0) {
        semCorridas.push(f.estado);
        continue;
      }
      estados.push({
        estado: f.estado,
        todas: f.todas ?? null,
        contagem: ordemContagem(f.estado),
        corridas,
      });
    }
    estados.sort(
      (a, b) =>
        Math.min(...a.corridas.map((c) => renhida(c.corrida))) -
          Math.min(...b.corridas.map((c) => renhida(c.corrida))) ||
        a.estado.localeCompare(b.estado),
    );
    return { instante: g.instante, estados, semCorridas };
  });

  return {
    decisivas,
    blocos,
    total: [...porEstado.values()].reduce((s, l) => s + l.length, 0),
  };
}
