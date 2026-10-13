"""Projeção da noite: junta as corridas e simula o controlo das duas câmaras.

O desvio ``s`` de cada corrida face à previsão congelada tem uma parte comum a todas as
corridas (o desvio nacional ``v``), uma parte da região do Census e uma parte própria:

    s_r = s0_r + l_r * (v + regiao_r) + n_r

As corridas com votos contados informam ``v`` e as regiões (por pesos de precisão); as
corridas sem votos ficam no prior, deslocadas apenas pelo que as outras já mostraram.
Uma corrida sem feed não é tratada como certa: mantém a incerteza toda da previsão. Cada
simulação sorteia ``v`` e as regiões, depois o desvio de cada corrida e, por fim, a margem
final dada a análise da corrida (``corrida.analisar``).
"""

import math
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime

import numpy as np
import numpy.typing as npt

from contratos.base import Fonte, Metadados
from contratos.noite import (
    DesvioNacionalNoite,
    ProjecaoCorridaNoite,
    ProjecaoNoite,
    ResumoCamaraNoite,
)
from contratos.previsao import PontoDistribuicao, PrevisaoCongresso, PrevisaoCorrida, ResumoCamara
from pipeline.modelo.dados import REGIOES
from pipeline.modelo.noite.corrida import AnaliseCorrida, Parametros, PriorCorrida, analisar
from pipeline.modelo.noite.entrada import Base, Instantaneo, agrupar

SIMULACOES = 20_000
Z_P90 = 1.2815515655446004
ORDEM_REGIOES = ("nordeste", "centro_oeste", "sul", "oeste")
FRACAO_NACIONAL = 0.8
"""Fração máxima da variância prior de uma corrida atribuída ao desvio comum."""

NOTAS = (
    "A projeção parte da previsão congelada e só a atualiza com votos contados.",
    "O voto por contar pode inclinar para qualquer dos lados: a incerteza é simétrica.",
    "Corridas sem votos contados mantêm a incerteza da previsão.",
)


@dataclass(frozen=True, slots=True)
class _Corrida:
    previsao: PrevisaoCorrida
    prior: PriorCorrida
    analise: AnaliseCorrida
    carga: npt.NDArray[np.float64]
    """``l_r`` vezes o indicador (nacional, região)."""

    tau2: float


def _prior(c: PrevisaoCorrida) -> PriorCorrida:
    sd = max((c.margem_p90 - c.margem_p10) / (2 * Z_P90), 0.5)
    return PriorCorrida(c.id, c.estado, c.margem_prevista, sd)


def participacao(ano: int, p: Parametros) -> float:
    return p.participacao_presidencial if ano % 4 == 0 else p.participacao_intercalar


def _preparar(
    previsao: PrevisaoCongresso,
    instantaneo: Instantaneo,
    referencia: Mapping[str, Mapping[str, Base]],
    p: Parametros,
    *,
    sd_nacional: float,
    sd_regiao: float,
) -> list[_Corrida]:
    contagens = agrupar(instantaneo.contagens)
    k = participacao(previsao.ano, p)
    sistematica = sd_nacional**2 + sd_regiao**2
    corridas: list[_Corrida] = []
    for c in previsao.corridas:
        if c.decidida is not None:
            continue
        prior = _prior(c)
        analise = analisar(prior, contagens.get(c.id, []), referencia.get(c.estado, {}), k, p)
        carga_ = min(1.0, math.sqrt(FRACAO_NACIONAL * analise.var_s / sistematica))
        x = np.zeros(1 + len(ORDEM_REGIOES))
        x[0] = carga_
        x[1 + ORDEM_REGIOES.index(REGIOES[c.estado])] = carga_
        tau2 = analise.var_s - carga_**2 * sistematica
        corridas.append(_Corrida(c, prior, analise, x, tau2))
    return corridas


