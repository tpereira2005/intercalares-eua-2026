"""Leitura robusta de ficheiros de texto delimitados das fontes oficiais.

Os ficheiros da Carolina do Norte têm aspas mal fechadas, bytes fora de UTF-8 e campos
com texto livre. Os leitores CSV paralelos (polars, DuckDB) perdem ou rejeitam linhas
nestes ficheiros: no ficheiro de 2022 o DuckDB devolveu 1,87 milhões de linhas quando o
ficheiro tem 2,28 milhões. Por isso lemos linha a linha com o módulo ``csv`` da
biblioteca padrão, validamos o cabeçalho e o número de campos de cada linha, e
guardamos **apenas as colunas pedidas**. Nomes, moradas e outros dados pessoais nunca
chegam a sair desta função.
"""

import csv
import io
import sys
import zipfile
from collections.abc import Iterator, Sequence
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

import polars as pl

from pipeline.comum.erros import ErroFormatoFonte

TAMANHO_LOTE = 250_000
LIMITE_LINHAS_INVALIDAS = 0.001
"""Fração máxima de linhas com número errado de campos antes de recusarmos o ficheiro."""

csv.field_size_limit(min(sys.maxsize, 2**31 - 1))


@dataclass(slots=True)
class RelatorioLeitura:
    linhas: int = 0
    linhas_invalidas: int = 0
    exemplos_invalidos: list[int] = field(default_factory=list)
    """Números das primeiras linhas inválidas (sem conteúdo, para não expor dados pessoais)."""


def _abrir_texto(caminho: Path, membro: str | None, codificacao: str) -> io.TextIOWrapper:
    if caminho.suffix.lower() == ".zip":
        arquivo = zipfile.ZipFile(caminho)
        nomes = arquivo.namelist()
        nome = membro or next((n for n in nomes if not n.endswith("/")), None)
        if nome is None:
            msg = f"Arquivo vazio: {caminho}"
            raise ErroFormatoFonte(msg)
        binario = arquivo.open(nome)
    else:
        binario = caminho.open("rb")
    return io.TextIOWrapper(binario, encoding=codificacao, errors="replace", newline="")


def data_geracao(caminho: Path) -> date | None:
    """Data em que a fonte gerou o ficheiro, lida do próprio zip (hora local da fonte).

    Não depende da data da descarga nem dos cabeçalhos HTTP, por isso é estável entre
    execuções e também funciona com ficheiros já descarregados.
    """
    if caminho.suffix.lower() != ".zip":
        return None
    with zipfile.ZipFile(caminho) as arquivo:
        membros = [m for m in arquivo.infolist() if not m.is_dir()]
    if not membros:
        return None
    ano, mes, dia, *_ = max(m.date_time for m in membros)
    return date(ano, mes, dia)


def ler_cabecalho(
    caminho: Path,
    *,
    delimitador: str = ",",
    codificacao: str = "utf-8",
    membro: str | None = None,
) -> list[str]:
    """Nomes das colunas do ficheiro, sem ler o resto."""
    with _abrir_texto(caminho, membro, codificacao) as texto:
        primeira = next(csv.reader(texto, delimiter=delimitador), [])
    return [c.strip().lstrip("\ufeff") for c in primeira]


def ler_delimitado(
    caminho: Path,
    colunas: Sequence[str],
    *,
    delimitador: str = ",",
    codificacao: str = "utf-8",
    membro: str | None = None,
    relatorio: RelatorioLeitura | None = None,
) -> Iterator[pl.DataFrame]:
    """Lê ``caminho`` (texto ou zip) e devolve lotes com as ``colunas`` pedidas, como texto.

    Falha com :class:`ErroFormatoFonte` se faltar alguma coluna no cabeçalho ou se a fração
    de linhas com o número errado de campos passar de ``LIMITE_LINHAS_INVALIDAS``.
    """
    rel = relatorio if relatorio is not None else RelatorioLeitura()
    with _abrir_texto(caminho, membro, codificacao) as texto:
        leitor = csv.reader(texto, delimiter=delimitador)
        try:
            cabecalho = [c.strip().lstrip("﻿") for c in next(leitor)]
        except StopIteration as erro:
            msg = f"Ficheiro sem cabeçalho: {caminho}"
            raise ErroFormatoFonte(msg) from erro
        em_falta = [c for c in colunas if c not in cabecalho]
        if em_falta:
            msg = f"Colunas em falta em {caminho.name}: {', '.join(em_falta)}"
            raise ErroFormatoFonte(msg)
        indices = [cabecalho.index(c) for c in colunas]
        largura = len(cabecalho)
        lote: list[list[str]] = [[] for _ in colunas]
        for linha in leitor:
            rel.linhas += 1
            if len(linha) != largura:
                rel.linhas_invalidas += 1
                if len(rel.exemplos_invalidos) < 5:
                    rel.exemplos_invalidos.append(rel.linhas + 1)
                continue
            for destino, i in zip(lote, indices, strict=True):
                destino.append(linha[i])
            if len(lote[0]) >= TAMANHO_LOTE:
                yield _para_tabela(colunas, lote)
                lote = [[] for _ in colunas]
        if lote[0]:
            yield _para_tabela(colunas, lote)
    if rel.linhas and rel.linhas_invalidas / rel.linhas > LIMITE_LINHAS_INVALIDAS:
        msg = (
            f"{caminho.name}: {rel.linhas_invalidas} de {rel.linhas} linhas com número errado "
            f"de campos (primeiras: {rel.exemplos_invalidos})"
        )
        raise ErroFormatoFonte(msg)


def _para_tabela(colunas: Sequence[str], valores: list[list[str]]) -> pl.DataFrame:
    return pl.DataFrame(
        {c: pl.Series(c, v, dtype=pl.String) for c, v in zip(colunas, valores, strict=True)}
    )


def ler_tudo(
    caminho: Path,
    colunas: Sequence[str],
    *,
    delimitador: str = ",",
    codificacao: str = "utf-8",
    membro: str | None = None,
) -> tuple[pl.DataFrame, RelatorioLeitura]:
    """Versão de conveniência que concatena todos os lotes."""
    relatorio = RelatorioLeitura()
    lotes = list(
        ler_delimitado(
            caminho,
            colunas,
            delimitador=delimitador,
            codificacao=codificacao,
            membro=membro,
            relatorio=relatorio,
        )
    )
    if not lotes:
        vazio = pl.DataFrame({c: pl.Series(c, [], dtype=pl.String) for c in colunas})
        return vazio, relatorio
    return pl.concat(lotes, rechunk=True), relatorio
