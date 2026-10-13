"""Eleitores recenseados: ficheiro atual (``ncvoter``) e retratos no dia da eleição.

Os dois têm formatos diferentes mas produzem a mesma tabela normalizada, uma linha por
eleitor recenseado (ativo ou inativo), sem nomes nem moradas.
"""

from collections.abc import Iterator
from pathlib import Path

import polars as pl

from pipeline.comum.categorias import Etnia, Genero, Partido, Raca
from pipeline.comum.erros import ErroFormatoFonte
from pipeline.comum.leitura import RelatorioLeitura, ler_delimitado
from pipeline.comum.normalizar import data, distrito, inteiro, mapear, texto
from pipeline.connectors.early_vote.nc import codigos

ESTADOS_RECENSEADO = ("A", "I", "S")
"""Ativo, inativo e temporário (militares e residentes no estrangeiro). Excluímos removidos
(R) e recusados (D), como a NCSBE nas suas estatísticas de eleitores recenseados."""

ESQUEMA_RECENSEAMENTO = {
    "ncid": pl.String,
    "fips_condado": pl.String,
    "distrito": pl.Int8,
    "idade": pl.Int16,
    "partido": pl.String,
    "raca": pl.String,
    "etnia": pl.String,
    "genero": pl.String,
    "data_registo": pl.Date,
}

COLUNAS_ATUAL = (
    "ncid",
    "county_desc",
    "status_cd",
    "party_cd",
    "race_code",
    "ethnic_code",
    "gender_code",
    "birth_year",
    "registr_dt",
    "cong_dist_abbrv",
)

COLUNAS_RETRATO = (
    "ncid",
    "county_desc",
    "status_cd",
    "party_cd",
    "race_code",
    "ethnic_code",
    "sex_code",
    "age",
    "registr_dt",
    "cong_dist_abbrv",
)


def _normalizar(lote: pl.DataFrame, idade: pl.Expr, genero: str) -> pl.DataFrame:
    return (
        lote.filter(texto("status_cd").is_in(ESTADOS_RECENSEADO))
        .select(
            pl.col("ncid").str.strip_chars().alias("ncid"),
            texto("county_desc")
            .replace_strict(codigos.FIPS_CONDADO, default=None)
            .alias("fips_condado"),
            distrito("cong_dist_abbrv").alias("distrito"),
            idade.alias("idade"),
            mapear("party_cd", codigos.PARTIDO, Partido.OUTRO).alias("partido"),
            mapear("race_code", codigos.RACA, Raca.NAO_INDICADA).alias("raca"),
            mapear("ethnic_code", codigos.ETNIA, Etnia.NAO_INDICADA).alias("etnia"),
            mapear(genero, codigos.GENERO, Genero.NAO_INDICADO).alias("genero"),
            data("registr_dt").alias("data_registo"),
        )
        .cast(ESQUEMA_RECENSEAMENTO)  # type: ignore[arg-type]
    )


def _validar(tabela: pl.DataFrame, origem: str) -> pl.DataFrame:
    sem_condado = tabela["fips_condado"].null_count()
    if tabela.height == 0:
        msg = f"{origem}: nenhum eleitor recenseado"
        raise ErroFormatoFonte(msg)
    if sem_condado / tabela.height > 0.001:
        msg = f"{origem}: {sem_condado} eleitores com condado desconhecido"
        raise ErroFormatoFonte(msg)
    return tabela


def _juntar(lotes: Iterator[pl.DataFrame]) -> pl.DataFrame:
    partes = list(lotes)
    if not partes:
        return pl.DataFrame(schema=ESQUEMA_RECENSEAMENTO)
    return pl.concat(partes, rechunk=True)


