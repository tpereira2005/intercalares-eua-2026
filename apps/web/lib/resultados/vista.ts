/**
 * Vista da noite eleitoral: contagem oficial por corrida (contrato ResultadosParciais)
 * ao lado da previsão congelada (PrevisaoCongresso).
 *
 * Não há aqui projeções nem chamadas de vencedor: só se somam os votos que cada
 * estado publica, unidade a unidade, e se calcula a margem contada até ao momento
 * (docs/metodologia/resultados.md). As probabilidades ao vivo serão do estimador
 * do modelo, quando o seu contrato existir.
 */

import type { CodigoEstado, ResultadosParciais } from "@intercalares/contratos";
import type { CorridaNoite, VistaNoite } from "../noite/vista.ts";
import { categoria, type CorridaVista, type VistaPrevisao } from "../previsao/vista.ts";

/**
 * Estados recolhidos na noite (workflow Resultados; docs/metodologia/resultados.md). Na
 * Geórgia e no Alasca, a fonte só dá o total de cada corrida; no Texas, só se acompanha
 * o condado de Harris. A Carolina do Sul e o Iowa ficam de fora: bloqueiam o Actions.
 */
export const COBERTURA_AO_VIVO: readonly {
  estado: CodigoEstado;
  soTotal: boolean;
  parcial: boolean;
}[] = [
  { estado: "NC", soTotal: false, parcial: false },
  { estado: "FL", soTotal: false, parcial: false },
  { estado: "GA", soTotal: true, parcial: false },
  { estado: "AK", soTotal: true, parcial: false },
  { estado: "TX", soTotal: false, parcial: true },
];

/** Estados com contagem ao vivo possível: as suas corridas da Câmara podem aparecer. */
const ESTADOS_AO_VIVO = new Set<CodigoEstado>(COBERTURA_AO_VIVO.map((c) => c.estado));

export interface ContagemCorrida {
  id: string;
  estado: CodigoEstado;
  votosD: number;
  votosR: number;
  votosOutros: number;
  total: number;
  /** (D − R) / total, em fração; `null` sem votos. */
  margem: number | null;
  /** Secções (ou condados) com resultados, quando todas as unidades as indicam. */
  seccoes: { reportadas: number; totais: number } | null;
  /** A fonte só publica o total da corrida (sem condados). */
  soTotal: boolean;
  /** Hora mais recente declarada pela fonte numa das unidades. */
  atualizadoEm: string | null;
}

export interface LinhaResultados {
  id: string;
  estado: CodigoEstado;
  senado: boolean;
  contagem: ContagemCorrida | null;
  previsao: CorridaVista | null;
  /** Projeção ao vivo do modelo para a corrida, quando a projeção é do mesmo ano. */
  projecao: CorridaNoite | null;
}

export interface EstadoCobertura {
  estado: CodigoEstado;
  soTotal: boolean;
  /** Só alguns condados; `nota` explica quais, quando a fonte a dá. */
  parcial: boolean;
  nota: string | null;
  corridas: number;
  atualizadoEm: string | null;
}

export interface VistaResultados {
  ano: number;
  instante: string;
  geradoEm: string;
  /** Ensaio: ordem reconstruída, ou ficheiro de outro ano que não o da previsão. */
  ensaio: boolean;
  fontes: { nome: string; url: string }[];
  /** Corridas com contagem: Senado primeiro, depois a Câmara do mais renhido ao menos. */
  aoVivo: LinhaResultados[];
  /** Senado e distritos não sólidos da previsão que não têm contagem ao vivo. */
  semDados: LinhaResultados[];
  cobertura: EstadoCobertura[];
  previsaoCongelada: boolean | null;
  cortePrevisao: string | null;
}

/** Soma as unidades de cada corrida, pela ordem em que aparecem no ficheiro. */
export function contarCorridas(parciais: ResultadosParciais): ContagemCorrida[] {
  const grupos = new Map<string, ResultadosParciais["unidades"]>();
  for (const u of parciais.unidades) {
    const lista = grupos.get(u.corrida);
    if (lista) lista.push(u);
    else grupos.set(u.corrida, [u]);
  }
  return [...grupos].map(([id, unidades]) => {
    let votosD = 0;
    let votosR = 0;
    let votosOutros = 0;
    let reportadas = 0;
    let totais = 0;
    let comSeccoes = true;
    let atualizadoEm: string | null = null;
    for (const u of unidades) {
      votosD += u.votos_d;
      votosR += u.votos_r;
      votosOutros += u.votos_outros;
      if (u.seccoes_reportadas === null || u.seccoes_totais === null) comSeccoes = false;
      else {
        reportadas += u.seccoes_reportadas;
        totais += u.seccoes_totais;
      }
      if (
        u.atualizado_em !== null &&
        (atualizadoEm === null || Date.parse(u.atualizado_em) > Date.parse(atualizadoEm))
      ) {
        atualizadoEm = u.atualizado_em;
      }
    }
    const total = votosD + votosR + votosOutros;
    return {
      id,
      estado: id.slice(0, 2) as CodigoEstado,
      votosD,
      votosR,
      votosOutros,
      total,
      margem: total > 0 ? (votosD - votosR) / total : null,
      seccoes: comSeccoes && totais > 0 ? { reportadas, totais } : null,
      soTotal: unidades.every((u) => u.unidade === "total"),
      atualizadoEm,
    };
  });
}

