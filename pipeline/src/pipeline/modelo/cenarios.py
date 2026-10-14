"""Grelha de cenários do ambiente nacional para o site.

Cada cenário corre ``prever`` com os mesmos dados, o mesmo corte e a mesma semente da
previsão publicada, mudando só ``Ajustes.desvio_ambiente`` (o centro do ambiente nacional)
e ``Ajustes.fator_erro_sondagens``. Assim o site mostra o que o simulador publicado diria
noutro ambiente, sem simular no browser com outro motor. A incerteza do ambiente mantém-se
em todos os cenários: um desvio de +3 pontos é "o ambiente estimado está 3 pontos mais
democrata", não "o voto nacional é exatamente esse".
"""

from collections.abc import Sequence
from datetime import date, datetime

import numpy as np

from contratos.base import Fonte, Metadados
from contratos.previsao import (
    Cenario,
    CenariosPrevisao,
    ProbCorridaCenario,
    ResumoCenarioCamara,
)
from pipeline.modelo.previsao import SIMULACOES, Ajustes, Dados, corte_final, prever
from pipeline.modelo.simulacao import ResultadoCamara

DESVIOS_AMBIENTE: tuple[float, ...] = tuple(float(d) for d in range(-8, 9))
FATORES_ERRO_SONDAGENS: tuple[float, ...] = (0.75, 1.0, 1.5)
"""Os mesmos níveis da análise de sensibilidade (mais e menos confiança nas sondagens)."""


def _resumo(resultado: ResultadoCamara) -> ResumoCenarioCamara:
    p10, p50, p90 = np.percentile(resultado.lugares_d, [10, 50, 90])
    return ResumoCenarioCamara(
        prob_controlo_d=resultado.prob_controlo_d,
        prob_controlo_r=resultado.prob_controlo_r,
        lugares_d_mediana=round(float(p50)),
        lugares_d_p10=round(float(p10)),
        lugares_d_p90=round(float(p90)),
    )


def calcular(
    dados: Dados,
    ano: int,
    corte: date,
    ambiente_publicado: tuple[float, str] | None,
    *,
    fontes: Sequence[Fonte],
    gerado_em: datetime,
    codigo_commit: str | None = None,
    desvios: Sequence[float] = DESVIOS_AMBIENTE,
    fatores: Sequence[float] = FATORES_ERRO_SONDAGENS,
) -> CenariosPrevisao:
    cenarios: list[Cenario] = []
    base = None
    for fator in fatores:
        for desvio in desvios:
            previsao = prever(
                dados,
                ano,
                corte=corte,
                ambiente_publicado=ambiente_publicado,
                ajustes=Ajustes(desvio_ambiente=desvio, fator_erro_sondagens=fator),
            )
            if desvio == 0.0 and fator == 1.0:
                base = previsao
            cenarios.append(
                Cenario(
                    desvio_ambiente=desvio,
                    ambiente=previsao.ambiente.margem,
                    fator_erro_sondagens=fator,
                    camara=_resumo(previsao.camara),
                    senado=_resumo(previsao.senado),
                    corridas_senado=tuple(
                        ProbCorridaCenario(id=c.linha.id, prob_d=c.prob_d)
                        for c in previsao.senado.corridas
                    ),
                )
            )
    if base is None:
        raise ValueError("A grelha tem de incluir o modelo publicado (desvio 0, fator 1)")
    return CenariosPrevisao(
        metadados=Metadados(gerado_em=gerado_em, fontes=tuple(fontes)),
        ano=ano,
        corte=base.corte,
        congelada=base.corte >= corte_final(ano),
        simulacoes=SIMULACOES,
        semente=base.semente,
        ambiente_base=base.ambiente.margem,
        desvio_padrao_ambiente=base.ambiente.sd,
        desvios_ambiente=tuple(desvios),
        fatores_erro_sondagens=tuple(fatores),
        cenarios=tuple(cenarios),
        codigo_commit=codigo_commit,
    )
