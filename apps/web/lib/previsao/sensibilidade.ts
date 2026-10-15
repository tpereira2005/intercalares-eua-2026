/**
 * Análise de sensibilidade da previsão (contrato SensibilidadePrevisao, asset
 * `sensibilidade-2026.json` da Release `dados-previsao`): cada variante muda uma
 * escolha do modelo e volta a correr a simulação. A primeira é sempre o modelo
 * publicado e tem de coincidir com a previsão; as outras comparam-se com ela.
 */

import type {
  PrevisaoCongresso,
  ResumoSensibilidade,
  SensibilidadePrevisao,
} from "@intercalares/contratos";

const IGUAL = 1e-6;

export interface ResumoVariante {
  probD: number;
  /** Diferença de `probD` face ao modelo publicado, em fração. */
  variacao: number;
  lugaresMediana: number;
  lugaresP10: number;
  lugaresP90: number;
}

export interface VarianteVista {
  nome: string;
  descricao: string;
  /** Margem nacional D−R, em pontos. */
  ambiente: number;
  camara: ResumoVariante;
  senado: ResumoVariante;
}

export interface VistaSensibilidade {
  corte: string;
  fontes: { nome: string; url: string }[];
  publicada: VarianteVista;
  /** Variantes pela ordem do ficheiro, sem o modelo publicado. */
  variantes: VarianteVista[];
}

/**
 * Só se mostra a sensibilidade calculada sobre a mesma previsão que está publicada:
 * mesmo ano, corte e commit, e a primeira variante com as probabilidades publicadas.
 */
export function sensibilidadeBateCerto(
  dados: SensibilidadePrevisao,
  previsao: PrevisaoCongresso,
): boolean {
  if (dados.ano !== previsao.ano || dados.corte !== previsao.corte) return false;
  if ((dados.codigo_commit ?? null) !== (previsao.codigo_commit ?? null)) return false;
  const [publicada] = dados.variantes;
  return (
    Math.abs(publicada.ambiente - previsao.ambiente.margem) < IGUAL &&
    Math.abs(publicada.camara.prob_controlo_d - previsao.camara.prob_controlo_d) < IGUAL &&
    Math.abs(publicada.senado.prob_controlo_d - previsao.senado.prob_controlo_d) < IGUAL
  );
}

function resumo(r: ResumoSensibilidade, base: ResumoSensibilidade): ResumoVariante {
  return {
    probD: r.prob_controlo_d,
    variacao: r.prob_controlo_d - base.prob_controlo_d,
    lugaresMediana: r.lugares_d_mediana,
    lugaresP10: r.lugares_d_p10,
    lugaresP90: r.lugares_d_p90,
  };
}

export function construirVistaSensibilidade(dados: SensibilidadePrevisao): VistaSensibilidade {
  const [base, ...resto] = dados.variantes;
  const vista = (v: SensibilidadePrevisao["variantes"][number]): VarianteVista => ({
    nome: v.nome,
    descricao: v.descricao,
    ambiente: v.ambiente,
    camara: resumo(v.camara, base.camara),
    senado: resumo(v.senado, base.senado),
  });
  return {
    corte: dados.corte,
    fontes: dados.metadados.fontes.map((f) => ({ nome: f.nome, url: f.url })),
    publicada: vista(base),
    variantes: resto.map(vista),
  };
}
