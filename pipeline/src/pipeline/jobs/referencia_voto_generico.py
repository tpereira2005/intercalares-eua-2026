"""Reconstrói a série diária dos agregadores do voto genérico de 2026 (uma vez).

Uso::

    uv run python -m pipeline.jobs.referencia_voto_generico --inicio 2026-01-01

A Wikipédia de 2026 só mostra os valores atuais dos agregadores. Para o passado, lê-se o
quadro "Generic congressional ballot aggregate polls" em cada revisão da página anual da
Câmara: para cada dia, a última revisão feita até ao fim desse dia. Os pedidos são
lentos de propósito (um de cada vez, com pausa, recuo exponencial nos 429) e ficam em
cache em ``data/brutos/modelo/wiki``: uma revisão nunca é pedida duas vezes, por isso o
job pode ser interrompido e retomado. O resultado fica versionado em
``data/reference/modelo/voto_generico_2026.csv`` (ver ``data/PROVENIENCIA.md``).
"""

import argparse
import csv
import logging
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import httpx

from pipeline.modelo import carregar as carga
from pipeline.modelo.dados import voto_generico_agregadores
from pipeline.modelo.fontes import revisoes, wikipedia

registo = logging.getLogger(__name__)

SAIDA = Path("data/reference/modelo/voto_generico_2026.csv")
CAMPOS = ("data", "revisao", "agregador", "margem")


def reconstruir(inicio: date, fim: date, cliente: httpx.Client) -> list[dict[str, str]]:
    titulo = carga.titulo_casa(carga.ANO_ATUAL)
    lista = revisoes.listar(titulo, inicio, fim, carga.CACHE / "revisoes", cliente)
    por_dia = revisoes.ultima_por_dia(lista, inicio, fim)
    registo.info(
        "%d revisões; %d dias; %d revisões distintas a ler",
        len(lista),
        len(por_dia),
        len({r.oldid for r in por_dia.values()}),
    )
    linhas: list[dict[str, str]] = []
    lidas: dict[int, list[tuple[str, float]] | None] = {}
    for dia, revisao in sorted(por_dia.items()):
        if revisao.oldid not in lidas:
            texto = wikipedia.obter(
                titulo, carga.CACHE / "revisoes", oldid=revisao.oldid, cliente=cliente
            )
            try:
                _, valores = voto_generico_agregadores(texto)
            except ValueError:
                valores = None
            lidas[revisao.oldid] = valores
        valores = lidas[revisao.oldid]
        if valores is None:
            continue
        linhas.extend(
            {
                "data": dia.isoformat(),
                "revisao": str(revisao.oldid),
                "agregador": n,
                "margem": f"{m:g}",
            }
            for n, m in valores
        )
    return linhas


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--inicio", type=date.fromisoformat, default=date(2026, 1, 1))
    parser.add_argument(
        "--fim",
        type=date.fromisoformat,
        default=None,
        help="último dia (por omissão, ontem)",
    )
    parser.add_argument("--saida", type=Path, default=SAIDA)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    fim = args.fim or datetime.now(UTC).date() - timedelta(days=1)
    with httpx.Client(
        headers={"User-Agent": wikipedia.USER_AGENT}, timeout=60.0, follow_redirects=True
    ) as cliente:
        linhas = reconstruir(args.inicio, fim, cliente)
    args.saida.parent.mkdir(parents=True, exist_ok=True)
    with args.saida.open("w", encoding="utf-8", newline="") as f:
        escritor = csv.DictWriter(f, fieldnames=CAMPOS, lineterminator="\n")
        escritor.writeheader()
        escritor.writerows(linhas)
    registo.info(
        "%d dias com agregadores gravados em %s", len({ln["data"] for ln in linhas}), args.saida
    )


if __name__ == "__main__":
    main()
