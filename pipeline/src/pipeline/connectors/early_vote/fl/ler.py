"""Leitura das estatísticas diárias da Florida e do arquivo de retratos."""

import re
from collections.abc import Sequence
from datetime import datetime, timedelta
from pathlib import Path

import polars as pl

from pipeline.comum.erros import ErroFormatoFonte
from pipeline.comum.leitura import ler_tudo
from pipeline.connectors.early_vote.fl import codigos

TOTAL_ESTADO = "STATETOTALS"
ESQUEMA_RETRATO = {
    "dados_ate": pl.Date,
    "fips_condado": pl.String,
    "partido": pl.String,
    "tipo": pl.String,
    "n": pl.Int64,
}
"""Uma linha por dia, condado, partido e tipo (``correio``, ``presencial``, ``pendentes``)."""

COLUNAS = ["CountyName", "StatType", *codigos.COLUNAS_PARTIDO, "GrandTotal", "CompileDate"]


def _chave(nome: str) -> str:
    return re.sub(r"[^A-Z]", "", nome.upper())


def _numero(texto: str) -> int:
    return int(texto.replace(",", "").strip() or 0)


def ler_estatisticas(caminhos: Sequence[Path]) -> pl.DataFrame:
    """Retrato atual no formato de ``ESQUEMA_RETRATO``.

    ``dados_ate`` é a véspera da compilação de cada condado: os relatórios são cumulativos
    até ao dia anterior. Confere a soma dos condados com a linha do total estadual.
    """
    linhas: list[dict[str, object]] = []
    totais: dict[str, int] = {}
    for caminho in caminhos:
        bruto, _ = ler_tudo(caminho, COLUNAS, delimitador="\t", codificacao="latin-1")
        for registo in bruto.iter_rows(named=True):
            tipo = codigos.TIPOS.get(registo["StatType"].strip().upper())
            if tipo is None:
                msg = f"{caminho.name}: tipo desconhecido {registo['StatType']!r}"
                raise ErroFormatoFonte(msg)
            chave = _chave(registo["CountyName"])
            compilado = datetime.strptime(  # noqa: DTZ007 (data local da fonte)
                " ".join(registo["CompileDate"].split()[:1]), "%m/%d/%Y"
            ).date()
            if chave == TOTAL_ESTADO:
                totais[tipo] = _numero(registo["GrandTotal"])
                continue
            fips = codigos.FIPS_CONDADO.get(chave)
            if fips is None:
                msg = f"{caminho.name}: condado desconhecido {registo['CountyName']!r}"
                raise ErroFormatoFonte(msg)
            for coluna, partido in codigos.COLUNAS_PARTIDO.items():
                linhas.append(
                    {
                        "dados_ate": compilado - timedelta(days=1),
                        "fips_condado": fips,
                        "partido": str(partido),
                        "tipo": tipo,
                        "n": _numero(registo[coluna]),
                    }
                )
    retrato = pl.DataFrame(linhas, schema=ESQUEMA_RETRATO)
    for tipo, total in totais.items():
        soma = retrato.filter(pl.col("tipo") == tipo)["n"].sum()
        if soma != total:
            msg = f"Florida, {tipo}: os condados somam {soma}, o total estadual diz {total}"
            raise ErroFormatoFonte(msg)
    return retrato


def juntar_arquivo(arquivo: pl.DataFrame | None, retrato: pl.DataFrame) -> pl.DataFrame:
    """Acrescenta o retrato ao arquivo; o retrato mais recente de cada condado e dia ganha."""
    if arquivo is None or arquivo.is_empty():
        return retrato.sort("dados_ate", "fips_condado", "partido", "tipo")
    chaves = ["dados_ate", "fips_condado", "partido", "tipo"]
    return (
        pl.concat([arquivo.cast(ESQUEMA_RETRATO), retrato])  # type: ignore[arg-type]
        .unique(chaves, keep="last", maintain_order=True)
        .sort(chaves)
    )


def ler_arquivo(caminho: Path) -> pl.DataFrame | None:
    if not caminho.exists() or caminho.stat().st_size == 0:
        return None
    return pl.read_csv(caminho, schema=ESQUEMA_RETRATO)