def ler_ficheiro_eleitores(
    caminho: Path, relatorio: RelatorioLeitura | None = None
) -> pl.DataFrame:
    """Ficheiro ``ncvoter_Statewide`` completo, incluindo removidos, sem dados pessoais.

    Além da tabela normalizada traz ``recenseado`` (ativo, inativo ou temporário) e
    ``ano_nascimento``. Os removidos servem para dar a idade exata, no fim de cada ano, a
    eleitores dos retratos antigos que entretanto saíram do recenseamento.
    """
    partes = [
        lote.select(
            pl.col("ncid").str.strip_chars().alias("ncid"),
            texto("status_cd").is_in(ESTADOS_RECENSEADO).alias("recenseado"),
            inteiro("birth_year").alias("ano_nascimento"),
            texto("county_desc")
            .replace_strict(codigos.FIPS_CONDADO, default=None)
            .alias("fips_condado"),
            distrito("cong_dist_abbrv").alias("distrito"),
            mapear("party_cd", codigos.PARTIDO, Partido.OUTRO).alias("partido"),
            mapear("race_code", codigos.RACA, Raca.NAO_INDICADA).alias("raca"),
            mapear("ethnic_code", codigos.ETNIA, Etnia.NAO_INDICADA).alias("etnia"),
            mapear("gender_code", codigos.GENERO, Genero.NAO_INDICADO).alias("genero"),
            data("registr_dt").alias("data_registo"),
        )
        for lote in ler_delimitado(
            caminho, COLUNAS_ATUAL, delimitador="\t", codificacao="utf-8", relatorio=relatorio
        )
    ]
    if not partes:
        msg = f"{caminho.name}: ficheiro de eleitores vazio"
        raise ErroFormatoFonte(msg)
    return pl.concat(partes, rechunk=True)


def recenseados_atuais(eleitores: pl.DataFrame, ano_eleicao: int) -> pl.DataFrame:
    """Recenseados do ficheiro atual, com a idade no fim do ano da eleição (a mesma definição
    do campo ``age`` dos ficheiros de boletins, confirmada eleitor a eleitor)."""
    tabela = (
        eleitores.filter(pl.col("recenseado"))
        .with_columns((pl.lit(ano_eleicao) - pl.col("ano_nascimento")).alias("idade"))
        .select(list(ESQUEMA_RECENSEAMENTO))
        .cast(ESQUEMA_RECENSEAMENTO)  # type: ignore[arg-type]
    )
    return _validar(tabela, "ncvoter_Statewide")


def anos_nascimento(eleitores: pl.DataFrame) -> pl.DataFrame:
    return eleitores.select("ncid", "ano_nascimento").drop_nulls().unique(subset="ncid")


def corrigir_idade(
    registados: pl.DataFrame, nascimentos: pl.DataFrame, ano_eleicao: int
) -> pl.DataFrame:
    """Põe a idade dos retratos na mesma definição dos boletins (idade no fim do ano).

    Os retratos trazem a idade no dia do retrato, o que deixa cerca de 14% dos eleitores um
    ano mais novos do que nos boletins (quem faz anos entre a eleição e 31 de dezembro).
    Usamos o ano de nascimento do ficheiro atual, que inclui os eleitores removidos.
    """
    return (
        registados.join(nascimentos, on="ncid", how="left")
        .with_columns(
            pl.coalesce(
                (pl.lit(ano_eleicao) - pl.col("ano_nascimento")).cast(pl.Int16), pl.col("idade")
            ).alias("idade")
        )
        .drop("ano_nascimento")
    )


def ler_retrato(caminho: Path, relatorio: RelatorioLeitura | None = None) -> pl.DataFrame:
    """Retrato ``VR_Snapshot_<data>`` (UTF-16, separado por tabulações, ~20 GB descomprimido).

    Os retratos incluem eleitores removidos nos dez anos anteriores; ficam de fora.
    """
    lotes = (
        _normalizar(lote, inteiro("age"), "sex_code")
        for lote in ler_delimitado(
            caminho, COLUNAS_RETRATO, delimitador="\t", codificacao="utf-16", relatorio=relatorio
        )
    )
    tabela = _validar(_juntar(lotes), caminho.name)
    # Um eleitor pode aparecer em dois condados no mesmo retrato (mudança de morada a meio do
    # processamento). Fica o registo mais recente.
    return tabela.sort("data_registo", nulls_last=False).unique(subset="ncid", keep="last")
