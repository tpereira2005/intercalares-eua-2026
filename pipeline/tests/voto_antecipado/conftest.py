"""Fixtures partilhadas pelos testes do voto antecipado.

Os painéis são aleatórios (semente fixa): nenhum dado vem de eleitores reais.
"""

from collections.abc import Callable
from datetime import date

import numpy as np
import polars as pl
import pytest

from pipeline.comum.calendario import EleicaoGeral
from pipeline.comum.faixas_etarias import CANONICA


def painel_sintetico(semente: int, n: int = 4000, *, taxa_extra: float = 0.0) -> pl.DataFrame:
    """Painel aleatório com a mesma forma que :func:`construir_painel` devolve."""
    rng = np.random.default_rng(semente)
    idades = rng.integers(18, 95, n)
    partidos = rng.choice(["dem", "rep", "nao_afiliado", "outro"], n, p=[0.33, 0.31, 0.33, 0.03])
    grupos = rng.choice(
        [
            "antecipado_na_referencia",
            "dia_eleicao_na_referencia",
            "absteve_se_na_referencia",
            "recenseado_apos_referencia",
        ],
        n,
        p=[0.3, 0.25, 0.35, 0.1],
    )
    prob = 0.15 + 0.004 * (idades - 18) + taxa_extra
    votou = rng.random(n) < np.clip(prob, 0, 1)
    modos = np.where(rng.random(n) < 0.3, "correio", "presencial")
    dias = rng.integers(0, 45, n)
    return pl.DataFrame(
        {
            "ncid": [f"T{semente}{i:06d}" for i in range(n)],
            "idade": pl.Series(idades, dtype=pl.Int16),
            "partido": partidos,
            "raca": rng.choice(["branca", "negra", "outra"], n),
            "etnia": rng.choice(["hispanica", "nao_hispanica"], n),
            "genero": rng.choice(["feminino", "masculino"], n),
            "grupo": grupos,
            "modalidade": np.where(votou, modos, "nao_votou"),
            "dias_antes": pl.Series(
                [int(d) if v else None for d, v in zip(dias, votou, strict=True)], dtype=pl.Int16
            ),
            "fips_condado": rng.choice(["37183", "37119", "37001"], n),
            "distrito_atual": pl.Series(rng.integers(1, 4, n), dtype=pl.Int8),
        }
    ).with_columns(CANONICA.expressao("idade", "faixa"))


FabricaPainel = Callable[..., pl.DataFrame]


@pytest.fixture
def fabrica_painel() -> FabricaPainel:
    return painel_sintetico


@pytest.fixture
def eleicao_teste() -> EleicaoGeral:
    return EleicaoGeral(
        "NC", date(2026, 11, 3), "intercalar", date(2026, 10, 15), date(2026, 10, 31), 2022
    )
