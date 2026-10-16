"""Classificações de especialistas: pontuação, tradução em margem e simetria."""

from collections.abc import Callable
from dataclasses import replace

import numpy as np
import pytest

from pipeline.modelo.previsao import Ajustes, Dados, estimar, prever
from pipeline.modelo.prognosticos import NIVEIS, estimar_traducao, pontuacao, pontuacoes

CATEGORIAS = list(NIVEIS)


def _com_classificacoes(dados: Dados) -> Dados:
    """Classificações sintéticas tiradas da margem real com ruído (só corridas renhidas)."""
    rng = np.random.default_rng(3)
    classificacoes: dict[tuple[int, str], tuple[tuple[str, str, str], ...]] = {}
    for ano, corridas in dados.corridas.items():
        for c in corridas:
            margem = (c.candidatos[0].percentagem or 0.0) - (c.candidatos[1].percentagem or 0.0)
            ruido = margem + rng.normal(0, 4)
            if abs(ruido) > 18:
                continue
            nivel = min(int(abs(ruido) // 4), 3)
            categoria = ["empate", "inclinado", "provavel", "seguro"][nivel]
            partido = "" if categoria == "empate" else ("D" if ruido > 0 else "R")
            classificacoes[(ano, c.id)] = tuple(
                (p, categoria, partido) for p in ("cook", "sabato", "ie")
            )
    return replace(dados, classificacoes=classificacoes)


@pytest.fixture(scope="module")
def com_classificacoes(dados_sinteticos: Dados) -> Dados:
    return _com_classificacoes(dados_sinteticos)


def test_pontuacao_troca_de_sinal_com_o_partido(com_classificacoes: Dados) -> None:
    _, linhas = estimar(com_classificacoes, 2018, "camara")
    linha = linhas[2018][0]
    assert pontuacao(linha, (("cook", "provavel", "D"), ("ie", "empate", ""))) == 1.0
    assert pontuacao(linha, (("cook", "provavel", "R"), ("ie", "empate", ""))) == -1.0
    assert pontuacao(linha, (("economist", "seguro", "D"),)) is None


def test_traducao_usa_so_anos_anteriores(com_classificacoes: Dados) -> None:
    _, linhas = estimar(com_classificacoes, 2016, "camara")
    t = estimar_traducao(linhas, com_classificacoes.classificacoes, 2016)
    assert t is not None
    assert t.pontos_por_nivel > 0
    so_antes = sum(
        len(pontuacoes(ls, com_classificacoes.classificacoes))
        for a, ls in linhas.items()
        if a < 2016
    )
    assert t.corridas <= so_antes


def test_classificacoes_mudam_as_corridas_e_sao_simetricas(
    com_classificacoes: Dados, espelhar_dados: Callable[[Dados], Dados]
) -> None:
    com = prever(com_classificacoes, 2018)
    sem = prever(com_classificacoes, 2018, ajustes=Ajustes(especialistas=False))
    mudaram = [
        a.linha.id
        for a, b in zip(com.camara.corridas, sem.camara.corridas, strict=True)
        if a.media != b.media
    ]
    assert len(mudaram) > 10
    espelho = prever(espelhar_dados(com_classificacoes), 2018)
    for a, b in zip(com.camara.corridas, espelho.camara.corridas, strict=True):
        assert b.media == pytest.approx(-a.media, abs=0.6)
    assert espelho.camara.prob_controlo_d == pytest.approx(com.camara.prob_controlo_r, abs=0.02)
    assert espelho.senado.prob_controlo_d == pytest.approx(com.senado.prob_controlo_r, abs=0.02)
