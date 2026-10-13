"""Do ficheiro bruto ao painel e aos cubos, para um ano da Carolina do Norte.

As tabelas intermédias com ``ncid`` ficam em ``data/cache/nc`` (ignorado pelo git). Só os
cubos, que não têm dados pessoais, saem daqui para o repositório ou para publicação.
"""

from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

import polars as pl

from pipeline.comum.calendario import DATAS_ELEICOES_GERAIS, eleicao_nc
from pipeline.comum.leitura import data_geracao
from pipeline.connectors.early_vote.nc.boletins import ResultadoBoletins, ler_boletins, votantes
from pipeline.connectors.early_vote.nc.historico import ler_historico
from pipeline.transform.early_vote.cubos import cubo_demografico, cubo_geografico
from pipeline.transform.early_vote.painel import construir_painel
from pipeline.transform.early_vote.relatorio import CubosAno

ANOS_HISTORICO = (2016, 2018, 2020, 2022, 2024)


def eleicoes_historico() -> dict[int, date]:
    return {ano: DATAS_ELEICOES_GERAIS[ano] for ano in ANOS_HISTORICO}


@dataclass(frozen=True, slots=True)
class AnoProcessado:
    cubos: CubosAno
    boletins: ResultadoBoletins
    dados_ate: date | None
    """Último dia com votos devolvidos no ficheiro (até ao dia da eleição)."""

    votantes_sem_recenseamento: int
    """Votantes que não estavam no ficheiro de recenseados (registo no próprio dia, etc.)."""


def historico_em_cache(caminho_zip: Path, cache: Path) -> pl.DataFrame:
    """Lê o histórico individual, reutilizando a cache se o zip não mudou."""
    destino = cache / "historico.parquet"
    if destino.exists() and destino.stat().st_mtime >= caminho_zip.stat().st_mtime:
        return pl.read_parquet(destino)
    historico = ler_historico(caminho_zip, eleicoes_historico())
    cache.mkdir(parents=True, exist_ok=True)
    historico.write_parquet(destino)
    return historico


def processar_ano(
    ano: int,
    *,
    caminho_boletins: Path,
    registados: pl.DataFrame,
    historico: pl.DataFrame | None,
    distrito_atual: pl.DataFrame | None,
) -> AnoProcessado:
    eleicao = eleicao_nc(ano)
    resultado = ler_boletins(caminho_boletins)
    votos = votantes(resultado.boletins)
    ref = eleicao.referencia_historico
    data_ref = DATAS_ELEICOES_GERAIS.get(ref) if ref is not None else None
    painel = construir_painel(
        registados,
        votos,
        historico=historico,
        eleicao=eleicao,
        data_referencia=data_ref,
        distrito_atual=distrito_atual,
    )
    fora = votos.join(registados.select("ncid"), on="ncid", how="anti").height
    ate = ultimo_dia_completo(votos, eleicao.data, data_geracao(caminho_boletins))
    return AnoProcessado(
        cubos=CubosAno(eleicao, cubo_demografico(painel), cubo_geografico(painel)),
        boletins=resultado,
        dados_ate=ate,
        votantes_sem_recenseamento=fora,
    )


def ultimo_dia_completo(
    votos: pl.DataFrame, data_eleicao: date, gerado_em: date | None
) -> date | None:
    """Último dia com dados completos.

    O ficheiro diário é gerado de madrugada e pode trazer alguns boletins com a data desse
    dia (registos lançados durante a noite). Esse dia está incompleto, por isso o último
    dia completo é a véspera da geração, e nunca depois da eleição.
    """
    limite = data_eleicao if gerado_em is None else min(data_eleicao, gerado_em - timedelta(days=1))
    ultimo = votos.filter(pl.col("data_devolucao") <= limite)["data_devolucao"].max()
    return ultimo if isinstance(ultimo, date) else None


def caminho_cubo(pasta: Path, tipo: str, ano: int) -> Path:
    return pasta / f"cubo_{tipo}_{ano}.parquet"


def guardar_cubos(cubos: CubosAno, pasta: Path) -> None:
    pasta.mkdir(parents=True, exist_ok=True)
    for tipo, tabela in (("demografico", cubos.demografico), ("geografico", cubos.geografico)):
        tabela.write_parquet(
            caminho_cubo(pasta, tipo, cubos.eleicao.ano),
            compression="zstd",
            compression_level=19,
            statistics=False,
        )


def ler_cubos(pasta: Path, ano: int) -> CubosAno:
    return CubosAno(
        eleicao_nc(ano),
        pl.read_parquet(caminho_cubo(pasta, "demografico", ano)),
        pl.read_parquet(caminho_cubo(pasta, "geografico", ano)),
    )
