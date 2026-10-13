"""O modelo não favorece nenhum partido: trocar os partidos em todas as entradas troca os
resultados (exatamente nos parâmetros, dentro do erro de simulação nas probabilidades)."""

import pytest

from pipeline.modelo.previsao import Dados, prever


def test_parametros_trocam_de_sinal(dados_sinteticos: Dados, dados_espelhados: Dados) -> None:
    original = prever(dados_sinteticos, 2018)
    espelho = prever(dados_espelhados, 2018)
    for a, b in (
        (original.fundamentos_camara, espelho.fundamentos_camara),
        (original.fundamentos_senado, espelho.fundamentos_senado),
    ):
        assert b.intercepto == pytest.approx(-a.intercepto, abs=1e-9)
        assert b.inclinacao == pytest.approx(a.inclinacao, abs=1e-9)
        assert b.incumbencia == pytest.approx(a.incumbencia, abs=1e-9)
        assert b.sd_corrida == pytest.approx(a.sd_corrida, abs=1e-9)
        assert b.sd_regiao == pytest.approx(a.sd_regiao, abs=1e-9)
        assert b.sd_ano == pytest.approx(a.sd_ano, abs=1e-9)
    assert espelho.ambiente.margem == pytest.approx(-original.ambiente.margem, abs=1e-9)
    assert espelho.ambiente.sd == pytest.approx(original.ambiente.sd, abs=1e-9)
    assert espelho.erro_sondagens.base == pytest.approx(original.erro_sondagens.base, abs=1e-9)


def test_probabilidades_trocam_de_lado(dados_sinteticos: Dados, dados_espelhados: Dados) -> None:
    original = prever(dados_sinteticos, 2018)
    espelho = prever(dados_espelhados, 2018)
    assert espelho.camara.prob_controlo_d == pytest.approx(
        original.camara.prob_controlo_r, abs=0.02
    )
    assert espelho.senado.prob_controlo_d == pytest.approx(
        original.senado.prob_controlo_r, abs=0.02
    )
    por_id = {c.linha.id: c for c in original.camara.corridas + original.senado.corridas}
    for c in espelho.camara.corridas + espelho.senado.corridas:
        o = por_id[c.linha.id]
        assert c.fundamentos == pytest.approx(-o.fundamentos, abs=1e-9)
        assert c.prob_d == pytest.approx(1 - o.prob_d, abs=0.03)
