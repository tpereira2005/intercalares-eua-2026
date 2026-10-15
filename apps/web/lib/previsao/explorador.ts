/**
 * Explorador de cenários e registo de alterações da previsão (contratos CenariosPrevisao e
 * AlteracoesPrevisao, publicados pelo modelo na Release `dados-previsao`).
 *
 * Os cenários já vêm simulados pelo modelo: aqui só se escolhe o da grelha que
 * corresponde à deslocação do ambiente e ao fator de erro pedidos.
 */

import type {
  AlteracoesPrevisao,
  CenariosPrevisao,
  PrevisaoCongresso,
} from "@intercalares/contratos";
import type { Camara } from "./vista.ts";

export interface ResumoCenario {
  probD: number;
  probR: number;
  mediana: number;
  p10: number;
  p90: number;
}

export interface CenarioVista {
  desvio: number;
  ambiente: number;
  fator: number;
  camara: ResumoCenario;
  senado: ResumoCenario;
  /** Probabilidade de vitória democrata de cada corrida ao Senado, por identificador. */
  corridasSenado: Record<string, number>;
}

export interface VistaCenarios {
  corte: string;
  congelada: boolean;
  commit: string | null;
  simulacoes: number;
  fontes: { nome: string; url: string }[];
  ambienteBase: number;
  desvioPadraoAmbiente: number;
  desvios: number[];
  fatores: number[];
  cenarios: CenarioVista[];
}

function resumo(r: CenariosPrevisao["cenarios"][number][Camara]): ResumoCenario {
  return {
    probD: r.prob_controlo_d,
    probR: r.prob_controlo_r,
    mediana: r.lugares_d_mediana,
    p10: r.lugares_d_p10,
    p90: r.lugares_d_p90,
  };
}

export function construirVistaCenarios(dados: CenariosPrevisao): VistaCenarios {
  return {
    corte: dados.corte,
    congelada: dados.congelada,
    commit: dados.codigo_commit ?? null,
    simulacoes: dados.simulacoes,
    fontes: dados.metadados.fontes.map((f) => ({ nome: f.nome, url: f.url })),
    ambienteBase: dados.ambiente_base,
    desvioPadraoAmbiente: dados.desvio_padrao_ambiente,
    desvios: [...dados.desvios_ambiente].sort((a, b) => a - b),
    fatores: [...dados.fatores_erro_sondagens].sort((a, b) => a - b),
    cenarios: dados.cenarios.map((c) => ({
      desvio: c.desvio_ambiente,
      ambiente: c.ambiente,
      fator: c.fator_erro_sondagens,
      camara: resumo(c.camara),
      senado: resumo(c.senado),
      corridasSenado: Object.fromEntries(c.corridas_senado.map((r) => [r.id, r.prob_d])),
    })),
  };
}

const IGUAL = 1e-6;

/**
 * O cenário central da grelha (sem deslocação, erro das sondagens como no modelo) tem de
 * dar a previsão publicada, com o mesmo corte e o mesmo código. Se não der, os cenários
 * vêm de outra corrida do modelo e não se mostram.
 */
export function cenariosBatemCerto(
  cenarios: CenariosPrevisao,
  previsao: PrevisaoCongresso,
): boolean {
  if (cenarios.ano !== previsao.ano || cenarios.corte !== previsao.corte) return false;
  if ((cenarios.codigo_commit ?? null) !== (previsao.codigo_commit ?? null)) return false;
  if (Math.abs(cenarios.ambiente_base - previsao.ambiente.margem) > IGUAL) return false;
  const base = cenarios.cenarios.find(
    (c) => Math.abs(c.desvio_ambiente) < IGUAL && Math.abs(c.fator_erro_sondagens - 1) < IGUAL,
  );
  return (
    base !== undefined &&
    Math.abs(base.camara.prob_controlo_d - previsao.camara.prob_controlo_d) < IGUAL &&
    Math.abs(base.senado.prob_controlo_d - previsao.senado.prob_controlo_d) < IGUAL
  );
}

/** Cenário da grelha com esta deslocação e este fator; `null` se não existir. */
export function obterCenario(
  vista: VistaCenarios,
  desvio: number,
  fator: number,
): CenarioVista | null {
  return (
    vista.cenarios.find(
      (c) => Math.abs(c.desvio - desvio) < IGUAL && Math.abs(c.fator - fator) < IGUAL,
    ) ?? null
  );
}

/** O cenário publicado: deslocação 0 e fator 1 (ou o mais próximo de 1 na grelha). */
export function cenarioPublicado(vista: VistaCenarios): CenarioVista | null {
  const fator = vista.fatores.reduce<number | null>(
    (melhor, f) => (melhor === null || Math.abs(f - 1) < Math.abs(melhor - 1) ? f : melhor),
    null,
  );
  return fator === null ? null : obterCenario(vista, 0, fator);
}

/**
 * Deslocação mais pequena (em valor absoluto) a partir da qual a câmara passa para o outro
 * lado, com o fator dado: o primeiro cenário em que o favorito publicado deixa de o ser.
 * `null` se nenhum cenário da grelha o vira.
 */
export function viragem(vista: VistaCenarios, camara: Camara, fator: number): number | null {
  const base = obterCenario(vista, 0, fator);
  if (!base) return null;
  const favoritoD = base[camara].probD >= 0.5;
  const candidatos = vista.cenarios
    .filter((c) => Math.abs(c.fator - fator) < IGUAL && c[camara].probD >= 0.5 !== favoritoD)
    .map((c) => c.desvio)
    .sort((a, b) => Math.abs(a) - Math.abs(b));
  return candidatos[0] ?? null;
}

export interface AlteracaoVista {
  data: string;
  descricao: string;
  pr: string;
  camara: { antes: number | null; depois: number };
  senado: { antes: number | null; depois: number };
}

export interface VistaAlteracoes {
  fontes: { nome: string; url: string }[];
  /** Da mais recente para a mais antiga. */
  lista: AlteracaoVista[];
}

export function construirAlteracoes(dados: AlteracoesPrevisao): VistaAlteracoes {
  const lista = dados.alteracoes
    .map((a, i) => ({ a, i }))
    .sort((x, y) => y.a.data.localeCompare(x.a.data) || y.i - x.i)
    .map(({ a }) => ({
      data: a.data,
      descricao: a.descricao,
      pr: a.pr_url,
      camara: { antes: a.camara.antes ?? null, depois: a.camara.depois },
      senado: { antes: a.senado.antes ?? null, depois: a.senado.depois },
    }));
  return { fontes: dados.metadados.fontes.map((f) => ({ nome: f.nome, url: f.url })), lista };
}
