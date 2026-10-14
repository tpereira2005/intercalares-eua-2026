"""Cubos de contagens: o painel agregado, sem qualquer dado pessoal.

Um cubo tem uma coluna ``n`` com o número de eleitores em cada combinação das dimensões.
Os recenseados que ainda não votaram antecipadamente têm ``modalidade = "nao_votou"`` e
``dias_antes`` nulo, por isso o mesmo cubo dá os numeradores e os denominadores.
"""

import polars as pl

from pipeline.comum.faixas_etarias import CANONICA

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
    "grupo",
    "modalidade",
    "dias_antes",
)
DIMENSOES_FINAIS = ("fips_condado", "distrito_atual", "faixa", "partido", "metodo")

ESQUEMA_DIMENSOES: dict[str, pl.DataType] = {
    "faixa": pl.String(),
    "partido": pl.String(),
    "raca": pl.String(),
    "etnia": pl.String(),
    "genero": pl.String(),
    "grupo": pl.String(),
    "modalidade": pl.String(),
    "dias_antes": pl.Int16(),
    "metodo": pl.String(),
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


def cubo_final(
    registados: pl.DataFrame,
    historico: pl.DataFrame,
    ano: int,
    distrito_atual: pl.DataFrame | None = None,
) -> pl.DataFrame:
    """Eleitorado final de ``ano``: todos os que votaram segundo o histórico individual,
    antecipadamente ou no dia, com idade e partido do retrato do recenseamento desse dia
    (as mesmas definições do painel). Quem votou mas não está no retrato fica de fora; o
    job de referência mede essa diferença."""
    votos = historico.filter(pl.col("ano") == ano).select("ncid", "metodo")
    base = registados.join(votos, on="ncid", how="inner").with_columns(
        CANONICA.expressao("idade", "faixa")
    )
    if distrito_atual is not None:
        base = base.join(distrito_atual, on="ncid", how="left").with_columns(
            pl.coalesce("distrito_atual", "distrito").alias("distrito_atual")
        )
    else:
        base = base.with_columns(pl.col("distrito").alias("distrito_atual"))
    return agregar(base, DIMENSOES_FINAIS)
