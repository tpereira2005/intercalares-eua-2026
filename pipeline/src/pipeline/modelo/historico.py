"""Histórico diário da previsão, para os gráficos de evolução do site.

Cada execução acrescenta (ou substitui, se a data de corte se repetir) uma entrada com o
resumo das duas câmaras e a probabilidade e margem de cada corrida.
"""

from contratos.previsao import (
    DiaHistorico,
    HistoricoPrevisao,
    PontoHistoricoCamara,
    PontoHistoricoCorrida,
    PrevisaoCongresso,
    ResumoCamara,
)

CASAS = 4
"""Casas decimais guardadas: chegam para os gráficos e mantêm o ficheiro pequeno."""


def _camara(resumo: ResumoCamara) -> PontoHistoricoCamara:
    return PontoHistoricoCamara(
        prob_controlo_d=round(resumo.prob_controlo_d, CASAS),
        prob_controlo_r=round(resumo.prob_controlo_r, CASAS),
        lugares_d_mediana=resumo.lugares_d_mediana,
        lugares_d_p10=resumo.lugares_d_p10,
        lugares_d_p90=resumo.lugares_d_p90,
    )


def dia(previsao: PrevisaoCongresso) -> DiaHistorico:
    return DiaHistorico(
        corte=previsao.corte,
        congelada=previsao.congelada,
        ambiente_margem=round(previsao.ambiente.margem, CASAS),
        camara=_camara(previsao.camara),
        senado=_camara(previsao.senado),
        corridas=tuple(
            PontoHistoricoCorrida(
                id=c.id,
                prob_d=round(c.prob_d, CASAS),
                margem_prevista=round(c.margem_prevista, 2),
            )
            for c in previsao.corridas
        ),
    )


def acrescentar(
    historico: HistoricoPrevisao | None, previsao: PrevisaoCongresso
) -> HistoricoPrevisao:
    """Junta a previsão ao histórico, uma entrada por data de corte, por ordem cronológica."""
    dias = {d.corte: d for d in historico.dias} if historico is not None else {}
    if historico is not None and historico.ano != previsao.ano:
        raise ValueError(f"Histórico de {historico.ano}, previsão de {previsao.ano}")
    dias[previsao.corte] = dia(previsao)
    return HistoricoPrevisao(
        metadados=previsao.metadados,
        ano=previsao.ano,
        dias=tuple(dias[c] for c in sorted(dias)),
    )
