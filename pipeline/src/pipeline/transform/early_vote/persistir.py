"""Gravação e leitura dos cubos agregados (versionados em ``data/reference/<estado>``)."""

from pathlib import Path

import polars as pl

from pipeline.comum.calendario import EleicaoGeral
from pipeline.transform.early_vote.agregado import CubosAgregados


def caminho(pasta: Path, tipo: str, ano: int) -> Path:
    return pasta / f"cubo_{tipo}_{ano}.parquet"


def guardar(cubos: CubosAgregados, pasta: Path) -> None:
    pasta.mkdir(parents=True, exist_ok=True)
    for tipo, tabela in (("votos", cubos.votos), ("pedidos", cubos.pedidos)):
        tabela.write_parquet(
            caminho(pasta, tipo, cubos.eleicao.ano),
            compression="zstd",
            compression_level=19,
            statistics=False,
        )


def existe(pasta: Path, ano: int) -> bool:
    return caminho(pasta, "votos", ano).exists()


def ler(pasta: Path, eleicao: EleicaoGeral) -> CubosAgregados:
    return CubosAgregados(
        eleicao,
        pl.read_parquet(caminho(pasta, "votos", eleicao.ano)),
        pl.read_parquet(caminho(pasta, "pedidos", eleicao.ano)),
    )
