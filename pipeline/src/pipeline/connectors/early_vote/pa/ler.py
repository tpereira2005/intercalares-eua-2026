"""Leitura dos pedidos de voto por correspondência da Pensilvânia."""

from pathlib import Path

import polars as pl

from pipeline.comum.calendario import EleicaoGeral
from pipeline.comum.categorias import Modalidade, Partido
from pipeline.comum.erros import ErroFormatoFonte
from pipeline.comum.leitura import RelatorioLeitura, ler_tudo
from pipeline.comum.normalizar import mapear, texto
from pipeline.connectors.early_vote.pa import codigos, fontes

MINIMO_RECONHECIDOS = 0.999
"""Fração mínima de linhas com condado conhecido; abaixo disto o formato mudou."""


def _data(coluna: str) -> pl.Expr:
    """As datas vêm como "2022-10-20" ou "2022-10-20T00:00:00.000"."""
    return pl.col(coluna).str.slice(0, 10).str.strptime(pl.Date, "%Y-%m-%d", strict=False)


def ler_pedidos(caminho: Path, eleicao: EleicaoGeral) -> tuple[pl.DataFrame, RelatorioLeitura]:
    """Um pedido por linha, nas colunas de :mod:`pipeline.transform.early_vote.agregado`."""
    ano = eleicao.ano
    colunas = list(fontes.COLUNAS)
    if ano in fontes.ANOS_COM_ESTADO:
        colunas.append(fontes.COLUNA_ESTADO)
    bruto, relatorio = ler_tudo(caminho, colunas)
    if bruto.is_empty():
        msg = f"{caminho.name}: sem pedidos"
        raise ErroFormatoFonte(msg)
    devolvido = _data("ballotreturneddate")
    if ano in fontes.ANOS_COM_ESTADO:
        anulado = texto(fontes.COLUNA_ESTADO).is_in(list(codigos.ESTADOS_ANULADOS))
        devolvido = pl.when(anulado).then(None).otherwise(devolvido)
    ano_nascimento = pl.col("dateofbirth").str.slice(0, 4).cast(pl.Int16, strict=False)
    tabela = bruto.select(
        (pl.lit(ano, pl.Int16) - ano_nascimento).alias("idade"),
        mapear("party", codigos.PARTIDOS, Partido.OUTRO).alias("partido"),
        pl.lit(str(Modalidade.CORREIO)).alias("modalidade"),
        texto("countyname")
        .replace_strict(codigos.FIPS_CONDADO, default=None)
        .alias("fips_condado"),
        # "13TH CONGRESSIONAL DISTRICT": o número vem no início.
        pl.col("congressional")
        .str.extract(r"^\s*(\d+)")
        .cast(pl.Int8, strict=False)
        .alias("distrito"),
        _data("appissuedate").alias("data_pedido"),
        devolvido.alias("data_devolucao"),
    )
    for coluna, nome in (("fips_condado", "um condado"), ("distrito", "um distrito")):
        reconhecidos = tabela[coluna].count() / tabela.height
        if reconhecidos < MINIMO_RECONHECIDOS:
            msg = f"{caminho.name}: só {reconhecidos:.2%} das linhas têm {nome} conhecido"
            raise ErroFormatoFonte(msg)
    return tabela, relatorio
