"""Estimação dos parâmetros do modelo com os ciclos anteriores ao ano previsto.

Só se usam anos anteriores ao ano a prever: o backtest de 2018 estima com 2012 a 2016, o
de 2022 com 2012 a 2020 e assim por diante. Assim os backtests reproduzem o que o modelo
saberia na véspera de cada eleição.
"""

import math
from collections import defaultdict
from dataclasses import dataclass

import numpy as np
import numpy.typing as npt

from pipeline.modelo.dados import LinhaModelo

LIMITE_COMPETITIVO = 30.0
"""Os desvios-padrão estimam-se com corridas previstas a menos de 30 pontos: são as que
decidem lugares, e as corridas desequilibradas têm erros muito maiores e irrelevantes."""


@dataclass(frozen=True, slots=True)
class Fundamentos:
    """Margem esperada = N + intercepto + inclinação x PVI + incumbência (+ resíduo anterior)."""

    intercepto: float
    inclinacao: float
    incumbencia: float
    persistencia: float
    """Fração do resíduo do ciclo anterior que se mantém (mesmo incumbente, mesmo mapa)."""

    sd_ano: float
    """Desvio-padrão do intercepto entre anos (incerteza na tradução do ambiente nacional)."""

    sd_regiao: float
    """Desvio-padrão do choque comum a uma região num ano."""

    sd_corrida: float
    """Desvio-padrão do erro próprio de cada corrida (competitivas)."""

    observacoes: int

    def esperado(self, linha: LinhaModelo, nacional: float) -> float:
        valor = nacional + self.intercepto + self.inclinacao * linha.pvi
        valor += self.incumbencia * linha.incumbente
        if linha.residuo_anterior is not None:
            valor += self.persistencia * linha.residuo_anterior
        return valor


def _matriz(linhas: list[LinhaModelo], anos: list[int]) -> npt.NDArray[np.float64]:
    x = np.zeros((len(linhas), 2 + len(anos)))
    for i, linha in enumerate(linhas):
        x[i, 0] = linha.pvi
        x[i, 1] = linha.incumbente
        x[i, 2 + anos.index(linha.ano)] = 1.0
    return x


def estimar_fundamentos(
    linhas: list[LinhaModelo], nacional: dict[int, float]
) -> tuple[Fundamentos, dict[tuple[int, str], float]]:
    """Mínimos quadrados com efeitos fixos de ano; devolve os parâmetros e os resíduos."""
    usadas = [
        ln
        for ln in linhas
        if ln.margem is not None
        and ln.certo is None
        and not ln.lado_d_independente
        and not ln.lado_r_independente
        and ln.ano in nacional
    ]
    if len(usadas) < 30:
        raise ValueError("Corridas insuficientes para estimar os fundamentos")
    anos = sorted({ln.ano for ln in usadas})
    y = np.array([(ln.margem or 0.0) - nacional[ln.ano] for ln in usadas])
    x = _matriz(usadas, anos)
    coef, *_ = np.linalg.lstsq(x, y, rcond=None)
    inclinacao, incumbencia = float(coef[0]), float(coef[1])
    efeitos = coef[2:]
    previsto = x @ coef
    residuos = y - previsto

    # Persistência: regressão do resíduo atual no resíduo anterior (mesmo incumbente).
    por_id = {(ln.ano, ln.id): float(r) for ln, r in zip(usadas, residuos, strict=True)}
    pares = [
        (ln.residuo_anterior, por_id[(ln.ano, ln.id)])
        for ln in usadas
        if ln.residuo_anterior is not None
    ]
    persistencia = 0.0
    if len(pares) >= 20:
        a = np.array([p[0] for p in pares])
        b = np.array([p[1] for p in pares])
        persistencia = float(np.clip((a @ b) / (a @ a), 0.0, 1.0))
        for i, ln in enumerate(usadas):
            if ln.residuo_anterior is not None:
                residuos[i] -= persistencia * ln.residuo_anterior

    competitivas = np.abs(previsto) < LIMITE_COMPETITIVO
    regioes: dict[tuple[int, str], list[float]] = defaultdict(list)
    for ln, r, c in zip(usadas, residuos, competitivas, strict=True):
        if c:
            regioes[(ln.ano, ln.regiao)].append(float(r))
    medias_regiao = {k: float(np.mean(v)) for k, v in regioes.items() if len(v) >= 3}
    tamanhos = {k: len(v) for k, v in regioes.items() if len(v) >= 3}
    idio = [
        float(r) - medias_regiao.get((ln.ano, ln.regiao), 0.0)
        for ln, r, c in zip(usadas, residuos, competitivas, strict=True)
        if c
    ]
    sd_corrida = float(np.std(idio, ddof=1 + len(anos)))
    # Variância entre regiões descontada do ruído de amostragem de cada média.
    excesso = [m**2 - sd_corrida**2 / tamanhos[k] for k, m in medias_regiao.items()]
    sd_regiao = math.sqrt(max(float(np.mean(excesso)), 0.0)) if excesso else 0.0
    sd_ano = float(np.std(efeitos, ddof=1)) if len(efeitos) > 1 else 0.0

    residuos_finais = {(ln.ano, ln.id): float(r) for ln, r in zip(usadas, residuos, strict=True)}
    return (
        Fundamentos(
            intercepto=float(np.mean(efeitos)),
            inclinacao=inclinacao,
            incumbencia=incumbencia,
            persistencia=persistencia,
            sd_ano=sd_ano,
            sd_regiao=sd_regiao,
            sd_corrida=sd_corrida,
            observacoes=len(usadas),
        ),
        residuos_finais,
    )


