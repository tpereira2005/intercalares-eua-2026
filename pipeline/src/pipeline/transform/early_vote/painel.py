"""Painel de eleitores: recenseados x votos antecipados x histórico de voto."""

from datetime import date

import polars as pl

from pipeline.comum.calendario import EleicaoGeral
from pipeline.comum.categorias import GrupoHistorico, MetodoHistorico, Modalidade
from pipeline.comum.faixas_etarias import CANONICA

DIAS_ANTES_MAXIMO = 90
"""Votos devolvidos mais cedo do que isto (raros, sobretudo militares) agrupam-se aqui."""

DIAS_ANTES_MINIMO = -15
"""Correspondência recebida depois do dia da eleição (permitida até 2022)."""

ATRIBUTOS = ("fips_condado", "distrito", "idade", "partido", "raca", "etnia", "genero")


def construir_painel(
    registados: pl.DataFrame,
    votantes: pl.DataFrame,
    *,
    historico: pl.DataFrame | None,
    eleicao: EleicaoGeral,
    data_referencia: date | None,
    distrito_atual: pl.DataFrame | None = None,
) -> pl.DataFrame:
    """Junta recenseados, votantes e histórico numa linha por eleitor.

    * Os votantes que não estão no ficheiro de recenseados (recenseamento no próprio dia
      do voto antecipado, ou posterior ao ficheiro) entram com os atributos do boletim.
    * ``distrito_atual`` (``ncid``, ``distrito_atual``) põe os eleitores de anos anteriores
      nos distritos do mapa de 2026; sem ele, usa-se o distrito da época.
    * ``data_referencia`` é a data da eleição de referência do histórico.
    """
    votos = votantes.select(
        "ncid",
        "modalidade",
        "data_devolucao",
        pl.col("registo_no_dia").fill_null(value=False),
        *[pl.col(c).alias(f"_v_{c}") for c in ATRIBUTOS],
    )
    base = registados.join(votos, on="ncid", how="full", coalesce=True)
    base = base.with_columns(
        [pl.coalesce(pl.col(c), pl.col(f"_v_{c}")).alias(c) for c in ATRIBUTOS]
    ).drop([f"_v_{c}" for c in ATRIBUTOS])

    dias = (
        (pl.lit(eleicao.data) - pl.col("data_devolucao"))
        .dt.total_days()
        .clip(DIAS_ANTES_MINIMO, DIAS_ANTES_MAXIMO)
        .cast(pl.Int16)
    )
    base = base.with_columns(
        pl.col("modalidade").fill_null(str(Modalidade.NAO_VOTOU)),
        pl.when(pl.col("data_devolucao").is_not_null())
        .then(dias)
        .otherwise(None)
        .alias("dias_antes"),
        CANONICA.expressao("idade", "faixa"),
        pl.col("registo_no_dia").fill_null(value=False),
    )
    base = _grupo_historico(base, historico, eleicao, data_referencia)
    if distrito_atual is not None:
        base = base.join(distrito_atual, on="ncid", how="left").with_columns(
            pl.coalesce("distrito_atual", "distrito").alias("distrito_atual")
        )
    else:
        base = base.with_columns(pl.col("distrito").alias("distrito_atual"))
    return base.drop("data_devolucao")


def _grupo_historico(
    base: pl.DataFrame,
    historico: pl.DataFrame | None,
    eleicao: EleicaoGeral,
    data_referencia: date | None,
) -> pl.DataFrame:
    ano_ref = eleicao.referencia_historico
    if historico is None or ano_ref is None or data_referencia is None:
        return base.with_columns(pl.lit(str(GrupoHistorico.SEM_HISTORICO)).alias("grupo"))
    ref = historico.filter(pl.col("ano") == ano_ref).select(
        "ncid", pl.col("metodo").alias("_metodo_ref")
    )
    if ref.height == 0:
        return base.with_columns(pl.lit(str(GrupoHistorico.SEM_HISTORICO)).alias("grupo"))
    metodo = pl.col("_metodo_ref")
    grupo = (
        pl.when(metodo == str(MetodoHistorico.ANTECIPADO))
        .then(pl.lit(str(GrupoHistorico.ANTECIPADO_NA_REFERENCIA)))
        .when(metodo == str(MetodoHistorico.DIA_ELEICAO))
        .then(pl.lit(str(GrupoHistorico.DIA_ELEICAO_NA_REFERENCIA)))
        .when(
            (pl.col("data_registo") > pl.lit(data_referencia))
            | (pl.col("data_registo").is_null() & pl.col("registo_no_dia"))
        )
        .then(pl.lit(str(GrupoHistorico.RECENSEADO_APOS_REFERENCIA)))
        .otherwise(pl.lit(str(GrupoHistorico.ABSTEVE_SE_NA_REFERENCIA)))
        .alias("grupo")
    )
    return base.join(ref, on="ncid", how="left").with_columns(grupo).drop("_metodo_ref")
