"""Cubos de contagens: o painel agregado, sem qualquer dado pessoal.

Um cubo tem uma coluna ``n`` com o número de eleitores em cada combinação das dimensões.
Os recenseados que ainda não votaram antecipadamente têm ``modalidade = "nao_votou"`` e
``dias_antes`` nulo, por isso o mesmo cubo dá os numeradores e os denominadores.
"""

import polars as pl

DIMENSOES_DEMOGRAFICAS = (
    "faixa",
    "partido",
    "raca",
    "etnia",
    "genero",
    "grupo",
    "modalidade",
    "dias_antes",
)
DIMENSOES_GEOGRAFICAS = (
    "fips_condado",
    "distrito_atual",
    "faixa",
    "partido",
    "modalidade",
    "dias_antes",
)

ESQUEMA_DIMENSOES: dict[str, pl.DataType] = {
    "faixa": pl.String(),
    "partido": pl.String(),
    "raca": pl.String(),
    "etnia": pl.String(),
    "genero": pl.String(),
    "grupo": pl.String(),
    "modalidade": pl.String(),
    "dias_antes": pl.Int16(),
    "fips_condado": pl.String(),
    "distrito_atual": pl.Int8(),
}


def agregar(painel: pl.DataFrame, dimensoes: tuple[str, ...]) -> pl.DataFrame:
    """Conta eleitores por combinação de ``dimensoes``, numa ordem estável."""
    return (
        painel.group_by(list(dimensoes))
        .agg(pl.len().cast(pl.UInt32).alias("n"))
        .cast({d: ESQUEMA_DIMENSOES[d] for d in dimensoes})
        .sort(list(dimensoes), nulls_last=True)
    )


def cubo_demografico(painel: pl.DataFrame) -> pl.DataFrame:
    return agregar(painel, DIMENSOES_DEMOGRAFICAS)


def cubo_geografico(painel: pl.DataFrame) -> pl.DataFrame:
    return agregar(painel, DIMENSOES_GEOGRAFICAS)
