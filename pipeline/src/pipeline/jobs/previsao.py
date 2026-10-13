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
from contratos.previsao import HistoricoPrevisao
from contratos.sondagens import SondagensCongresso
from pipeline.modelo import carregar as carga
from pipeline.modelo import publicar_sondagens
from pipeline.modelo.dados import LinhaModelo
from pipeline.modelo.fontes import wikipedia
from pipeline.modelo.historico import acrescentar
from pipeline.modelo.previsao import DATAS_ELEICAO, Dados, corte_final, estimar, prever
from pipeline.modelo.publicar import avaliar, montar
from pipeline.modelo.verificacoes import exigir_coerencia

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


def executar(
    saida: Path,
    *,
    corte: date | None,
    atualizar: bool,
    historico: Path | None = None,
    ficheiro_sondagens: Path | None = None,
) -> None:
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
    exigir_coerencia(ficheiro, corridas)
    saida.parent.mkdir(parents=True, exist_ok=True)
    saida.write_text(ficheiro.model_dump_json(indent=1), encoding="utf-8")
    registo.info(
        "Previsão gravada em %s: Câmara P(D)=%.3f, Senado P(D)=%.3f",
        saida,
        ficheiro.camara.prob_controlo_d,
        ficheiro.senado.prob_controlo_d,
    )
    if historico is not None:
        anterior = (
            HistoricoPrevisao.model_validate_json(historico.read_text(encoding="utf-8"))
            if historico.exists()
            else None
        )
        novo = acrescentar(anterior, ficheiro)
        historico.parent.mkdir(parents=True, exist_ok=True)
        historico.write_text(novo.model_dump_json(), encoding="utf-8")
        registo.info("Histórico com %d dias gravado em %s", len(novo.dias), historico)
    if ficheiro_sondagens is not None:
        linhas = [c.linha for c in previsao.senado.corridas if c.linha.certo is None]
        escrever_sondagens(
            ficheiro_sondagens,
            dados=dados,
            corte=corte,
            linhas=linhas,
            agregadores=agregadores,
            agora=agora,
        )


def escrever_sondagens(
    caminho: Path,
    *,
    dados: Dados,
    corte: date,
    linhas: list[LinhaModelo],
    agregadores: list[tuple[str, float]],
    agora: datetime,
) -> None:
    """Atualiza o ficheiro das sondagens (a série do voto genérico continua a anterior)."""
    anterior = (
        SondagensCongresso.model_validate_json(caminho.read_text(encoding="utf-8"))
        if caminho.exists()
        else None
    )
    ficheiro = publicar_sondagens.montar(
        dados,
        carga.ANO_ATUAL,
        corte,
        linhas,
        agregadores,
        anterior=anterior,
        fontes=fontes(agora),
        gerado_em=agora,
    )
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.write_text(ficheiro.model_dump_json(), encoding="utf-8")
    registo.info(
        "Sondagens de %d corridas e %d dias do voto genérico gravadas em %s",
        len(ficheiro.corridas),
        len(ficheiro.voto_generico),
        caminho,
    )


def apenas_sondagens(caminho: Path, *, atualizar: bool) -> None:
    """Depois do congelamento: atualiza só as sondagens, até ao dia da eleição.

    A previsão congelada não muda; as sondagens usam o corte de hoje (exclusive), sem o
    limite de 1 de novembro.
    """
    corte = min(datetime.now(UTC).date(), DATAS_ELEICAO[carga.ANO_ATUAL])
    with httpx.Client(
        headers={"User-Agent": wikipedia.USER_AGENT}, timeout=60.0, follow_redirects=True
    ) as cliente:
        corridas, sondagens, redesenhados, (_, agregadores) = carga.dados_2026(
            cliente, atualizar=atualizar
        )
    dados = carga.carregar(atual=corridas, sondagens_atuais=sondagens, redesenho_atual=redesenhados)
    _, linhas_senado = estimar(dados, carga.ANO_ATUAL, "senado")
    linhas = [ln for ln in linhas_senado[carga.ANO_ATUAL] if ln.certo is None]
    escrever_sondagens(
        caminho,
        dados=dados,
        corte=corte,
        linhas=linhas,
        agregadores=agregadores,
        agora=datetime.now(UTC),
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--saida", type=Path, help="Ficheiro da previsão (exceto com --apenas-sondagens)."
    )
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
    parser.add_argument(
        "--historico",
        type=Path,
        default=None,
        help="Ficheiro do histórico diário a atualizar (criado se não existir).",
    )
    parser.add_argument(
        "--sondagens",
        type=Path,
        default=None,
        help="Ficheiro das sondagens para o site a atualizar (criado se não existir).",
    )
    parser.add_argument(
        "--apenas-sondagens",
        action="store_true",
        help="Depois do congelamento: atualiza só o ficheiro das sondagens (até à eleição).",
    )
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    if args.apenas_sondagens:
        if args.sondagens is None:
            parser.error("--apenas-sondagens precisa de --sondagens")
        apenas_sondagens(args.sondagens, atualizar=not args.sem_descarga)
        return
    if args.saida is None:
        parser.error("--saida é obrigatório")
    executar(
        args.saida,
        corte=args.corte,
        atualizar=not args.sem_descarga,
        historico=args.historico,
        ficheiro_sondagens=args.sondagens,
    )


if __name__ == "__main__":
    main()
