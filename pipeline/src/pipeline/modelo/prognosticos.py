"""Classificações de especialistas (Cook, Sabato, Inside Elections) como sinal por corrida.

Cada classificação vira uma pontuação com sinal: seguro 3, provável 2, inclinado 1, ligeiro
0,5 e empate 0, positiva para o lado democrata e negativa para o republicano. A pontuação
da corrida é a média dos prognosticadores disponíveis.

A pontuação traduz-se numa margem (``k`` pontos por nível) e combina-se com a previsão do
modelo pela precisão, como as sondagens. ``k`` e o erro dessa margem estimam-se só com anos
anteriores, por câmara: ``k`` por mínimos quadrados sem constante (simétrico entre
partidos) e o erro pela dispersão dentro de cada ano, porque a parte comum ao ano já está
no erro nacional da simulação.
"""

from collections.abc import Iterable, Mapping
from dataclasses import dataclass

import numpy as np

from pipeline.modelo.dados import LinhaModelo

PROGNOSTICADORES = ("cook", "sabato", "ie")
"""Os três com classificações finais publicadas desde 2010 para as duas câmaras."""

NIVEIS = {"seguro": 3.0, "provavel": 2.0, "inclinado": 1.0, "ligeiro": 0.5, "empate": 0.0}

MINIMO_CORRIDAS = 40
"""Corridas classificadas necessárias, nos anos anteriores, para estimar a tradução."""

Classificacoes = tuple[tuple[str, str, str], ...]
"""(prognosticador, categoria, partido) de uma corrida."""


@dataclass(frozen=True, slots=True)
class Traducao:
    """Margem implícita numa pontuação e o erro dessa margem dentro de um ano."""

    pontos_por_nivel: float
    sd: float
    corridas: int


def pontuacao(linha: LinhaModelo, classificacoes: Classificacoes) -> float | None:
    """Média das pontuações com sinal (positiva para o lado democrata) ou ``None``."""
    valores = []
    for prognosticador, categoria, partido in classificacoes:
        if prognosticador not in PROGNOSTICADORES or categoria not in NIVEIS:
            continue
        nivel = NIVEIS[categoria]
        if nivel == 0.0:
            valores.append(0.0)
            continue
        lado = _lado(linha, partido)
        if lado is None:
            continue
        valores.append(nivel if lado == "D" else -nivel)
    return float(np.mean(valores)) if valores else None


def _lado(linha: LinhaModelo, partido: str) -> str | None:
    if partido in {"D", "R"}:
        return partido
    if partido == "I":
        if linha.lado_d_independente:
            return "D"
        if linha.lado_r_independente:
            return "R"
    return None


def pontuacoes(
    linhas: Iterable[LinhaModelo], classificacoes: Mapping[tuple[int, str], Classificacoes]
) -> dict[str, float]:
    """Pontuação de cada corrida com classificações (por id)."""
    resultado = {}
    for linha in linhas:
        c = classificacoes.get((linha.ano, linha.id))
        if c is None or linha.certo is not None:
            continue
        p = pontuacao(linha, c)
        if p is not None:
            resultado[linha.id] = p
    return resultado


def estimar_traducao(
    linhas_por_ano: Mapping[int, list[LinhaModelo]],
    classificacoes: Mapping[tuple[int, str], Classificacoes],
    ano: int,
) -> Traducao | None:
    """Tradução estimada com os anos anteriores a ``ano`` (``None`` sem dados suficientes)."""
    xs: list[float] = []
    ys: list[float] = []
    anos: list[int] = []
    for a, linhas in linhas_por_ano.items():
        if a >= ano:
            continue
        for id_, p in pontuacoes(linhas, classificacoes).items():
            margem = next(x.margem for x in linhas if x.id == id_)
            if margem is None:
                continue
            xs.append(p)
            ys.append(margem)
            anos.append(a)
    x, y, ano_arr = np.array(xs), np.array(ys), np.array(anos)
    if len(x) < MINIMO_CORRIDAS or not np.any(x):
        return None
    k = float(np.sum(x * y) / np.sum(x * x))
    residuos = y - k * x
    for a in set(anos):
        residuos[ano_arr == a] -= residuos[ano_arr == a].mean()
    sd = float(np.sqrt(np.sum(residuos**2) / (len(residuos) - len(set(anos)) - 1)))
    return Traducao(pontos_por_nivel=k, sd=sd, corridas=len(x))
