"""Constrói os cubos do eleitorado final da Carolina do Norte (todos os que votaram).

Uso::

    uv run python -m pipeline.jobs.eleitorado_final_nc --anos 2016 2018 2020 2022 2024

Os cubos de referência do voto antecipado só distinguem quem votou cedo; quem votou no dia
fica em ``nao_votou``. Este job junta o histórico individual (``ncvhis``) ao retrato do
recenseamento no dia de cada eleição e grava ``data/reference/nc/cubo_final_<ano>.parquet``
com contagens por condado, distrito do mapa de 2026, faixa, partido e método (antecipado
ou no dia). Serve o modelo etário. Corre uma vez: os ficheiros destes anos não mudam.
"""

import argparse
import logging
from pathlib import Path

import httpx
import polars as pl

from pipeline.connectors.early_vote.nc import recolha
from pipeline.connectors.early_vote.nc.fontes import URL_ELEITORES, URL_HISTORICO
from pipeline.connectors.early_vote.nc.recenseamento import anos_nascimento, recenseados_atuais
from pipeline.transform.early_vote.cubos import cubo_final

registo = logging.getLogger(__name__)

TOLERANCIA_COBERTURA = 0.01
"""Fração máxima de votantes do histórico que pode faltar no retrato do recenseamento."""


def caminho_final(pasta: Path, ano: int) -> Path:
    return pasta / f"cubo_final_{ano}.parquet"


def validar(cubo: pl.DataFrame, historico: pl.DataFrame, ano: int) -> None:
    """O cubo tem de cobrir quase todos os votantes do histórico desse ano. Os que faltam
    não estavam no retrato (recenseamento posterior, ficheiros fundidos, etc.)."""
    no_cubo = int(cubo["n"].sum())
    oficial = historico.filter(pl.col("ano") == ano).height
    falta = (oficial - no_cubo) / oficial if oficial else 1.0
    registo.info(
        "%s: %s votantes no cubo, %s no histórico (faltam %.2f%%)",
        ano,
        no_cubo,
        oficial,
        100 * falta,
    )
    if falta > TOLERANCIA_COBERTURA or no_cubo > oficial:
        msg = f"{ano}: o cubo cobre {no_cubo} de {oficial} votantes do histórico"
        raise RuntimeError(msg)


def executar(raiz: Path, anos: list[int], *, descarregar: bool) -> None:
    pastas = recolha.Pastas.omissao(raiz)
    with httpx.Client(timeout=httpx.Timeout(60.0, read=600.0), follow_redirects=True) as cliente:
        d_eleitores = recolha.obter(URL_ELEITORES, pastas, cliente, descarregar_=descarregar)
        d_historico = recolha.obter(URL_HISTORICO, pastas, cliente, descarregar_=descarregar)
        historico = recolha.historico(d_historico.caminho, pastas)
        eleitores = recolha.eleitores(d_eleitores.caminho, pastas)
        nascimentos = anos_nascimento(eleitores)
        distritos = recenseados_atuais(eleitores, 2026).select(
            "ncid", pl.col("distrito").alias("distrito_atual")
        )
        del eleitores
        for ano in anos:
            d_retrato = recolha.obter(
                recolha.url_retrato(ano), pastas, cliente, descarregar_=descarregar
            )
            registados = recolha.recenseamento_historico(
                d_retrato.caminho, pastas, ano, nascimentos
            )
            cubo = cubo_final(registados, historico, ano, distritos)
            validar(cubo, historico, ano)
            pastas.referencia.mkdir(parents=True, exist_ok=True)
            cubo.write_parquet(
                caminho_final(pastas.referencia, ano),
                compression="zstd",
                compression_level=19,
                statistics=False,
            )
            registo.info("%s: cubo final gravado em %s", ano, pastas.referencia)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--raiz", type=Path, default=Path.cwd(), help="raiz do repositório")
    parser.add_argument("--anos", type=int, nargs="+", default=[2016, 2018, 2020, 2022, 2024])
    parser.add_argument("--sem-descarga", action="store_true", help="usar só ficheiros locais")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    executar(args.raiz, args.anos, descarregar=not args.sem_descarga)


if __name__ == "__main__":
    main()