@dataclass(frozen=True, slots=True)
class ErroSondagens:
    """Erro de uma média de sondagens de uma corrida: comum ao ano mais próprio da corrida.

    A variância própria da corrida é ``base² + por_instituto² / institutos``.
    """

    base: float
    por_instituto: float
    sd_ano: float
    """Desvio-padrão do erro comum a todas as corridas num ano."""

    ligacao_nacional: float
    """Quanto do erro comum acompanha o erro do voto genérico (regressão entre anos)."""

    observacoes: int

    def variancia(self, institutos: int) -> float:
        return self.base**2 + self.por_instituto**2 / max(institutos, 1)


def estimar_erro_sondagens(
    erros: list[tuple[int, int, float]], erros_nacionais: dict[int, float]
) -> ErroSondagens:
    """``erros``: (ano, institutos, média - resultado) de cada corrida com sondagens."""
    if len(erros) < 30:
        raise ValueError("Corridas com sondagens insuficientes para estimar o erro")
    por_ano: dict[int, list[float]] = defaultdict(list)
    for ano, _, e in erros:
        por_ano[ano].append(e)
    medias = {a: float(np.mean(v)) for a, v in por_ano.items()}
    centrados = [(k, e - medias[a]) for a, k, e in erros]
    # e² ≈ base² + por_instituto²/k  (mínimos quadrados com coeficientes não negativos)
    x = np.array([[1.0, 1.0 / max(k, 1)] for k, _ in centrados])
    y = np.array([e**2 for _, e in centrados])
    coef, *_ = np.linalg.lstsq(x, y, rcond=None)
    base2, inst2 = float(max(coef[0], 1.0)), float(max(coef[1], 0.0))
    anos = sorted(set(medias) & set(erros_nacionais))
    ligacao = 1.0
    if len(anos) >= 4:
        a = np.array([erros_nacionais[x] for x in anos])
        b = np.array([medias[x] for x in anos])
        ligacao = float(np.clip((a @ b) / (a @ a), 0.0, 1.5))
    return ErroSondagens(
        base=math.sqrt(base2),
        por_instituto=math.sqrt(inst2),
        sd_ano=float(np.std(list(medias.values()), ddof=1)),
        ligacao_nacional=ligacao,
        observacoes=len(erros),
    )


def erro_quadratico_medio(erros: list[float]) -> float:
    """Raiz do erro quadrático médio: mede a dimensão do erro sem lhe impor um sinal."""
    return math.sqrt(sum(e * e for e in erros) / len(erros))
