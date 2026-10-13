"""Constrói os cubos de referência da Carolina do Norte (2018, 2022, 2024).

Uso::

    uv run python -m pipeline.jobs.referencia_voto_antecipado_nc --anos 2018 2022 2024

Corre uma vez (os ficheiros finais destes anos não mudam). Descarrega o ficheiro final de
boletins, o retrato do recenseamento no dia da eleição (1 a 1,5 GB comprimido), o histórico
de voto e o ficheiro de eleitores atual (para pôr cada eleitor no distrito do mapa de 2026),
e grava em ``data/reference/nc`` apenas os cubos de contagens, que são versionados.
"""

import argparse
import logging
from pathlib import Path

import httpx
import polars as pl

from pipeline.comum.categorias import MetodoHistorico, Modalidade
from pipeline.connectors.early_vote.nc import recolha
from pipeline.connectors.early_vote.nc.fontes import URL_ELEITORES, URL_HISTORICO
from pipeline.connectors.early_vote.nc.processar import AnoProcessado, guardar_cubos, processar_ano
from pipeline.connectors.early_vote.nc.recenseamento import anos_nascimento, recenseados_atuais

registo = logging.getLogger(__name__)

TOLERANCIA_VALIDACAO = 0.01


def validar(processado: AnoProcessado, historico: pl.DataFrame) -> None:
    """Confere o total de votos antecipados com o histórico individual da NCSBE (fonte
    independente do ficheiro de boletins). Uma diferença acima de 1% indica um erro de
    leitura ou de normalização e impede a gravação."""
    ano = processado.cubos.eleicao.ano
    cubo = processado.cubos.demografico
    votos = int(cubo.filter(pl.col("modalidade") != str(Modalidade.NAO_VOTOU))["n"].sum())
    oficial = historico.filter(
        (pl.col("ano") == ano) & (pl.col("metodo") == str(MetodoHistorico.ANTECIPADO))
    ).height
    diferenca = abs(votos - oficial) / oficial if oficial else 1.0
    registo.info(
        "%s: %s votos antecipados nos boletins, %s no histórico (diferença %.2f%%)",
        ano,
        votos,
        oficial,
        100 * diferenca,
    )
    if diferenca > TOLERANCIA_VALIDACAO:
        msg = f"{ano}: diferença de {100 * diferenca:.2f}% face ao histórico oficial"
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
            d_boletins = recolha.obter(
                recolha.url_boletins(ano), pastas, cliente, descarregar_=descarregar
            )
            d_retrato = recolha.obter(
                recolha.url_retrato(ano), pastas, cliente, descarregar_=descarregar
            )
            registados = recolha.recenseamento_historico(
                d_retrato.caminho, pastas, ano, nascimentos
            )
            processado = processar_ano(
                ano,
                caminho_boletins=d_boletins.caminho,
                registados=registados,
                historico=historico,
                distrito_atual=distritos,
            )
            validar(processado, historico)
            guardar_cubos(processado.cubos, pastas.referencia)
            registo.info("%s: cubos gravados em %s", ano, pastas.referencia)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--raiz", type=Path, default=Path.cwd(), help="raiz do repositório")
    parser.add_argument("--anos", type=int, nargs="+", default=[2018, 2022, 2024])
    parser.add_argument("--sem-descarga", action="store_true", help="usar só ficheiros locais")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    executar(args.raiz, args.anos, descarregar=not args.sem_descarga)


if __name__ == "__main__":
    main()