/** Distância a 50%: quanto menor, mais renhida a corrida na previsão. */
function proximidade(l: LinhaResultados): number {
  return l.previsao ? Math.abs(l.previsao.probD - 0.5) : 1;
}

function ordenar(a: LinhaResultados, b: LinhaResultados): number {
  if (a.senado !== b.senado) return a.senado ? -1 : 1;
  return proximidade(a) - proximidade(b) || a.id.localeCompare(b.id);
}

function naoSolida(c: CorridaVista): boolean {
  const cat = categoria(c.probD);
  return c.decidida === null && cat !== "solidaD" && cat !== "solidaR";
}

/** O que a vista dos resultados usa da previsão. */
export type PrevisaoResultados = Pick<
  VistaPrevisao,
  "ano" | "congelada" | "corte" | "corridasSenado" | "corridasCamara"
>;

/**
 * A previsão reduzida ao que a noite pode mostrar: o Senado, os distritos não sólidos e
 * os distritos dos estados com contagem ao vivo. É o que segue para o browser, que
 * reconstrói a vista a cada consulta da API, e dá a mesma vista que a previsão completa.
 */
export function previsaoParaResultados(previsao: VistaPrevisao): PrevisaoResultados {
  return {
    ano: previsao.ano,
    congelada: previsao.congelada,
    corte: previsao.corte,
    corridasSenado: previsao.corridasSenado,
    corridasCamara: previsao.corridasCamara.filter(
      (c) => naoSolida(c) || ESTADOS_AO_VIVO.has(c.estado),
    ),
  };
}

export function construirVistaResultados(
  parciais: ResultadosParciais,
  previsao: PrevisaoResultados | null,
  noite: VistaNoite | null = null,
): VistaResultados {
  // A projeção só se junta à contagem do mesmo ano e da mesma natureza (real ou ensaio).
  const projecoes =
    noite?.ano === parciais.ano && noite.reconstruido === parciais.reconstruido
      ? noite.corridas
      : new Map<string, CorridaNoite>();
  // Um ensaio de outro ano não se cruza com a previsão de 2026: os distritos mudaram.
  const ensaio = parciais.reconstruido || (previsao !== null && parciais.ano !== previsao.ano);
  const previstas = new Map<string, CorridaVista>();
  if (previsao && !ensaio) {
    for (const c of [...previsao.corridasSenado, ...previsao.corridasCamara])
      previstas.set(c.id, c);
  }
  const contagens = contarCorridas(parciais);
  const comContagem = new Set(contagens.map((c) => c.id));
  const aoVivo = contagens
    .map((c) => ({
      id: c.id,
      estado: c.estado,
      senado: c.id.includes("-S"),
      contagem: c,
      previsao: previstas.get(c.id) ?? null,
      projecao: projecoes.get(c.id) ?? null,
    }))
    .sort(ordenar);
  const semDados = previsao
    ? [...previsao.corridasSenado, ...previsao.corridasCamara.filter(naoSolida)]
        .filter((c) => !comContagem.has(c.id) || ensaio)
        .map((c) => ({
          id: c.id,
          estado: c.estado,
          senado: c.camara === "senado",
          contagem: null,
          previsao: c,
          projecao: ensaio ? null : (projecoes.get(c.id) ?? null),
        }))
        .sort(ordenar)
    : [];
  // Um estado com contagem fora da lista (num ensaio, por exemplo) também aparece.
  const extra = [...new Set(contagens.map((c) => c.estado))]
    .filter((e) => !ESTADOS_AO_VIVO.has(e))
    .map((estado) => ({ estado, soTotal: false, parcial: false }));
  const cobertura = [...COBERTURA_AO_VIVO, ...extra].map(({ estado, soTotal, parcial }) => {
    const doEstado = contagens.filter((c) => c.estado === estado);
    const horas = doEstado.flatMap((c) => (c.atualizadoEm ? [c.atualizadoEm] : []));
    return {
      estado,
      soTotal,
      parcial,
      nota: (parciais.cobertura_parcial ?? []).find((p) => p.estado === estado)?.nota ?? null,
      corridas: doEstado.length,
      atualizadoEm: horas.reduce<string | null>(
        (max, h) => (max === null || Date.parse(h) > Date.parse(max) ? h : max),
        null,
      ),
    };
  });
  return {
    ano: parciais.ano,
    instante: parciais.instante,
    geradoEm: parciais.metadados.gerado_em,
    ensaio,
    fontes: parciais.metadados.fontes
      .filter((f, i, todas) => todas.findIndex((g) => g.nome === f.nome) === i)
      .map((f) => ({ nome: f.nome, url: f.url })),
    aoVivo,
    semDados,
    cobertura,
    previsaoCongelada: previsao ? previsao.congelada : null,
    cortePrevisao: previsao ? previsao.corte : null,
  };
}