def _comum(
    corridas: Sequence[_Corrida], sd_nacional: float, sd_regiao: float
) -> tuple[npt.NDArray[np.float64], npt.NDArray[np.float64], int]:
    """Posterior normal de (desvio nacional, regiões): média, covariância, corridas usadas."""
    precisao = np.diag([1 / sd_nacional**2] + [1 / sd_regiao**2] * len(ORDEM_REGIOES))
    vetor = np.zeros(1 + len(ORDEM_REGIOES))
    usadas = 0
    for c in corridas:
        a = c.analise
        if a.s_chapeu is None or a.var_chapeu is None:
            continue
        variancia = a.var_chapeu + c.tau2
        precisao += np.outer(c.carga, c.carga) / variancia
        vetor += c.carga * (a.s_chapeu - a.s0) / variancia
        usadas += 1
    covariancia = np.linalg.inv(precisao)
    return covariancia @ vetor, covariancia, usadas


def _margens(
    corridas: Sequence[_Corrida],
    media: npt.NDArray[np.float64],
    covariancia: npt.NDArray[np.float64],
    n: int,
    rng: np.random.Generator,
) -> npt.NDArray[np.float64]:
    """Margens finais simuladas, uma coluna por corrida.

    Os sorteios são antitéticos (cada um tem o seu simétrico em torno da média), o que
    torna a simulação exatamente simétrica entre partidos e reduz o ruído de Monte Carlo.
    """
    metade = n // 2

    def normais(*forma: int) -> npt.NDArray[np.float64]:
        z = rng.standard_normal((metade, *forma))
        return np.concatenate([z, -z])

    comum = media + normais(len(media)) @ np.linalg.cholesky(covariancia).T
    margens = np.empty((2 * metade, len(corridas)))
    for j, c in enumerate(corridas):
        a = c.analise
        centro = a.s0 + comum @ c.carga
        if a.s_chapeu is not None and a.var_chapeu is not None:
            precisao = 1 / c.tau2 + 1 / a.var_chapeu
            centro = (centro / c.tau2 + a.s_chapeu / a.var_chapeu) / precisao
            sd = math.sqrt(1 / precisao)
        else:
            sd = math.sqrt(c.tau2)
        s = centro + sd * normais()
        margens[:, j] = a.alfa + a.beta * s + a.gama * normais()
    return margens


def _resumo(
    resumo: ResumoCamara,
    previsao: PrevisaoCongresso,
    corridas: Sequence[_Corrida],
    margens: npt.NDArray[np.float64],
    desempate: str,
) -> ResumoCamaraNoite:
    certas = sum(
        c.decidida in {"D", "I"}
        for c in previsao.corridas
        if c.camara == resumo.camara and c.decidida is not None
    )
    colunas = [j for j, c in enumerate(corridas) if c.previsao.camara == resumo.camara]
    lugares = resumo.lugares_fora_de_jogo_d + certas + (margens[:, colunas] > 0).sum(axis=1)
    total = resumo.lugares_total
    empate = 2 * lugares == total
    controlo_d = (2 * lugares > total) | (empate & (desempate == "D"))
    controlo_r = (2 * lugares < total) | (empate & (desempate == "R"))
    contagem = np.bincount(lugares, minlength=total + 1) / len(lugares)
    return ResumoCamaraNoite(
        camara=resumo.camara,
        lugares_total=total,
        maioria=resumo.maioria,
        prob_controlo_d=float(controlo_d.mean()),
        prob_controlo_r=float(controlo_r.mean()),
        prob_controlo_d_prior=resumo.prob_controlo_d,
        lugares_d_media=float(lugares.mean()),
        lugares_d_p10=int(np.percentile(lugares, 10, method="inverted_cdf")),
        lugares_d_mediana=int(np.percentile(lugares, 50, method="inverted_cdf")),
        lugares_d_p90=int(np.percentile(lugares, 90, method="inverted_cdf")),
        corridas_com_votos=sum(corridas[j].analise.votos_contados > 0 for j in colunas),
        distribuicao=tuple(
            PontoDistribuicao(lugares=i, probabilidade=float(q))
            for i, q in enumerate(contagem)
            if q > 0
        ),
    )


