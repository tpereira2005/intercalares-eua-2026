/**
 * Classificações de outros prognosticadores (contrato PrognosticosExternos, asset
 * `prognosticos-2026.json` da Release `dados-previsao`), postas ao lado da previsão.
 *
 * Para comparar, cada classificação ocupa um lugar na escala das categorias de leitura
 * do Escrutínio (`CATEGORIAS`, de "Sólida D" a "Sólida R"): Safe/Solid é sólida, Likely é
 * provável, Lean é inclinada, Tossup é renhida e Tilt fica a meio caminho entre inclinada
 * e renhida. O consenso é a mediana dessas posições. É uma régua de leitura, não um
 * modelo: nada aqui altera as probabilidades publicadas.
 */

import type { Classificacao, PrognosticosExternos } from "@intercalares/contratos";
import {
  CATEGORIAS,
  categoria,
  type Camara,
  type Categoria,
  type CorridaVista,
  type Lado,
  type VistaPrevisao,
} from "./vista.ts";

/** Posição de "Renhida" na escala (0 é Sólida D, 6 é Sólida R). */
export const CENTRO = 3;

const DISTANCIA: Record<Classificacao["categoria"], number> = {
  seguro: 3,
  provavel: 2,
  inclinado: 1,
  ligeiro: 0.5,
  empate: 0,
};

export interface PrognosticadorVista {
  chave: string;
  nome: string;
  /** Data da versão das classificações (AAAA-MM-DD), como a fonte a indica. */
  data: string | null;
}

export interface ClassificacaoVista {
  chave: string;
  nome: string;
  categoria: Classificacao["categoria"];
  /** Lado favorecido, já com o independente no lado que o modelo lhe atribui. */
  lado: Lado | null;
  /** Posição na escala de `CATEGORIAS` (0 a 6; o Tilt fica em 2,5 ou 3,5). */
  posicao: number;
  /** Categoria do Escrutínio com que se pinta (o Tilt pinta-se como inclinada). */
  cor: Categoria;
}

export interface ComparacaoCorrida {
  corrida: CorridaVista;
  nossa: Categoria;
  nossaPosicao: number;
  classificacoes: ClassificacaoVista[];
  /** Mediana das posições dos outros prognosticadores. */
  consenso: number;
  /** Lado favorecido pelo consenso; `null` quando a mediana é o empate. */
  ladoConsenso: Lado | null;
  /**
   * `favorito`: o Escrutínio e o consenso favorecem lados diferentes; `confianca`: o mesmo
   * lado, mas a duas ou mais categorias de distância; `null` sem divergência assinalável.
   */
  divergencia: "favorito" | "confianca" | null;
}

export interface ResumoComparacao {
  camara: Camara;
  /** Fontes desta câmara (a página da Wikipedia de onde vêm as classificações). */
  fontes: { nome: string; url: string }[];
  prognosticadores: PrognosticadorVista[];
  /** Corridas classificadas por pelo menos um prognosticador, da mais renhida à menos. */
  corridas: ComparacaoCorrida[];
  mesmoFavorito: number;
  favoritoDiferente: number;
}

export interface VistaPrognosticos {
  recolhidoEm: string;
  congelado: boolean;
  fontes: { nome: string; url: string }[];
  senado: ResumoComparacao;
  camara: ResumoComparacao;
}

function lado(posicao: number): Lado | null {
  if (posicao < CENTRO) return "D";
  if (posicao > CENTRO) return "R";
  return null;
}

function mediana(valores: readonly number[]): number {
  const ordenados = [...valores].sort((a, b) => a - b);
  const meio = Math.floor(ordenados.length / 2);
  const a = ordenados[meio] ?? CENTRO;
  if (ordenados.length % 2 === 1) return a;
  return ((ordenados[meio - 1] ?? a) + a) / 2;
}

/** Lado de uma classificação; um independente fica no lado em que o modelo o põe. */
function ladoClassificacao(c: Classificacao, corrida: CorridaVista): Lado | null {
  if (c.partido === "D" || c.partido === "R") return c.partido;
  if (c.partido === "I" && corrida.independenteD) return "D";
  if (c.partido === "I" && corrida.independenteR) return "R";
  return null;
}

/** Categoria com que se pinta uma posição: a meio caminho, a mais afastada do empate. */
export function corDe(posicao: number): Categoria {
  // O Tilt (2,5 ou 3,5) pinta-se como inclinada.
  const indice = posicao < CENTRO ? Math.floor(posicao) : Math.ceil(posicao);
  return CATEGORIAS[indice] ?? "renhida";
}

