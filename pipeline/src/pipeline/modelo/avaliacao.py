"""Avaliação da previsão congelada face aos resultados (scorecard da Fase 4).

Funciona sobre o ficheiro publicado (``PrevisaoCongresso``), por isso avalia exatamente o
que esteve no site. Todas as métricas são simétricas: trocar os partidos na previsão e nos
resultados dá os mesmos valores (o viés troca de sinal). A calibração usa a probabilidade
do favorito de cada corrida, seja qual for o partido.
"""

import csv
import math
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from contratos.base import Fonte, Metadados
from contratos.previsao import (
    AvaliacaoCamara,
    AvaliacaoPrevisao,
    CamaraCongresso,
    FaixaCalibracao,
    PrevisaoCongresso,
    PrevisaoCorrida,
    ResumoCamara,
)
from pipeline.comum.erros import ErroFormatoFonte
from pipeline.modelo.dados import LinhaModelo

FAIXAS = ((0.5, 0.6), (0.6, 0.7), (0.7, 0.8), (0.8, 0.9), (0.9, 0.95), (0.95, 1.0))
PROB_MINIMA = 1e-6
"""As probabilidades limitam-se a [1e-6, 1 - 1e-6] no log-loss, para que uma corrida dada
como certa e perdida não torne a média infinita."""


@dataclass(frozen=True, slots=True)
class Resultado:
    """Resultado de uma corrida no mesmo referencial da previsão (lado D e lado R)."""

    vencedor: str
    """``D`` (lado democrata, incluindo independente nesse lado) ou ``R``."""

    margem: float | None = None
    """Margem final D-R em pontos, quando já há contagem suficiente."""


def resultados_de_linhas(linhas: Iterable[LinhaModelo]) -> dict[str, Resultado]:
    """Resultados de um ano terminado a partir das linhas do modelo (para os backtests)."""
    resultado: dict[str, Resultado] = {}
    for linha in linhas:
        if linha.vencedor in {"D", "R"}:
            resultado[linha.id] = Resultado(linha.vencedor, linha.margem)
    return resultado


def ler_resultados(caminho: Path) -> dict[str, Resultado]:
    """Lê um CSV ``id,vencedor,margem`` (margem vazia enquanto a contagem não acaba)."""
    resultado: dict[str, Resultado] = {}
    with caminho.open(encoding="utf-8", newline="") as ficheiro:
        for linha in csv.DictReader(ficheiro):
            vencedor = linha["vencedor"].strip().upper()
            if vencedor not in {"D", "R"}:
                raise ErroFormatoFonte(f"Vencedor inválido em {linha['id']}: {vencedor!r}")
            margem = linha.get("margem", "").strip()
            resultado[linha["id"].strip()] = Resultado(vencedor, float(margem) if margem else None)
    return resultado


def _limitar(p: float) -> float:
    return min(max(p, PROB_MINIMA), 1.0 - PROB_MINIMA)


def calibracao(pares: list[tuple[float, bool]]) -> tuple[FaixaCalibracao, ...]:
    """``pares``: (probabilidade do lado D, D ganhou). Agrupa pela probabilidade do favorito."""
    favoritos = [(p, ganhou) if p >= 0.5 else (1.0 - p, not ganhou) for p, ganhou in pares]
    faixas: list[FaixaCalibracao] = []
    for i, (inferior, superior) in enumerate(FAIXAS):
        ultima = i == len(FAIXAS) - 1
        dentro = [
            (p, g) for p, g in favoritos if inferior <= p < superior or (ultima and p == superior)
        ]
        faixas.append(
            FaixaCalibracao(
                limite_inferior=inferior,
                limite_superior=superior,
                corridas=len(dentro),
                prob_media=sum(p for p, _ in dentro) / len(dentro) if dentro else None,
                frequencia=sum(g for _, g in dentro) / len(dentro) if dentro else None,
            )
        )
    return tuple(faixas)


def _controlo(lugares_d: int, total: int, desempate: str) -> str:
    if 2 * lugares_d > total:
        return "D"
    if 2 * lugares_d < total:
        return "R"
    return desempate


def avaliar_camara(
    resumo: ResumoCamara,
    corridas: list[PrevisaoCorrida],
    resultados: Mapping[str, Resultado],
    desempate: str,
) -> AvaliacaoCamara:
    disputadas = [c for c in corridas if c.decidida is None]
    avaliadas = [c for c in disputadas if c.id in resultados]
    por_decidir = tuple(c.id for c in disputadas if c.id not in resultados)
    pares = [(c.prob_d, resultados[c.id].vencedor == "D") for c in avaliadas]
    n = len(pares)
    brier = sum((p - g) ** 2 for p, g in pares) / n if n else 0.0
    log_loss = -sum(math.log(_limitar(p if g else 1.0 - p)) for p, g in pares) / n if n else 0.0
    erradas = tuple(c.id for c, (p, g) in zip(avaliadas, pares, strict=True) if (p > 0.5) != g)
    com_margem = [(c, m) for c in avaliadas if (m := resultados[c.id].margem) is not None]
    erros = [c.margem_prevista - m for c, m in com_margem]

    lugares_reais: int | None = None
    prob_vencedor: float | None = None
    if not por_decidir:
        ganhos_d = sum(resultados[c.id].vencedor == "D" for c in avaliadas)
        decididas_d = sum(c.decidida in {"D", "I"} for c in corridas if c.decidida is not None)
        lugares_reais = resumo.lugares_fora_de_jogo_d + decididas_d + ganhos_d
        controlo = _controlo(lugares_reais, resumo.lugares_total, desempate)
        prob_vencedor = resumo.prob_controlo_d if controlo == "D" else resumo.prob_controlo_r
    camara: CamaraCongresso = resumo.camara
    return AvaliacaoCamara(
        camara=camara,
        corridas_avaliadas=n,
        corridas_por_decidir=por_decidir,
        corridas_erradas=erradas,
        acertos=1.0 - len(erradas) / n if n else 0.0,
        brier=brier,
        log_loss=log_loss,
        corridas_com_margem=len(com_margem),
        erro_absoluto_margem=sum(abs(e) for e in erros) / len(erros) if erros else None,
        vies_margem=sum(erros) / len(erros) if erros else None,
        cobertura_80=(
            sum(c.margem_p10 <= m <= c.margem_p90 for c, m in com_margem) / len(com_margem)
            if com_margem
            else None
        ),
        calibracao=calibracao(pares),
        prob_controlo_vencedor=prob_vencedor,
        lugares_d_previstos=resumo.lugares_d_mediana,
        lugares_d_reais=lugares_reais,
    )


def avaliar_previsao(
    previsao: PrevisaoCongresso,
    resultados: Mapping[str, Resultado],
    *,
    fontes: Iterable[Fonte],
    gerado_em: datetime,
    ambiente_real: float | None = None,
    desempate: str = "R",
) -> AvaliacaoPrevisao:
    """Avalia a previsão publicada; ``desempate`` é o partido do vice-presidente."""
    camaras = tuple(
        avaliar_camara(
            resumo,
            [c for c in previsao.corridas if c.camara == resumo.camara],
            resultados,
            desempate,
        )
        for resumo in (previsao.camara, previsao.senado)
    )
    return AvaliacaoPrevisao(
        metadados=Metadados(gerado_em=gerado_em, fontes=tuple(fontes)),
        ano=previsao.ano,
        corte=previsao.corte,
        ambiente_previsto=previsao.ambiente.margem,
        ambiente_real=ambiente_real,
        camaras=camaras,
    )
