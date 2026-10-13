"""Scorecard da previsão congelada: métricas, simetria, contagem lenta e backtests reais."""

import math
from dataclasses import replace
from datetime import UTC, datetime

import pytest

from contratos.base import Fonte
from contratos.previsao import PrevisaoCongresso
from pipeline.jobs.avaliacao_previsao import backtest
from pipeline.modelo.avaliacao import Resultado, avaliar_previsao, calibracao, resultados_de_linhas
from pipeline.modelo.dados import linha_modelo
from pipeline.modelo.previsao import Dados, prever
from pipeline.modelo.publicar import montar

AGORA = datetime(2018, 11, 30, tzinfo=UTC)
FONTE = Fonte(nome="Sintética", url="https://example.org/", obtida_em=AGORA)


def _publicada(dados: Dados) -> PrevisaoCongresso:
    return montar(prever(dados, 2018), fontes=[FONTE], gerado_em=AGORA)


def _resultados(dados: Dados) -> dict[str, Resultado]:
    linhas = [ln for c in dados.corridas[2018] if (ln := linha_modelo(c)) is not None]
    return resultados_de_linhas(linhas)


def test_calibracao_usa_o_favorito_e_e_simetrica() -> None:
    pares = [(0.9, True), (0.2, False), (0.55, False), (0.97, True)]
    espelho = [(1 - p, not g) for p, g in pares]
    assert calibracao(pares) == calibracao(espelho)
    faixas = {f.limite_inferior: f for f in calibracao(pares)}
    assert faixas[0.8].corridas == 1  # 0,2 para D é 0,8 para o favorito R, que ganhou
    assert faixas[0.8].frequencia == 1.0
    assert faixas[0.5].frequencia == 0.0


def test_metricas_numa_previsao_sintetica(dados_sinteticos: Dados) -> None:
    publicada = _publicada(dados_sinteticos)
    resultados = _resultados(dados_sinteticos)
    avaliacao = avaliar_previsao(publicada, resultados, fontes=[FONTE], gerado_em=AGORA)
    camara = next(c for c in avaliacao.camaras if c.camara == "camara")
    corridas = [c for c in publicada.corridas if c.camara == "camara"]
    brier = sum((c.prob_d - (resultados[c.id].vencedor == "D")) ** 2 for c in corridas) / len(
        corridas
    )
    assert camara.brier == pytest.approx(brier)
    assert 0 < camara.brier < 0.25
    assert camara.log_loss > camara.brier
    assert camara.corridas_por_decidir == ()
    assert camara.lugares_d_reais == sum(
        r.vencedor == "D" for i, r in resultados.items() if "-S" not in i
    )
    assert sum(f.corridas for f in camara.calibracao) == camara.corridas_avaliadas
    copia = type(avaliacao).model_validate_json(avaliacao.model_dump_json())
    assert copia == avaliacao


def test_simetria_das_metricas(dados_sinteticos: Dados, dados_espelhados: Dados) -> None:
    a = avaliar_previsao(
        _publicada(dados_sinteticos), _resultados(dados_sinteticos), fontes=[FONTE], gerado_em=AGORA
    )
    b = avaliar_previsao(
        _publicada(dados_espelhados), _resultados(dados_espelhados), fontes=[FONTE], gerado_em=AGORA
    )
    for x, y in zip(a.camaras, b.camaras, strict=True):
        assert y.brier == pytest.approx(x.brier, abs=0.005)
        assert y.log_loss == pytest.approx(x.log_loss, abs=0.02)
        assert y.vies_margem == pytest.approx(-(x.vies_margem or 0.0), abs=0.3)


def test_contagem_lenta_fica_por_decidir(dados_sinteticos: Dados) -> None:
    publicada = _publicada(dados_sinteticos)
    resultados = _resultados(dados_sinteticos)
    em_falta = next(c.id for c in publicada.corridas if c.camara == "senado")
    del resultados[em_falta]
    resultados["AL-01"] = replace(resultados["AL-01"], margem=None)
    avaliacao = avaliar_previsao(publicada, resultados, fontes=[FONTE], gerado_em=AGORA)
    senado = next(c for c in avaliacao.camaras if c.camara == "senado")
    camara = next(c for c in avaliacao.camaras if c.camara == "camara")
    assert senado.corridas_por_decidir == (em_falta,)
    assert senado.lugares_d_reais is None
    assert senado.prob_controlo_vencedor is None
    assert camara.corridas_com_margem == camara.corridas_avaliadas - 1


def test_log_loss_finito_com_certeza_errada(dados_sinteticos: Dados) -> None:
    publicada = _publicada(dados_sinteticos)
    resultados = {c.id: Resultado("R" if c.prob_d > 0.5 else "D") for c in publicada.corridas}
    avaliacao = avaliar_previsao(publicada, resultados, fontes=[FONTE], gerado_em=AGORA)
    assert all(math.isfinite(c.log_loss) for c in avaliacao.camaras)
    assert all(c.acertos == 0.0 for c in avaliacao.camaras)


@pytest.mark.parametrize(
    ("ano", "camara_d", "senado_d"), [(2018, 235, 47), (2022, 213, 51), (2024, 215, 47)]
)
def test_backtests_com_os_resultados_reais(ano: int, camara_d: int, senado_d: int) -> None:
    avaliacao = backtest(ano, AGORA)
    camara, senado = avaliacao.camaras
    assert camara.lugares_d_reais == camara_d
    assert senado.lugares_d_reais == senado_d
    for c in avaliacao.camaras:
        assert c.corridas_por_decidir == ()
        assert c.brier < 0.06
        assert c.acertos > 0.9
