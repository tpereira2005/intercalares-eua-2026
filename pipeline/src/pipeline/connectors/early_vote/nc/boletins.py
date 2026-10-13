"""Ficheiro diário de boletins de voto antecipado (``absentee_<data>.zip``)."""

from dataclasses import dataclass
from pathlib import Path

import polars as pl

from pipeline.comum.categorias import (
    ESTADOS_DEVOLVIDOS,
    EstadoBoletim,
    Etnia,
    Genero,
    Partido,
    Raca,
)
from pipeline.comum.erros import ErroFormatoFonte
from pipeline.comum.leitura import RelatorioLeitura, ler_cabecalho, ler_tudo
from pipeline.comum.normalizar import (
    data,
    distrito,
    inteiro,
    mapear,
    texto,
)
from pipeline.connectors.early_vote.nc import codigos

COLUNAS = (
    "county_desc",
    "ncid",
    "race",
    "gender",
    "age",
    "voter_party_code",
    "cong_dist_desc",
    "ballot_req_type",
    "ballot_req_dt",
    "ballot_send_dt",
    "ballot_rtn_dt",
    "ballot_rtn_status",
    "sdr",
)
COLUNA_ETNIA = "ethnicity"
"""Ausente no ficheiro principal de 2018."""

LIMITE_DESCONHECIDOS = 0.01
"""Fração máxima de linhas com modalidade ou condado desconhecidos antes de falhar."""

ESQUEMA_BOLETINS = {
    "ncid": pl.String,
    "fips_condado": pl.String,
    "distrito": pl.Int8,
    "idade": pl.Int16,
    "partido": pl.String,
    "raca": pl.String,
    "etnia": pl.String,
    "genero": pl.String,
    "modalidade": pl.String,
    "data_pedido": pl.Date,
    "data_envio": pl.Date,
    "data_devolucao": pl.Date,
    "estado_boletim": pl.String,
    "registo_no_dia": pl.Boolean,
}


@dataclass(frozen=True, slots=True)
class ResultadoBoletins:
    boletins: pl.DataFrame
    leitura: RelatorioLeitura
    linhas_descartadas: int
    estados_desconhecidos: dict[str, int]


def ler_boletins(caminho: Path) -> ResultadoBoletins:
    """Lê e normaliza o ficheiro de boletins, descartando todas as colunas pessoais."""
    colunas = list(COLUNAS)
    com_etnia = COLUNA_ETNIA in ler_cabecalho(caminho)
    if com_etnia:
        colunas.append(COLUNA_ETNIA)
    bruto, relatorio = ler_tudo(caminho, colunas)
    return normalizar_boletins(bruto, relatorio)


def normalizar_boletins(
    bruto: pl.DataFrame, relatorio: RelatorioLeitura | None = None
) -> ResultadoBoletins:
    etnia = (
        mapear("ethnicity", codigos.ETNIA, Etnia.NAO_INDICADA)
        if "ethnicity" in bruto.columns
        else pl.lit(str(Etnia.NAO_INDICADA))
    )
    estado_bruto = texto("ballot_rtn_status")
    normal = bruto.select(
        pl.col("ncid").str.strip_chars().alias("ncid"),
        texto("county_desc")
        .replace_strict(codigos.FIPS_CONDADO, default=None)
        .alias("fips_condado"),
        distrito("cong_dist_desc").alias("distrito"),
        inteiro("age").alias("idade"),
        mapear("voter_party_code", codigos.PARTIDO, Partido.OUTRO).alias("partido"),
        mapear("race", codigos.RACA, Raca.NAO_INDICADA).alias("raca"),
        etnia.alias("etnia"),
        mapear("gender", codigos.GENERO, Genero.NAO_INDICADO).alias("genero"),
        texto("ballot_req_type")
        .replace_strict(
            list(codigos.MODALIDADE), [str(v) for v in codigos.MODALIDADE.values()], default=None
        )
        .alias("modalidade"),
        data("ballot_req_dt").alias("data_pedido"),
        data("ballot_send_dt").alias("data_envio"),
        data("ballot_rtn_dt").alias("data_devolucao"),
        estado_bruto.replace_strict(
            list(codigos.ESTADO_BOLETIM),
            [str(v) for v in codigos.ESTADO_BOLETIM.values()],
            default=str(EstadoBoletim.DESCONHECIDO),
        ).alias("estado_boletim"),
        (texto("sdr") == "Y").alias("registo_no_dia"),
        estado_bruto.alias("_estado_bruto"),
    )
    desconhecidos = (
        normal.filter(pl.col("estado_boletim") == str(EstadoBoletim.DESCONHECIDO))
        .group_by("_estado_bruto")
        .len()
    )
    estados_desconhecidos = dict(
        zip(
            desconhecidos["_estado_bruto"].to_list(),
            desconhecidos["len"].to_list(),
            strict=True,
        )
    )
    invalidas = pl.col("modalidade").is_null() | pl.col("fips_condado").is_null()
    descartadas = normal.filter(invalidas).height
    if normal.height and descartadas / normal.height > LIMITE_DESCONHECIDOS:
        msg = (
            f"{descartadas} de {normal.height} boletins sem modalidade ou condado reconhecidos: "
            "o formato da fonte pode ter mudado"
        )
        raise ErroFormatoFonte(msg)
    boletins = normal.filter(~invalidas).drop("_estado_bruto").cast(ESQUEMA_BOLETINS)  # type: ignore[arg-type]
    return ResultadoBoletins(
        boletins=boletins,
        leitura=relatorio or RelatorioLeitura(),
        linhas_descartadas=descartadas,
        estados_desconhecidos=estados_desconhecidos,
    )


def votantes(boletins: pl.DataFrame) -> pl.DataFrame:
    """Um registo por eleitor que já devolveu um boletim: o primeiro, por data de devolução.

    Os boletins anulados (substituídos, cancelados) não contam. Um eleitor que pediu boletim
    por correio e depois votou presencialmente fica com a modalidade do voto que contou
    primeiro.
    """
    devolvidos = [str(e) for e in ESTADOS_DEVOLVIDOS]
    return (
        boletins.filter(
            pl.col("estado_boletim").is_in(devolvidos)
            & pl.col("data_devolucao").is_not_null()
            & (pl.col("ncid").str.len_chars() > 0)
        )
        .sort(["ncid", "data_devolucao", "modalidade"])
        .unique(subset="ncid", keep="first", maintain_order=True)
    )
