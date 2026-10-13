"""Descarga das fontes da NCSBE e leitura com cache local.

Pastas (relativas à raiz do repositório, ambas ignoradas pelo git):

* ``data/brutos/nc``: ficheiros tal como vêm da fonte;
* ``data/cache/nc``: tabelas normalizadas com ``ncid`` (nunca publicadas).
"""

import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import httpx
import polars as pl

from contratos.base import Fonte
from pipeline.comum.calendario import eleicao_nc
from pipeline.comum.descarga import Descarga, descarregar
from pipeline.connectors.early_vote.nc import fontes
from pipeline.connectors.early_vote.nc.processar import historico_em_cache
from pipeline.connectors.early_vote.nc.recenseamento import (
    corrigir_idade,
    ler_ficheiro_eleitores,
    ler_retrato,
    recenseados_atuais,
)

registo = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class Pastas:
    brutos: Path
    cache: Path
    referencia: Path

    @classmethod
    def omissao(cls, raiz: Path) -> "Pastas":
        return cls(
            brutos=raiz / "data" / "brutos" / "nc",
            cache=raiz / "data" / "cache" / "nc",
            referencia=raiz / "data" / "reference" / "nc",
        )


def _nome(url: str) -> str:
    return url.rsplit("/", 1)[-1]


def obter(
    url: str, pastas: Pastas, cliente: httpx.Client | None, *, descarregar_: bool
) -> Descarga:
    destino = pastas.brutos / _nome(url)
    if not descarregar_:
        if not destino.exists():
            msg = f"{destino} não existe; corre sem --sem-descarga"
            raise FileNotFoundError(msg)
        return Descarga(url, destino, False, None, None, _mtime(destino))
    descarga = descarregar(url, destino, cliente=cliente)
    estado = "novo" if descarga.alterado else "sem alterações"
    registo.info("%s: %s", _nome(url), estado)
    return descarga


def _mtime(caminho: Path) -> datetime:
    return datetime.fromtimestamp(caminho.stat().st_mtime, tz=UTC)


def fonte(descarga: Descarga) -> Fonte:
    return Fonte.model_validate(
        {
            "nome": fontes.NOME_FONTE,
            "url": descarga.url,
            "licenca": fontes.LICENCA,
            "obtida_em": descarga.obtido_em,
        }
    )


def _em_cache(origem: Path, destino: Path) -> pl.DataFrame | None:
    if destino.exists() and destino.stat().st_mtime >= origem.stat().st_mtime:
        return pl.read_parquet(destino)
    return None


def eleitores(caminho_zip: Path, pastas: Pastas) -> pl.DataFrame:
    """Ficheiro de eleitores atual normalizado (todos os estados de registo), em cache."""
    destino = pastas.cache / "eleitores_atual.parquet"
    if (tabela := _em_cache(caminho_zip, destino)) is not None:
        return tabela
    tabela = ler_ficheiro_eleitores(caminho_zip)
    pastas.cache.mkdir(parents=True, exist_ok=True)
    tabela.write_parquet(destino)
    return tabela


def recenseamento_atual(caminho_zip: Path, pastas: Pastas, ano: int) -> pl.DataFrame:
    return recenseados_atuais(eleitores(caminho_zip, pastas), ano)


def recenseamento_historico(
    caminho_zip: Path, pastas: Pastas, ano: int, nascimentos: pl.DataFrame
) -> pl.DataFrame:
    """Recenseados no dia da eleição de ``ano``, com a idade no fim desse ano."""
    destino = pastas.cache / f"recenseamento_{ano}.parquet"
    tabela = _em_cache(caminho_zip, destino)
    if tabela is None:
        registo.info("A ler o retrato do recenseamento de %s (demora vários minutos)", ano)
        tabela = ler_retrato(caminho_zip)
        pastas.cache.mkdir(parents=True, exist_ok=True)
        tabela.write_parquet(destino)
    return corrigir_idade(tabela, nascimentos, ano)


def historico(caminho_zip: Path, pastas: Pastas) -> pl.DataFrame:
    return historico_em_cache(caminho_zip, pastas.cache)


def url_boletins(ano: int) -> str:
    return fontes.url_boletins(eleicao_nc(ano).data)


def url_retrato(ano: int) -> str:
    return fontes.url_retrato_recenseamento(eleicao_nc(ano).data)
