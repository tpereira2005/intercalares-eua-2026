"""Projeção da noite: junta as corridas e simula o controlo das duas câmaras.

A estrutura de erros é exatamente a da previsão congelada (``simulacao.py``), reconstruída
a partir dos parâmetros publicados. A margem final de cada corrida é

    margem_r = centro_r + L_r · F + n_r

em que ``F`` são os fatores comuns da previsão: o erro nacional (t de Student com 5 graus
de liberdade), o erro do ano na Câmara, o erro do ano nos fundamentos do Senado, o erro
comum das sondagens do Senado e as quatro regiões do Census. As cargas ``L_r`` são as da
simulação da previsão (no Senado dependem do peso das sondagens) e ``n_r`` é o erro
próprio da corrida. Por isso, antes de haver votos, a projeção é a previsão congelada,
corrida a corrida e no controlo das câmaras (a menos do erro de Monte Carlo).

As corridas com votos contados informam ``F`` por pesos de precisão; as corridas sem votos
ficam no prior, deslocadas apenas pelo que as outras já mostraram, e mantêm a incerteza
toda da previsão. A t de Student escreve-se como uma mistura de normais: cada simulação
sorteia a escala do erro nacional do prior, pesa-a pela verosimilhança dos votos contados
(amostragem por importância com reamostragem sistemática) e sorteia ``F`` da normal
condicionada a essa escala. Por fim sorteia o desvio de cada corrida e a margem final
dada a análise da corrida (``corrida.analisar``).
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
from contratos.previsao import (
    ParametrosFundamentos,
    PontoDistribuicao,
    PrevisaoCongresso,
    PrevisaoCorrida,
    ResumoCamara,
)
from pipeline.modelo.dados import REGIOES
from pipeline.modelo.noite.corrida import AnaliseCorrida, Parametros, PriorCorrida, analisar
from pipeline.modelo.noite.entrada import Base, Instantaneo, agrupar
from pipeline.modelo.simulacao import GRAUS_LIBERDADE

SIMULACOES = 20_000
Z_P90 = 1.2815515655446004
ORDEM_REGIOES = ("nordeste", "centro_oeste", "sul", "oeste")
NACIONAL, ANO_CAMARA, ANO_SENADO, SONDAGENS_SENADO = range(4)
FATORES = 4 + len(ORDEM_REGIOES)
SD_MINIMO = 1e-3
"""Desvio mínimo de um fator ou de um erro próprio (evita precisões infinitas)."""

NOTAS = (
    "A projeção parte da previsão congelada e só a atualiza com votos contados.",
    "O voto por contar pode inclinar para qualquer dos lados: a incerteza é simétrica.",
    "Corridas sem votos contados mantêm a incerteza da previsão.",
)


@dataclass(frozen=True, slots=True)
class Estrutura:
    """Desvios-padrão dos fatores comuns da previsão (o nacional é o da t de Student)."""

    sd: npt.NDArray[np.float64]
    var_fundamentos: dict[str, float]
    """Variância do erro próprio nos fundamentos, por câmara."""

    erro_base: float
    erro_por_instituto: float
    ligacao_nacional: float


def estrutura(previsao: PrevisaoCongresso) -> Estrutura:
    fundamentos: dict[str, ParametrosFundamentos] = {f.camara: f for f in previsao.fundamentos}
    camara, senado = fundamentos["camara"], fundamentos["senado"]
    erro = previsao.erro_sondagens
    sd_ambiente = previsao.ambiente.desvio_padrao
    # Parte do erro comum das sondagens que não acompanha o voto genérico (como na
    # simulação da previsão).
    residual = math.sqrt(max(erro.desvio_ano**2 - (erro.ligacao_nacional * sd_ambiente) ** 2, 0))
    sd = np.array(
        [sd_ambiente, camara.desvio_ano, senado.desvio_ano, residual]
        + [camara.desvio_regiao] * len(ORDEM_REGIOES)
    )
    return Estrutura(
        sd=np.maximum(sd, SD_MINIMO),
        var_fundamentos={"camara": camara.desvio_corrida**2, "senado": senado.desvio_corrida**2},
        erro_base=erro.erro_base,
        erro_por_instituto=erro.erro_por_instituto,
        ligacao_nacional=erro.ligacao_nacional,
    )


def decompor(c: PrevisaoCorrida, e: Estrutura) -> tuple[float, npt.NDArray[np.float64], float]:
    """Centro, cargas nos fatores comuns e variância própria de uma corrida disputada."""
    carga = np.zeros(FATORES)
    carga[4 + ORDEM_REGIOES.index(REGIOES[c.estado])] = 1.0
    var_f = e.var_fundamentos[c.camara]
    if c.camara == "camara":
        carga[NACIONAL] = carga[ANO_CAMARA] = 1.0
        return c.margem_fundamentos, carga, var_f
    w = c.peso_sondagens if c.margem_sondagens is not None else 0.0
    carga[NACIONAL] = (1 - w) + w * e.ligacao_nacional
    carga[ANO_SENADO] = 1 - w
    carga[SONDAGENS_SENADO] = w
    if c.margem_sondagens is None:
        return c.margem_fundamentos, carga, var_f
    var_p = e.erro_base**2 + e.erro_por_instituto**2 / max(c.institutos, 1)
    centro = (1 - w) * c.margem_fundamentos + w * c.margem_sondagens
    return centro, carga, var_f * var_p / (var_f + var_p)


@dataclass(frozen=True, slots=True)
class _Corrida:
    previsao: PrevisaoCorrida
    prior: PriorCorrida
    analise: AnaliseCorrida
    carga: npt.NDArray[np.float64]
    tau2: float
    """Variância do desvio da corrida que não vem dos fatores comuns."""


def participacao(ano: int, p: Parametros) -> float:
    return p.participacao_presidencial if ano % 4 == 0 else p.participacao_intercalar


def _preparar(
    previsao: PrevisaoCongresso,
    instantaneo: Instantaneo,
    referencia: Mapping[str, Mapping[str, Base]],
    p: Parametros,
    e: Estrutura,
) -> list[_Corrida]:
    contagens = agrupar(instantaneo.contagens)
    k = participacao(previsao.ano, p)
    corridas: list[_Corrida] = []
    for c in previsao.corridas:
        if c.decidida is not None:
            continue
        centro, carga, var_propria = decompor(c, e)
        comum = float(carga**2 @ e.sd**2)
        prior = PriorCorrida(c.id, c.estado, centro, math.sqrt(comum + var_propria))
        analise = analisar(
            prior,
            contagens.get(c.id, []),
            referencia.get(c.estado, {}),
            k,
            p,
            parcial=c.estado in instantaneo.parciais,
        )
        tau2 = max(analise.var_s - comum, SD_MINIMO**2)
        corridas.append(_Corrida(c, prior, analise, carga, tau2))
    return corridas


@dataclass(frozen=True, slots=True)
class _Comum:
    """Sorteios dos fatores comuns (antitéticos) e o resumo do desvio nacional."""

    sorteios: npt.NDArray[np.float64]
    media_nacional: float
    sd_nacional: float
    informativas: int


def _comum(
    corridas: Sequence[_Corrida], e: Estrutura, metade: int, rng: np.random.Generator
) -> _Comum:
    """Fatores comuns condicionados às corridas com votos.

    Dada a escala ``lambda`` do erro nacional, o prior de ``F`` é normal e a posterior
    também. Cada sorteio da escala pesa-se pela verosimilhança marginal das corridas
    informativas, e a reamostragem sistemática escolhe ``metade`` escalas; sem votos os
    pesos são iguais e cada escala sai exatamente uma vez (o prior da previsão).
    """
    gl = GRAUS_LIBERDADE
    escala = gl / rng.chisquare(gl, metade) * (gl - 2) / gl
    var_prior = np.tile(e.sd**2, (metade, 1))
    var_prior[:, NACIONAL] *= escala

    informacao = np.zeros((FATORES, FATORES))
    vetor = np.zeros(FATORES)
    usadas = 0
    for c in corridas:
        a = c.analise
        if a.s_chapeu is None or a.var_chapeu is None:
            continue
        variancia = a.var_chapeu + c.tau2
        informacao += np.outer(c.carga, c.carga) / variancia
        vetor += c.carga * (a.s_chapeu - a.s0) / variancia
        usadas += 1

    precisao = informacao[None, :, :] + np.einsum("ij,ki->kij", np.eye(FATORES), 1 / var_prior)
    covariancia = np.linalg.inv(precisao)
    media = covariancia @ vetor
    if usadas:
        _, logdet_p = np.linalg.slogdet(precisao)
        logpeso = -0.5 * (np.log(var_prior).sum(axis=1) + logdet_p - media @ vetor)
        pesos = np.exp(logpeso - logpeso.max())
        pesos /= pesos.sum()
    else:
        pesos = np.full(metade, 1 / metade)
    posicoes = (rng.random() + np.arange(metade)) / metade
    escolhidos = np.minimum(np.searchsorted(np.cumsum(pesos), posicoes), metade - 1)

    z = rng.standard_normal((metade, FATORES))
    desvio = np.einsum("kij,kj->ki", np.linalg.cholesky(covariancia[escolhidos]), z)
    centro = media[escolhidos]
    sorteios = np.concatenate([centro + desvio, centro - desvio])
    m = float(pesos @ media[:, NACIONAL])
    segundo = float(pesos @ (covariancia[:, NACIONAL, NACIONAL] + media[:, NACIONAL] ** 2))
    return _Comum(sorteios, m, math.sqrt(max(segundo - m**2, 0.0)), usadas)


def _margens(
    corridas: Sequence[_Corrida],
    comum: npt.NDArray[np.float64],
    rng: np.random.Generator,
) -> npt.NDArray[np.float64]:
    """Margens finais simuladas, uma coluna por corrida.

    Os sorteios são antitéticos (cada um tem o seu simétrico em torno da média), o que
    torna a simulação exatamente simétrica entre partidos e reduz o ruído de Monte Carlo.
    """
    metade = len(comum) // 2

    def normais() -> npt.NDArray[np.float64]:
        z = rng.standard_normal(metade)
        return np.concatenate([z, -z])

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
    corridas = _preparar(previsao, instantaneo, referencia, p, estrutura(previsao))
    rng = np.random.default_rng(semente)
    comum = _comum(corridas, estrutura(previsao), simulacoes // 2, rng)
    margens = _margens(corridas, comum.sorteios, rng)
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
            media=comum.media_nacional,
            desvio_padrao=comum.sd_nacional,
            corridas_informativas=comum.informativas,
        ),
        camara=_resumo(previsao.camara, previsao, corridas, margens, desempate),
        senado=_resumo(previsao.senado, previsao, corridas, margens, desempate),
        corridas=linhas,
        notas=NOTAS,
    )
