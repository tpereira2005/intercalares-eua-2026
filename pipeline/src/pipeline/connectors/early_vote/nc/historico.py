"""Histórico de voto individual (``ncvhis_Statewide``).

Guardamos só as eleições gerais de novembro e a forma como cada eleitor votou nelas
(antecipadamente ou no dia), por ``ncid``. É o que permite separar quem já votava cedo,
quem passou do dia da eleição para o voto antecipado e quem é voto novo.
"""

from datetime import date
from pathlib import Path

import polars as pl

from pipeline.comum.categorias import MetodoHistorico
from pipeline.comum.erros import ErroFormatoFonte
from pipeline.comum.leitura import RelatorioLeitura, ler_delimitado
from pipeline.comum.normalizar import texto
from pipeline.connectors.early_vote.nc import codigos

COLUNAS = ("ncid", "election_lbl", "voting_method")

ESQUEMA_HISTORICO = {"ncid": pl.String, "ano": pl.Int16, "metodo": pl.String}


def ler_historico(
    caminho: Path,
    eleicoes: dict[int, date],
    relatorio: RelatorioLeitura | None = None,
) -> pl.DataFrame:
    """Uma linha por eleitor e eleição geral pedida, com o método (antecipado ou no dia).

    Quando um eleitor tem mais de um registo na mesma eleição (por exemplo, mudou de
    condado), prevalece o voto antecipado, que é o que a análise precisa de identificar.
    """
    rotulos = {d.strftime("%m/%d/%Y"): ano for ano, d in eleicoes.items()}
    antecipado = list(codigos.METODO_HISTORICO_ANTECIPADO)
    dia = list(codigos.METODO_HISTORICO_DIA)
    partes: list[pl.DataFrame] = []
    for lote in ler_delimitado(
        caminho, COLUNAS, delimitador="\t", codificacao="utf-8", relatorio=relatorio
    ):
        filtrado = lote.filter(pl.col("election_lbl").str.strip_chars().is_in(list(rotulos)))
        if filtrado.height == 0:
            continue
        metodo = texto("voting_method")
        partes.append(
            filtrado.select(
                pl.col("ncid").str.strip_chars(),
                pl.col("election_lbl")
                .str.strip_chars()
                .replace_strict(rotulos, return_dtype=pl.Int16)
                .alias("ano"),
                pl.when(metodo.is_in(antecipado))
                .then(pl.lit(str(MetodoHistorico.ANTECIPADO)))
                .when(metodo.is_in(dia))
                .then(pl.lit(str(MetodoHistorico.DIA_ELEICAO)))
                .otherwise(None)
                .alias("metodo"),
            ).filter(pl.col("metodo").is_not_null())
        )
    if not partes:
        msg = f"{caminho.name}: nenhuma das eleições pedidas está no histórico"
        raise ErroFormatoFonte(msg)
    historico = pl.concat(partes, rechunk=True)
    return (
        historico.sort(
            ["ncid", "ano", pl.col("metodo") == str(MetodoHistorico.ANTECIPADO)],
            descending=[False, False, True],
        )
        .unique(subset=["ncid", "ano"], keep="first")
        .cast(ESQUEMA_HISTORICO)  # type: ignore[arg-type]
    )