def _corrida(c: _Corrida, margens: npt.NDArray[np.float64]) -> ProjecaoCorridaNoite:
    a = c.analise
    return ProjecaoCorridaNoite(
        id=c.previsao.id,
        camara=c.previsao.camara,
        votos_contados=a.votos_contados,
        votos_esperados=a.votos_esperados,
        fracao_contada=a.fracao_contada,
        unidades_com_votos=a.unidades_com_votos,
        margem_contada=a.margem_contada,
        margem_prior=c.previsao.margem_prevista,
        margem_projetada=float(margens.mean()),
        margem_p10=float(np.percentile(margens, 10)),
        margem_p90=float(np.percentile(margens, 90)),
        prob_d=float((margens > 0).mean()),
        prob_d_prior=c.previsao.prob_d,
        decidida=False,
    )


def _decidida(c: PrevisaoCorrida) -> ProjecaoCorridaNoite:
    return ProjecaoCorridaNoite(
        id=c.id,
        camara=c.camara,
        votos_contados=0,
        votos_esperados=None,
        fracao_contada=None,
        unidades_com_votos=0,
        margem_contada=None,
        margem_prior=c.margem_prevista,
        margem_projetada=c.margem_prevista,
        margem_p10=c.margem_p10,
        margem_p90=c.margem_p90,
        prob_d=c.prob_d,
        prob_d_prior=c.prob_d,
        decidida=True,
    )


def projetar(
    previsao: PrevisaoCongresso,
    instantaneo: Instantaneo,
    referencia: Mapping[str, Mapping[str, Base]],
    *,
    fontes: Iterable[Fonte],
    gerado_em: datetime,
    desempate: str = "R",
    parametros: Parametros | None = None,
    simulacoes: int = SIMULACOES,
    semente: int = 2026,
    reconstruido: bool = False,
) -> ProjecaoNoite:
    """Projeção num instante; ``desempate`` é o partido do vice-presidente (Senado 50-50).

    ``reconstruido`` marca resultados reconstruídos (ensaio ou repetição).
    """
    p = parametros or Parametros()
    sd_nacional = previsao.ambiente.desvio_padrao
    sd_regiao = next(f.desvio_regiao for f in previsao.fundamentos if f.camara == "camara")
    sd_regiao = max(sd_regiao, 0.5)
    corridas = _preparar(
        previsao, instantaneo, referencia, p, sd_nacional=sd_nacional, sd_regiao=sd_regiao
    )
    media, covariancia, usadas = _comum(corridas, sd_nacional, sd_regiao)
    rng = np.random.default_rng(semente)
    margens = _margens(corridas, media, covariancia, simulacoes, rng)
    por_id = {c.previsao.id: _corrida(c, margens[:, j]) for j, c in enumerate(corridas)}
    linhas = tuple(por_id.get(c.id) or _decidida(c) for c in previsao.corridas)
    return ProjecaoNoite(
        metadados=Metadados(gerado_em=gerado_em, fontes=tuple(fontes)),
        ano=previsao.ano,
        instante=instantaneo.instante,
        corte_prior=previsao.corte,
        prior_congelado=previsao.congelada,
        reconstruido=reconstruido,
        simulacoes=simulacoes,
        semente=semente,
        desvio_nacional=DesvioNacionalNoite(
            media=float(media[0]),
            desvio_padrao=float(math.sqrt(covariancia[0, 0])),
            corridas_informativas=usadas,
        ),
        camara=_resumo(previsao.camara, previsao, corridas, margens, desempate),
        senado=_resumo(previsao.senado, previsao, corridas, margens, desempate),
        corridas=linhas,
        notas=NOTAS,
    )
