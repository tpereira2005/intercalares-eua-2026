"""Reconstrói as tabelas de referência do modelo de previsão (eleições de 2012 a 2024).

Uso::

    uv run python -m pipeline.jobs.referencia_modelo

Corre uma vez: lê as páginas anuais da Wikipédia (resultados, PVI e incumbentes da Câmara
e do Senado), as sondagens das corridas ao Senado de 2024 e o ficheiro ``raw_polls.csv``
da FiveThirtyEight, e grava em ``data/reference/modelo`` as tabelas versionadas. As
páginas descarregadas ficam em ``data/brutos/modelo`` (ignorado pelo git).
"""

import logging

from pipeline.modelo.carregar import construir_referencia


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    construir_referencia()


if __name__ == "__main__":
    main()
