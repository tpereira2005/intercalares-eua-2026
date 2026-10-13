"""Constrói os cubos de referência de um estado agregado (ficheiros finais de anos anteriores).

Uso::

    uv run python -m pipeline.jobs.referencia_voto_antecipado_estado --estado PA

Corre uma vez: os ficheiros finais não mudam. Grava em ``data/reference/<estado>`` só os
cubos de contagens, que são versionados.
"""

import argparse
import logging
from pathlib import Path

import httpx

from contratos.estados import CodigoEstado
from pipeline.connectors.early_vote.agregados import CONECTORES
from pipeline.jobs.voto_antecipado_estado import obter
from pipeline.transform.early_vote import agregado, persistir

registo = logging.getLogger(__name__)


def executar(
    estado: CodigoEstado, raiz: Path, anos: list[int] | None, *, descarregar_: bool
) -> None:
    conector = CONECTORES[estado]
    with httpx.Client(timeout=httpx.Timeout(60.0, read=900.0), follow_redirects=True) as cliente:
        for ano in anos or list(conector.anos_base):
            eleicao = conector.eleicao(ano)
            descarga = obter(
                conector, conector.urls_base[ano], ano, raiz, cliente if descarregar_ else None
            )
            boletins, relatorio = conector.ler(descarga.caminho, eleicao)
            cubos = agregado.cubos(boletins, eleicao)
            persistir.guardar(cubos, conector.pasta(raiz, "reference"))
            registo.info(
                "%s %s: %s boletins, %s devolvidos (%s linhas inválidas)",
                estado,
                ano,
                boletins.height,
                agregado.total_votos(cubos.votos, -1000),
                relatorio.linhas_invalidas,
            )


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--estado", required=True, choices=[e.value for e in CONECTORES])
    parser.add_argument("--anos", type=int, nargs="*", default=None)
    parser.add_argument("--raiz", type=Path, default=Path.cwd(), help="raiz do repositório")
    parser.add_argument("--sem-descarga", action="store_true", help="usar só ficheiros locais")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    executar(CodigoEstado(args.estado), args.raiz, args.anos, descarregar_=not args.sem_descarga)


if __name__ == "__main__":
    main()
