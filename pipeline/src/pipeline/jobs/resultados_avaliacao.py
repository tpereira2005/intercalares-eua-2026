"""Exporta o CSV ``id,vencedor,margem`` para a avaliação da previsão.

Uso::

    uv run python -m pipeline.jobs.resultados_avaliacao \\
        --pasta data/publicado/resultados --saida resultados-2026.csv

Lê os ``<estado>.json`` publicados (contrato ``ResultadosEstado``) e escreve só as
corridas com todas as secções apuradas (ver ``transform.resultados.avaliacao``).
"""

import argparse
import logging
from pathlib import Path

from contratos.resultados import ResultadosEstado
from pipeline.transform.resultados.avaliacao import csv_avaliacao

registo = logging.getLogger(__name__)

IGNORADOS = {"nacional.json", "parciais.json"}


def executar(pasta: Path, saida: Path) -> Path:
    estados = [
        ResultadosEstado.model_validate_json(p.read_text(encoding="utf-8"))
        for p in sorted(pasta.glob("*.json"))
        if p.name not in IGNORADOS
    ]
    texto = csv_avaliacao(estados)
    saida.parent.mkdir(parents=True, exist_ok=True)
    saida.write_text(texto, encoding="utf-8")
    registo.info("Escrito %s: %s corridas", saida, texto.count("\n") - 1)
    return saida


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--pasta", type=Path, required=True)
    parser.add_argument("--saida", type=Path, required=True)
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    executar(args.pasta, args.saida)


if __name__ == "__main__":
    main()
