"""Leitura do ficheiro de votantes por correspondência do Maine."""

from pathlib import Path

import polars as pl

from pipeline.comum.calendario import EleicaoGeral
from pipeline.comum.categorias import Modalidade, Partido
from pipeline.comum.erros import ErroFormatoFonte
from pipeline.comum.leitura import RelatorioLeitura, ler_cabecalho, ler_tudo
from pipeline.comum.normalizar import mapear, texto

PARTIDOS: dict[str, Partido] = {"D": Partido.DEM, "R": Partido.REP, "U": Partido.NAO_AFILIADO}
"""Verdes, libertários e outros ficam em ``outro``."""

PRESENCIAL = frozenset({"VP"})
"""Voto na presença do funcionário municipal: o voto antecipado presencial do Maine."""

# Os ficheiros até 2024 e o de 2026 usam nomes de colunas diferentes.
NOMES: dict[str, tuple[str, ...]] = {
    "eleitor": ("VOTER ID", "Voter Record #"),
    "partido": ("P",),
    "distrito": ("CG",),
    "pedido": ("REQDATE", "Req Date"),
    "rececao": ("RECDATE", "Rec Date"),
    "tipo_rececao": ("RECTYPE", "Rec Type"),
}


def _coluna(cabecalho: list[str], nomes: tuple[str, ...]) -> str:
    for nome in nomes:
        if nome in cabecalho:
            return nome
    msg = f"Coluna em falta: {' / '.join(nomes)}"
    raise ErroFormatoFonte(msg)


def _data(coluna: str) -> pl.Expr:
    """As datas vêm como "10/14/2022" ou "11/08/2022 04:31 pm"."""
    return (
        pl.col(coluna)
        .str.strip_chars()
        .str.slice(0, 10)
        .str.strptime(pl.Date, "%m/%d/%Y", strict=False)
    )


def ler_boletins(caminho: Path, eleicao: EleicaoGeral) -> tuple[pl.DataFrame, RelatorioLeitura]:
    """Um boletim por eleitor, nas colunas de :mod:`pipeline.transform.early_vote.agregado`.

    Quando um eleitor tem mais de um boletim (um duplicado depois de um extravio, por
    exemplo), conta a primeira receção; sem nenhuma receção, conta o primeiro pedido.
    """
    cabecalho = ler_cabecalho(caminho, delimitador="|", codificacao="latin-1")
    origem = {chave: _coluna(cabecalho, nomes) for chave, nomes in NOMES.items()}
    bruto, relatorio = ler_tudo(
        caminho, list(origem.values()), delimitador="|", codificacao="latin-1"
    )
    if bruto.is_empty():
        msg = f"{caminho.name}: sem boletins"
        raise ErroFormatoFonte(msg)
    tabela = (
        bruto.select(
            texto(origem["eleitor"]).alias("_eleitor"),
            mapear(origem["partido"], PARTIDOS, Partido.OUTRO).alias("partido"),
            pl.when(texto(origem["tipo_rececao"]).is_in(list(PRESENCIAL)))
            .then(pl.lit(str(Modalidade.PRESENCIAL)))
            .otherwise(pl.lit(str(Modalidade.CORREIO)))
            .alias("modalidade"),
            pl.col(origem["distrito"])
            .str.strip_chars()
            .cast(pl.Int8, strict=False)
            .alias("distrito"),
            _data(origem["pedido"]).alias("data_pedido"),
            _data(origem["rececao"]).alias("data_devolucao"),
        )
        .filter(pl.col("_eleitor") != "")
        .sort("data_devolucao", "data_pedido", nulls_last=True)
        .unique("_eleitor", keep="first", maintain_order=True)
        .drop("_eleitor")
        .with_columns(
            pl.lit(None, pl.Int16).alias("idade"), pl.lit(None, pl.String).alias("fips_condado")
        )
    )
    if tabela["distrito"].null_count() > 0.01 * tabela.height:
        msg = f"{caminho.name}: distritos em falta ou ilegíveis"
        raise ErroFormatoFonte(msg)
    return tabela, relatorio
