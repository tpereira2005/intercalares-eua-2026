"""Códigos FIPS dos condados (Census Bureau, lista de 2020, domínio público).

Os feeds de resultados identificam os condados pelo nome, escrito de formas diferentes
("DeKalb", "De Kalb", "St. Johns", "Saint Johns"). A chave normalizada só guarda as
letras, depois de tirar o sufixo ("County", "Parish") e de escrever "Saint" como "St".
"""

import csv
import re
from functools import cache
from importlib.resources import files

_SUFIXO = re.compile(r"\s+(COUNTY|PARISH|BOROUGH|CENSUS AREA|MUNICIPALITY|CITY AND BOROUGH)$")


def chave(nome: str) -> str:
    texto = _SUFIXO.sub("", nome.upper().strip())
    texto = re.sub(r"\bSAINT\b", "ST", texto)
    return re.sub(r"[^A-Z]", "", texto)


@cache
def _tabela() -> tuple[tuple[str, str, str], ...]:
    conteudo = files("pipeline.comum").joinpath("dados/condados_2020.csv").read_text("utf-8")
    return tuple((r["estado"], r["fips"], r["nome"]) for r in csv.DictReader(conteudo.splitlines()))


@cache
def fips_por_nome(estado: str) -> dict[str, str]:
    """Chave normalizada do nome para o FIPS de cinco dígitos, num estado."""
    return {chave(nome): fips for uf, fips, nome in _tabela() if uf == estado}


@cache
def nomes(estado: str) -> dict[str, str]:
    """FIPS para o nome curto (sem "County"), num estado."""
    return {
        fips: re.sub(r"\s+(County|Parish|Borough|Census Area)$", "", nome)
        for uf, fips, nome in _tabela()
        if uf == estado
    }


@cache
def _estados_por_codigo() -> dict[str, str]:
    return {fips[:2]: uf for uf, fips, _ in _tabela()}


def estado_do_fips(fips: str) -> str | None:
    """Estado (código de duas letras) a partir dos dois primeiros dígitos do FIPS."""
    return _estados_por_codigo().get(fips[:2])