export function classificacaoVista(
  c: Classificacao,
  corrida: CorridaVista,
  nomes: ReadonlyMap<string, string>,
): ClassificacaoVista | null {
  const l = ladoClassificacao(c, corrida);
  if (c.categoria !== "empate" && l === null) return null;
  const distancia = DISTANCIA[c.categoria];
  const posicao = l === "R" ? CENTRO + distancia : CENTRO - distancia;
  return {
    chave: c.prognosticador,
    nome: nomes.get(c.prognosticador) ?? c.prognosticador,
    categoria: c.categoria,
    lado: c.categoria === "empate" ? null : l,
    posicao,
    cor: corDe(posicao),
  };
}

export function compararCorrida(
  corrida: CorridaVista,
  classificacoes: readonly ClassificacaoVista[],
): ComparacaoCorrida {
  const nossa = categoria(corrida.probD);
  const nossaPosicao = CATEGORIAS.indexOf(nossa);
  const consenso = mediana(classificacoes.map((c) => c.posicao));
  const ladoNosso = lado(nossaPosicao);
  const ladoConsenso = lado(consenso);
  const divergencia =
    ladoNosso !== null && ladoConsenso !== null && ladoNosso !== ladoConsenso
      ? "favorito"
      : Math.abs(nossaPosicao - consenso) >= 2
        ? "confianca"
        : null;
  return {
    corrida,
    nossa,
    nossaPosicao,
    classificacoes: [...classificacoes],
    consenso,
    ladoConsenso,
    divergencia,
  };
}

function resumir(
  camara: Camara,
  dados: PrognosticosExternos,
  previsao: VistaPrevisao,
): ResumoComparacao {
  const lista = camara === "senado" ? dados.prognosticadores_senado : dados.prognosticadores_camara;
  const nomes = new Map(lista.map((p) => [p.chave, p.nome]));
  const porId = new Map(
    (camara === "senado" ? dados.senado : dados.camara).map((c) => [c.id, c.classificacoes]),
  );
  const corridas: ComparacaoCorrida[] = [];
  for (const corrida of camara === "senado" ? previsao.corridasSenado : previsao.corridasCamara) {
    const brutas = porId.get(corrida.id);
    if (!brutas) continue;
    const vistas = brutas
      .map((c) => classificacaoVista(c, corrida, nomes))
      .filter((c): c is ClassificacaoVista => c !== null);
    if (vistas.length > 0) corridas.push(compararCorrida(corrida, vistas));
  }
  // A página da Wikipedia de cada câmara; sem a distinguir, citam-se as duas.
  const todas = dados.metadados.fontes.map((f) => ({ nome: f.nome, url: f.url }));
  const marca = camara === "senado" ? "Senate" : "House";
  const proprias = todas.filter((f) => f.nome.includes(marca));
  return {
    camara,
    fontes: proprias.length > 0 ? proprias : todas,
    prognosticadores: lista.map((p) => ({ chave: p.chave, nome: p.nome, data: p.data ?? null })),
    corridas,
    mesmoFavorito: corridas.filter((c) => c.divergencia !== "favorito").length,
    favoritoDiferente: corridas.filter((c) => c.divergencia === "favorito").length,
  };
}

/** Só se compara com a previsão do mesmo ano. */
export function prognosticosBatemCerto(
  dados: PrognosticosExternos,
  previsao: Pick<VistaPrevisao, "ano">,
): boolean {
  return dados.ano === previsao.ano;
}

export function construirVistaPrognosticos(
  dados: PrognosticosExternos,
  previsao: VistaPrevisao,
): VistaPrognosticos {
  return {
    recolhidoEm: dados.recolhido_em,
    congelado: dados.congelado,
    fontes: dados.metadados.fontes.map((f) => ({ nome: f.nome, url: f.url })),
    senado: resumir("senado", dados, previsao),
    camara: resumir("camara", dados, previsao),
  };
}

/** Comparação de uma corrida; `null` quando nenhum prognosticador a classifica. */
export function comparacaoDaCorrida(
  vista: VistaPrognosticos,
  corrida: Pick<CorridaVista, "id" | "camara">,
): ComparacaoCorrida | null {
  return vista[corrida.camara].corridas.find((c) => c.corrida.id === corrida.id) ?? null;
}
