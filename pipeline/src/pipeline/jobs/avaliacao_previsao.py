"""Avalia a previsão congelada face aos resultados (scorecard da Fase 4).

Uso em 2026, com o ficheiro congelado e um CSV ``id,vencedor,margem``::

    uv run python -m pipeline.jobs.avaliacao_previsao \\
        --previsao previsao-2026.json --resultados resultados-2026.csv \\
        --saida data/publicado/previsao/avaliacao-2026.json

Corridas que ainda não estão no CSV contam como por decidir e ficam fora das métricas, o
que permite publicar a avaliação durante a contagem lenta. Com ``--backtest ANO`` (2018,
2022 ou 2024) reproduz a previsão desse ano a partir da referência versionada e avalia-a
com os resultados reais, exatamente como será feito em 2026.
"""

import argparse
import logging
from datetime import UTC, datetime
from pathlib import Path

from contratos.base import Fonte
from contratos.previsao import AvaliacaoPrevisao, PrevisaoCongresso
from pipeline.modelo import carregar as carga
from pipeline.modelo.avaliacao import (
    Resultado,
    avaliar_previsao,
    ler_resultados,
    resultados_de_linhas,
)
from pipeline.modelo.dados import linha_modelo
from pipeline.modelo.previsao import Dados, prever
from pipeline.modelo.publicar import montar

registo = logging.getLogger(__name__)

DESEMPATE = {2018: "R", 2022: "D", 2024: "R", 2026: "R"}
"""Partido do vice-presidente no Congresso eleito (decide um Senado 50-50)."""


def resultados_reais(dados: Dados, ano: int) -> dict[str, Resultado]:
    linhas = [
        ln
        for c in dados.corridas[ano]
        if (ln := linha_modelo(c, dados.independentes_d, dados.independentes_r)) is not None
    ]
    return resultados_de_linhas(linhas)


def backtest(ano: int, agora: datetime) -> AvaliacaoPrevisao:
    """Previsão de ``ano`` com o corte final, avaliada com os resultados reais."""
    dados = carga.carregar()
    fonte = Fonte(
        nome="Referência do modelo (Wikipédia e FiveThirtyEight)",
        url="https://github.com/tpereira2005/intercalares-eua-2026/tree/main/data/reference/modelo",
        licenca="CC BY-SA 4.0 e CC BY 4.0",
        obtida_em=agora,
    )
    publicada = montar(prever(dados, ano), fontes=[fonte], gerado_em=agora)
    return avaliar_previsao(
        publicada,
        resultados_reais(dados, ano),
        fontes=[fonte],
        gerado_em=agora,
        ambiente_real=dados.nacional.get(ano),
        desempate=DESEMPATE[ano],
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--saida", type=Path, required=True)
    parser.add_argument("--previsao", type=Path, help="Ficheiro PrevisaoCongresso congelado.")
    parser.add_argument("--resultados", type=Path, help="CSV id,vencedor,margem.")
    parser.add_argument("--ambiente-real", type=float, default=None)
    parser.add_argument("--backtest", type=int, choices=(2018, 2022, 2024), default=None)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    agora = datetime.now(UTC)
    if args.backtest is not None:
        avaliacao = backtest(args.backtest, agora)
    else:
        if args.previsao is None or args.resultados is None:
            parser.error("--previsao e --resultados são obrigatórios sem --backtest")
        previsao = PrevisaoCongresso.model_validate_json(args.previsao.read_text(encoding="utf-8"))
        avaliacao = avaliar_previsao(
            previsao,
            ler_resultados(args.resultados),
            fontes=previsao.metadados.fontes,
            gerado_em=agora,
            ambiente_real=args.ambiente_real,
            desempate=DESEMPATE[previsao.ano],
        )
    args.saida.parent.mkdir(parents=True, exist_ok=True)
    args.saida.write_text(avaliacao.model_dump_json(indent=1), encoding="utf-8")
    for camara in avaliacao.camaras:
        registo.info(
            "%s: %d corridas, Brier %.3f, log-loss %.3f, %d erradas, %d por decidir",
            camara.camara,
            camara.corridas_avaliadas,
            camara.brier,
            camara.log_loss,
            len(camara.corridas_erradas),
            len(camara.corridas_por_decidir),
        )


if __name__ == "__main__":
    main()
