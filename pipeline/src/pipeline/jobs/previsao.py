"""Calcula a previsão para a Câmara e o Senado e grava o ficheiro publicado.

Uso::

    uv run python -m pipeline.jobs.previsao --saida data/publicado/previsao/2026.json

Lê a referência versionada em ``data/reference/modelo`` (eleições de 2012 a 2024),
descarrega da Wikipédia as listas de candidatos, os PVI e as sondagens de 2026 e corre os
backtests de 2018, 2022 e 2024 com o mesmo código. Depois de 1 de novembro de 2026 o
corte fica fixo: a previsão publicada é a congelada.
"""

import argparse
import logging
from datetime import UTC, date, datetime
from pathlib import Path

import httpx

from contratos.base import Fonte
from pipeline.modelo import carregar as carga
from pipeline.modelo.fontes import wikipedia
from pipeline.modelo.previsao import corte_final, prever
from pipeline.modelo.publicar import avaliar, montar

registo = logging.getLogger(__name__)

ANOS_BACKTEST = (2018, 2022, 2024)
DESEMPATE_REAL = {2018: "R", 2022: "D", 2024: "R"}
"""Partido do vice-presidente no Congresso eleito (decide um Senado 50-50)."""

URL_WIKIPEDIA = "https://en.wikipedia.org/wiki/"


def fontes(agora: datetime) -> list[Fonte]:
    titulos = (carga.titulo_casa(carga.ANO_ATUAL), carga.titulo_senado(carga.ANO_ATUAL))
    resultado = [
        Fonte(
            nome=f"Wikipédia: {titulo}",
            url=URL_WIKIPEDIA + titulo.replace(" ", "_"),
            licenca="CC BY-SA 4.0",
            obtida_em=agora,
        )
        for titulo in titulos
    ]
    resultado.append(
        Fonte(
            nome="FiveThirtyEight: raw_polls.csv (sondagens e resultados até 2022)",
            url=carga.URL_538,
            licenca="CC BY 4.0",
            obtida_em=agora,
        )
    )
    return resultado


def executar(saida: Path, *, corte: date | None, atualizar: bool) -> None:
    final = corte_final(carga.ANO_ATUAL)
    corte = min(corte or datetime.now(UTC).date(), final)
    with httpx.Client(
        headers={"User-Agent": wikipedia.USER_AGENT}, timeout=60.0, follow_redirects=True
    ) as cliente:
        corridas, sondagens, redesenhados, (generico, agregadores) = carga.dados_2026(
            cliente, atualizar=atualizar
        )
    dados = carga.carregar(atual=corridas, sondagens_atuais=sondagens, redesenho_atual=redesenhados)
    backtests = []
    for ano in ANOS_BACKTEST:
        backtests.extend(avaliar(prever(dados, ano), dados, DESEMPATE_REAL[ano]))
    previsao = prever(
        dados,
        carga.ANO_ATUAL,
        corte=corte,
        ambiente_publicado=(generico, "agregadores") if agregadores else None,
    )
    agora = datetime.now(UTC)
    ficheiro = montar(
        previsao,
        fontes=fontes(agora),
        gerado_em=agora,
        agregadores=agregadores,
        backtests=backtests,
    )
    saida.parent.mkdir(parents=True, exist_ok=True)
    saida.write_text(ficheiro.model_dump_json(indent=1), encoding="utf-8")
    registo.info(
        "Previsão gravada em %s: Câmara P(D)=%.3f, Senado P(D)=%.3f",
        saida,
        ficheiro.camara.prob_controlo_d,
        ficheiro.senado.prob_controlo_d,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--saida", type=Path, required=True)
    parser.add_argument(
        "--corte",
        type=date.fromisoformat,
        default=None,
        help="Data de corte (AAAA-MM-DD); por omissão hoje, nunca depois de 1 de novembro.",
    )
    parser.add_argument(
        "--sem-descarga",
        action="store_true",
        help="Usa só as páginas da Wikipédia já guardadas em data/brutos/modelo/wiki.",
    )
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    executar(args.saida, corte=args.corte, atualizar=not args.sem_descarga)


if __name__ == "__main__":
    main()
