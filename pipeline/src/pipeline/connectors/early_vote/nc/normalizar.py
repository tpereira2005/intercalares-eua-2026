"""Expressões polars partilhadas para normalizar campos da NCSBE."""

from collections.abc import Mapping
from enum import StrEnum

import polars as pl

FORMATOS_DATA = ("%m/%d/%Y", "%Y-%m-%d")
"""Os ficheiros diários usam mm/dd/aaaa; os retratos do recenseamento usam aaaa-mm-dd."""


def texto(coluna: str) -> pl.Expr:
    """Texto limpo e em maiúsculas (as fontes misturam espaços e capitalização)."""
    return pl.col(coluna).str.strip_chars().str.to_uppercase()


def data(coluna: str) -> pl.Expr:
    """Data num dos ``FORMATOS_DATA``; valores mascarados ou inválidos ficam nulos."""
    valor = pl.col(coluna).str.strip_chars()
    return pl.coalesce(
        [valor.str.strptime(pl.Date, formato, strict=False) for formato in FORMATOS_DATA]
    )


def inteiro(coluna: str) -> pl.Expr:
    return pl.col(coluna).str.strip_chars().cast(pl.Int16, strict=False)


def mapear(coluna: str, mapa: Mapping[str, StrEnum], omissao: StrEnum) -> pl.Expr:
    chaves = list(mapa)
    valores = [str(v) for v in mapa.values()]
    return texto(coluna).replace_strict(chaves, valores, default=str(omissao))


def distrito(coluna: str) -> pl.Expr:
    """Número do distrito do Congresso a partir de "CONGRESSIONAL DISTRICT 9" ou "09"."""
    return pl.col(coluna).str.extract(r"(\d+)\s*$").cast(pl.Int8, strict=False)
