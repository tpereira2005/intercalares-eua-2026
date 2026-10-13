"""Análise de sensibilidade da previsão: quanto mudam os números com cada escolha do modelo.

Uso::

    uv run python -m pipeline.jobs.sensibilidade_previsao --saida sensibilidade.json \\
        --markdown sensibilidade.md

Corre a previsão de 2026 (com os mesmos dados do job ``previsao``) e os backtests de 2018,
2022 e 2024 com cada variante de ``Ajustes``, uma escolha de cada vez. Para 2026 regista a
probabilidade de controlo e os lugares de cada câmara; nos backtests, o Brier médio e a
cobertura dos intervalos de 80%. As variantes do ambiente nacional testam-se sempre com os
dois sinais, e não se avaliam nos backtests (deslocar o ambiente num ano passado só mede
o erro real desse ano). Nada aqui altera a previsão publicada.
"""

import argparse
import json
import logging
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime
from pathlib import Path

import httpx
import numpy as np

from pipeline.jobs.previsao import ANOS_BACKTEST, DESEMPATE_REAL
from pipeline.modelo import carregar as carga
from pipeline.modelo.fontes import wikipedia
from pipeline.modelo.previsao import (
    AJUSTES_PUBLICADOS,
    Ajustes,
    Dados,
    Previsao,
    corte_final,
    prever,
)
from pipeline.modelo.publicar import avaliar
from pipeline.modelo.simulacao import ResultadoCamara

registo = logging.getLogger(__name__)

VEZES = "\u00d7"
TRACO = "\u2013"
MENOS = "\u2212"


@dataclass(frozen=True, slots=True)
class Variante:
    nome: str
    ajustes: Ajustes
    backtest: bool = True
    ambiente_proprio: bool = False
    """Ignora a média dos agregadores: o ambiente vem da média própria do voto genérico ou,
    sem sondagens do voto genérico, das sondagens do Senado (como no backtest de 2024)."""


VARIANTES: tuple[Variante, ...] = (
    Variante("Modelo publicado", AJUSTES_PUBLICADOS),
    *(
        Variante(
            f"Ambiente {d:+d} ponto{'s' if abs(d) > 1 else ''}".replace("-", MENOS),
            Ajustes(desvio_ambiente=float(d)),
            backtest=False,
        )
        for d in (-3, -2, -1, 1, 2, 3)
    ),
    Variante("Ambiente sem os agregadores", AJUSTES_PUBLICADOS, False, True),
    Variante(f"Erro do ambiente {VEZES} 0,75", Ajustes(fator_sd_nacional=0.75)),
    Variante(f"Erro do ambiente {VEZES} 1,25", Ajustes(fator_sd_nacional=1.25)),
    Variante(f"Erro do ambiente {VEZES} 1,5", Ajustes(fator_sd_nacional=1.5)),
    Variante("t com 3 graus de liberdade", Ajustes(graus_liberdade=3)),
    Variante("t com 30 graus de liberdade (quase normal)", Ajustes(graus_liberdade=30)),
    Variante(f"Erro de cada corrida {VEZES} 0,75", Ajustes(fator_sd_corrida=0.75)),
    Variante(f"Erro de cada corrida {VEZES} 1,25", Ajustes(fator_sd_corrida=1.25)),
    Variante(f"Erro das sondagens {VEZES} 0,75", Ajustes(fator_erro_sondagens=0.75)),
    Variante(f"Erro das sondagens {VEZES} 1,5", Ajustes(fator_erro_sondagens=1.5)),
    Variante("Meia-vida das sondagens de 7 dias", Ajustes(meia_vida_dias=7.0)),
    Variante("Meia-vida das sondagens de 28 dias", Ajustes(meia_vida_dias=28.0)),
    Variante("Sem sondagens do Senado (só fundamentos)", Ajustes(sem_sondagens_senado=True)),
)


def _camara(r: ResultadoCamara) -> dict[str, float | int]:
    lugares = r.lugares_d
    return {
        "prob_controlo_d": r.prob_controlo_d,
        "lugares_d_mediana": int(np.percentile(lugares, 50, method="inverted_cdf")),
        "lugares_d_p10": int(np.percentile(lugares, 10, method="inverted_cdf")),
        "lugares_d_p90": int(np.percentile(lugares, 90, method="inverted_cdf")),
    }


