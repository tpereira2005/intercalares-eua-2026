"""Estimação com dados sintéticos: recupera a regra que os gerou e só usa o passado."""

import pytest

from pipeline.modelo.estimacao import erro_quadratico_medio
from pipeline.modelo.previsao import Dados, estimar, prever


def test_fundamentos_recuperam_os_parametros(dados_sinteticos: Dados) -> None:
    fund, _ = estimar(dados_sinteticos, 2018, "camara")
    # Margem gerada com 1,8 x PVI e 6 pontos de incumbência (PVI no modelo é o dobro).
    assert fund.inclinacao == pytest.approx(0.9, abs=0.08)
    assert fund.incumbencia == pytest.approx(6.0, abs=1.0)
    assert fund.sd_corrida == pytest.approx(7.0, abs=1.0)


def test_so_usa_anos_anteriores(dados_sinteticos: Dados) -> None:
    previsao = prever(dados_sinteticos, 2014)
    assert previsao.anos_treino == (2008, 2010, 2012)


def test_erro_quadratico_medio_sem_sinal() -> None:
    assert erro_quadratico_medio([3.0, -3.0]) == pytest.approx(3.0)
    assert erro_quadratico_medio([-4.0]) == erro_quadratico_medio([4.0])
