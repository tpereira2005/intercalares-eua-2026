"""Leitura do ``US.csv`` do UF Election Lab e do arquivo de retratos diários."""

import csv
import io
import re
from collections.abc import Collection
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

import polars as pl

from contratos.estados import CodigoEstado
from pipeline.comum.erros import ErroFormatoFonte

ESQUEMA_RETRATO = {
    "estado": pl.String,
    "dados_ate": pl.Date,
    "votos": pl.Int64,
    "correio": pl.Int64,
    "presencial": pl.Int64,
    "dem": pl.Int64,
    "rep": pl.Int64,
    "nao_afiliado": pl.Int64,
    "pedidos": pl.Int64,
    "devolvidos": pl.Int64,
}
"""Uma linha por estado e dia: votos acumulados (total, correio e presencial), votos por
partido de registo (nulos quando o estado não tem partido na fonte) e boletins por
correspondência pedidos e devolvidos."""

COLUNAS = (
    "state_abbv",
    "last_update",
    "data_source",
    "request_all",
    "accept_all",
    "inperson_all",
    "voted_all",
    "voted_dem",
    "voted_rep",
    "voted_none",
)
"""Colunas que lemos. Se faltar alguma, o formato mudou e nada é publicado."""

_INTEIRO = re.compile(r"\d+")


@dataclass(frozen=True, slots=True)
class Retrato:
    estado: CodigoEstado
    dados_ate: date
    votos: int
    correio: int
    presencial: int
    dem: int | None
    rep: int | None
    nao_afiliado: int | None
    pedidos: int
    devolvidos: int
    origem: str
    """Origem que o próprio UF Election Lab indica para o estado."""


def _inteiro(linha: dict[str, str], coluna: str) -> int:
    texto = linha[coluna].strip()
    if not _INTEIRO.fullmatch(texto):
        msg = (
            f"UF Election Lab, {linha['state_abbv']}: {coluna} não é um inteiro "
            f"não negativo ({texto!r})"
        )
        raise ErroFormatoFonte(msg)
    return int(texto)


def _data(linha: dict[str, str]) -> date:
    texto = linha["last_update"].strip()
    try:
        if not re.fullmatch(r"\d{1,2}/\d{1,2}/\d{4}", texto):
            raise ValueError(texto)
        dia = datetime.strptime(texto, "%m/%d/%Y").date()  # noqa: DTZ007
    except ValueError as erro:
        msg = f"UF Election Lab, {linha['state_abbv']}: last_update inválido {texto!r}"
        raise ErroFormatoFonte(msg) from erro
    return dia


def _retrato(linha: dict[str, str], estado: CodigoEstado, ano: int) -> Retrato | None:
    """Retrato validado, ou ``None`` quando o estado ainda não tem votos."""
    nome = estado.value
    votos = _inteiro(linha, "voted_all")
    if votos == 0:
        return None
    correio, presencial = _inteiro(linha, "accept_all"), _inteiro(linha, "inperson_all")
    pedidos = _inteiro(linha, "request_all")
    dia = _data(linha)
    if dia.year != ano:
        msg = f"UF Election Lab, {nome}: last_update {dia} não é de {ano}"
        raise ErroFormatoFonte(msg)
    if correio + presencial != votos:
        msg = (
            f"UF Election Lab, {nome}: correio ({correio}) e presencial ({presencial}) "
            f"não somam os votos ({votos})"
        )
        raise ErroFormatoFonte(msg)
    if correio > pedidos:
        msg = f"UF Election Lab, {nome}: devolvidos ({correio}) superam pedidos ({pedidos})"
        raise ErroFormatoFonte(msg)
    partidos = [_inteiro(linha, c) for c in ("voted_dem", "voted_rep", "voted_none")]
    if any(partidos):
        if sum(partidos) != votos:
            msg = f"UF Election Lab, {nome}: os partidos somam {sum(partidos)}, os votos {votos}"
            raise ErroFormatoFonte(msg)
        dem, rep, nao_afiliado = partidos
        com_partido: tuple[int | None, int | None, int | None] = (dem, rep, nao_afiliado)
    else:
        com_partido = (None, None, None)
    return Retrato(
        estado, dia, votos, correio, presencial, *com_partido, pedidos, correio,
        linha["data_source"].strip(),
    )  # fmt: skip


def ler_csv(texto: str, estados: Collection[CodigoEstado], ano: int = 2026) -> list[Retrato]:
    """Retratos dos ``estados`` pedidos que já têm votos.

    Valida o esquema da fonte: as colunas esperadas, uma só linha por estado e todos os
    estados pedidos presentes, números inteiros não negativos, datas M/D/AAAA do ano da
    eleição, correio mais presencial igual aos votos, devolvidos não superiores aos pedidos
    e partidos a somar os votos. Um estado sem votos fica de fora; qualquer falha levanta
    ``ErroFormatoFonte``.
    """
    leitor = csv.DictReader(io.StringIO(texto))
    em_falta = [c for c in COLUNAS if c not in (leitor.fieldnames or ())]
    if em_falta:
        msg = f"UF Election Lab: faltam as colunas {em_falta!r}"
        raise ErroFormatoFonte(msg)
    linhas: dict[str, dict[str, str]] = {}
    for linha in leitor:
        sigla = (linha["state_abbv"] or "").strip().upper()
        if sigla in linhas:
            msg = f"UF Election Lab: estado repetido {sigla!r}"
            raise ErroFormatoFonte(msg)
        linhas[sigla] = {k: (v or "") for k, v in linha.items() if k is not None}
    retratos: list[Retrato] = []
    for estado in sorted(estados, key=lambda e: e.value):
        if estado.value not in linhas:
            msg = f"UF Election Lab: falta o estado {estado.value}"
            raise ErroFormatoFonte(msg)
        retrato = _retrato(linhas[estado.value], estado, ano)
        if retrato is not None:
            retratos.append(retrato)
    return retratos


def para_arquivo(retratos: list[Retrato]) -> pl.DataFrame:
    return pl.DataFrame(
        [
            {
                "estado": r.estado.value,
                "dados_ate": r.dados_ate,
                "votos": r.votos,
                "correio": r.correio,
                "presencial": r.presencial,
                "dem": r.dem,
                "rep": r.rep,
                "nao_afiliado": r.nao_afiliado,
                "pedidos": r.pedidos,
                "devolvidos": r.devolvidos,
            }
            for r in retratos
        ],
        schema=ESQUEMA_RETRATO,
    )


def juntar_arquivo(arquivo: pl.DataFrame | None, retratos: pl.DataFrame) -> pl.DataFrame:
    """Acrescenta os retratos ao arquivo; o retrato mais recente de cada estado e dia ganha
    (a fonte atualiza várias vezes por dia, e o último valor do dia é o mais completo)."""
    chaves = ["estado", "dados_ate"]
    if arquivo is None or arquivo.is_empty():
        return retratos.sort(chaves)
    return (
        pl.concat([arquivo.cast(ESQUEMA_RETRATO), retratos])  # type: ignore[arg-type]
        .unique(chaves, keep="last", maintain_order=True)
        .sort(chaves)
    )


def ler_arquivo(caminho: Path) -> pl.DataFrame | None:
    if not caminho.exists() or caminho.stat().st_size == 0:
        return None
    return pl.read_csv(caminho, schema=ESQUEMA_RETRATO)