def _backtests(dados: Dados, ajustes: Ajustes) -> dict[str, dict[str, float]]:
    resultado: dict[str, dict[str, float]] = {}
    por_camara: dict[str, list[tuple[float, float]]] = {"camara": [], "senado": []}
    for ano in ANOS_BACKTEST:
        for b in avaliar(prever(dados, ano, ajustes=ajustes), dados, DESEMPATE_REAL[ano]):
            por_camara[b.camara].append((b.brier, b.cobertura_80))
    for camara, valores in por_camara.items():
        resultado[camara] = {
            "brier": float(np.mean([v[0] for v in valores])),
            "cobertura_80": float(np.mean([v[1] for v in valores])),
        }
    return resultado


def analisar(
    dados: Dados,
    corte: date,
    ambiente_publicado: tuple[float, str] | None,
    variantes: Sequence[Variante] = VARIANTES,
) -> list[dict[str, object]]:
    linhas: list[dict[str, object]] = []
    for v in variantes:
        publicado = None if v.ambiente_proprio else ambiente_publicado
        previsao: Previsao = prever(
            dados, carga.ANO_ATUAL, corte=corte, ambiente_publicado=publicado, ajustes=v.ajustes
        )
        linha: dict[str, object] = {
            "variante": v.nome,
            "ajustes": asdict(v.ajustes),
            "ambiente": previsao.ambiente.margem,
            "fonte_ambiente": previsao.fonte_ambiente,
            "camara": _camara(previsao.camara),
            "senado": _camara(previsao.senado),
            "backtests": _backtests(dados, v.ajustes) if v.backtest else None,
        }
        linhas.append(linha)
        registo.info(
            "%-45s Câmara %.3f, Senado %.3f",
            v.nome,
            previsao.camara.prob_controlo_d,
            previsao.senado.prob_controlo_d,
        )
    return linhas


def _pct(x: object) -> str:
    return f"{100 * float(str(x)):.0f}%".replace(".", ",")


def _dec(x: float) -> str:
    return f"{x:.3f}".replace(".", ",")


def markdown(linhas: Sequence[dict[str, object]]) -> str:
    """Tabela em português de Portugal para a metodologia."""
    cab = (
        f"| Variante | Câmara P(D) | Lugares D (p10{TRACO}p90) | Senado P(D) "
        f"| Lugares D (p10{TRACO}p90) "
        "| Brier Câmara | Brier Senado | Cobertura 80% Câmara | Cobertura 80% Senado |\n"
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |\n"
    )
    corpo = []
    for ln in linhas:
        c = ln["camara"]
        s = ln["senado"]
        b = ln["backtests"]
        if not isinstance(c, dict) or not isinstance(s, dict):
            raise TypeError(ln)
        if isinstance(b, dict):
            extra = (
                f"{_dec(b['camara']['brier'])} | {_dec(b['senado']['brier'])} | "
                f"{_pct(b['camara']['cobertura_80'])} | {_pct(b['senado']['cobertura_80'])}"
            )
        else:
            extra = "— | — | — | —"
        corpo.append(
            f"| {ln['variante']} | {_pct(c['prob_controlo_d'])} | {c['lugares_d_mediana']} "
            f"({c['lugares_d_p10']}{TRACO}{c['lugares_d_p90']}) | {_pct(s['prob_controlo_d'])} | "
            f"{s['lugares_d_mediana']} ({s['lugares_d_p10']}{TRACO}{s['lugares_d_p90']}) "
            f"| {extra} |"
        )
    return cab + "\n".join(corpo) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--saida", type=Path, required=True, help="relatório em JSON")
    parser.add_argument("--markdown", type=Path, help="tabela para a metodologia")
    parser.add_argument("--corte", type=date.fromisoformat, default=None)
    parser.add_argument("--sem-descarga", action="store_true")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    corte = min(args.corte or datetime.now(UTC).date(), corte_final(carga.ANO_ATUAL))
    with httpx.Client(
        headers={"User-Agent": wikipedia.USER_AGENT}, timeout=60.0, follow_redirects=True
    ) as cliente:
        corridas, sondagens, redesenhados, (generico, agregadores) = carga.dados_2026(
            cliente, atualizar=not args.sem_descarga
        )
    dados = carga.carregar(atual=corridas, sondagens_atuais=sondagens, redesenho_atual=redesenhados)
    publicado = (generico, "agregadores") if agregadores else None
    linhas = analisar(dados, corte, publicado)
    args.saida.parent.mkdir(parents=True, exist_ok=True)
    relatorio = {"corte": corte.isoformat(), "variantes": linhas}
    args.saida.write_text(json.dumps(relatorio, indent=1, ensure_ascii=False), encoding="utf-8")
    if args.markdown is not None:
        args.markdown.write_text(markdown(linhas), encoding="utf-8")


if __name__ == "__main__":
    main()
