"""Modelo C com a ordem de contagem (``noite/modos.py``) em corridas sintéticas.

Cada corrida tem 40 condados com referência; o voto antecipado chega inteiro e primeiro,
com uma diferença face ao resto de sinal aleatório. Verifica-se quando o caminho por modos
se usa, que trocar os partidos troca a análise, que com tudo contado a margem é a contada,
que os intervalos de 80% têm a cobertura certa e que, perante uma miragem do voto
antecipado, a margem projetada fica mais perto do resultado do que sem os modos.
"""

import math
from dataclasses import replace

import numpy as np
import pytest

from pipeline.modelo.noite import modos
from pipeline.modelo.noite.corrida import AnaliseCorrida, Parametros, PriorCorrida, analisar
from pipeline.modelo.noite.entrada import Base, Contagem, VotosModo

P = Parametros()
PARTICIPACAO = P.participacao_intercalar
CONDADOS = 40


def _votos(n: float, margem: float) -> tuple[int, int]:
    """Votos D e R (sem outros) de ``n`` votos com a margem dada."""
    d = round(n * (1 + margem / 100) / 2)
    return d, round(n) - d


def _contagem(fips: str, nc: float, mc: float, nr: float, mr: float) -> Contagem:
    cd, cr = _votos(nc, mc)
    rd, rr = _votos(nr, mr)
    modos_ = (VotosModo("antecipado_presencial", cd, cr, 0), VotosModo("dia_eleicao", rd, rr, 0))
    return Contagem("NC-S", fips, cd + rd, cr + rr, 0, modos=modos_)


def _noite(
    rng: np.random.Generator, chegados: float, contado_resto: float
) -> tuple[PriorCorrida, list[Contagem], dict[str, Base], float]:
    """Corrida sintética coerente com o modelo; devolve também a margem final verdadeira."""
    s = rng.normal(0, 8)
    g = rng.normal(0, P.ordem.sd_diferenca)
    participacao = PARTICIPACAO * math.exp(rng.normal(0, 0.1))
    prior = PriorCorrida("NC-S", "NC", 0.0, 8.0)
    base: dict[str, Base] = {}
    contagens: list[Contagem] = []
    soma = soma_votos = 0.0
    for i in range(CONDADOS):
        fips = f"37{i:03d}"
        t = float(rng.uniform(5_000, 60_000))
        b = float(rng.normal(0, 15))
        base[fips] = Base(t, b)
        e = t * participacao * math.exp(rng.normal(0, 0.03))
        f = b + s + rng.normal(0, P.sd_unidade)
        pi = float(rng.uniform(0.4, 0.7))
        gu = g + rng.normal(0, P.ordem.sd_diferenca_unidade)
        soma += e * f
        soma_votos += e
        if i < chegados * CONDADOS:
            nr = (1 - pi) * e * contado_resto
            contagens.append(_contagem(fips, pi * e, f + (1 - pi) * gu, nr, f - pi * gu))
    return prior, contagens, base, soma / soma_votos


def _media_sd(a: AnaliseCorrida) -> tuple[float, float]:
    """Média e desvio da margem final juntando o prior de ``s`` e as contagens."""
    precisao = 1 / a.var_s
    centro = a.s0 / a.var_s
    if a.s_chapeu is not None and a.var_chapeu is not None:
        precisao += 1 / a.var_chapeu
        centro += a.s_chapeu / a.var_chapeu
    s, var = centro / precisao, 1 / precisao
    return a.alfa + a.beta * s, math.sqrt(a.gama**2 + a.beta**2 * var)


def test_so_condados_com_voto_antecipado_usam_os_modos() -> None:
    n = np.array([100.0, 0.0])
    nc = np.array([60.0, math.nan])
    nr = np.array([40.0, math.nan])
    condados = np.array([True, True])
    assert modos.elegivel("NC", n, nc, nr, condados)
    assert not modos.elegivel("PA", n, nc, nr, condados)
    assert not modos.elegivel("NC", n, nc, nr, np.array([False, True]))
    assert not modos.elegivel("NC", n, np.array([math.nan, math.nan]), nr, condados)
    assert not modos.elegivel("NC", n, np.array([60.0, math.nan]), np.array([30.0, 0]), condados)
    assert not modos.elegivel("NC", np.zeros(2), nc, nr, condados)


def test_trocar_partidos_troca_a_analise() -> None:
    prior, contagens, base, _ = _noite(np.random.default_rng(1), 0.5, 0.4)
    a = analisar(prior, contagens, base, PARTICIPACAO, P)
    espelho = analisar(
        replace(prior, media=-prior.media),
        [
            replace(
                c,
                votos_d=c.votos_r,
                votos_r=c.votos_d,
                modos=tuple(replace(m, votos_d=m.votos_r, votos_r=m.votos_d) for m in c.modos),
            )
            for c in contagens
        ],
        {k: Base(b.votos, -b.margem) for k, b in base.items()},
        PARTICIPACAO,
        P,
    )
    assert a.s_chapeu is not None
    assert espelho.s_chapeu is not None
    assert espelho.alfa == pytest.approx(-a.alfa, abs=1e-9)
    assert espelho.beta == pytest.approx(a.beta, abs=1e-9)
    assert espelho.gama == pytest.approx(a.gama, abs=1e-9)
    assert espelho.s_chapeu == pytest.approx(-a.s_chapeu, abs=1e-9)


def test_tudo_contado_da_a_margem_contada() -> None:
    prior, contagens, base, _ = _noite(np.random.default_rng(2), 1.0, 1.0)
    completas = [replace(c, fracao_contada=1.0) for c in contagens]
    a = analisar(prior, completas, base, PARTICIPACAO, P)
    assert a.margem_contada is not None
    assert a.alfa == pytest.approx(a.margem_contada, abs=1e-9)
    assert a.beta == pytest.approx(0.0, abs=1e-12)
    assert a.gama == pytest.approx(0.0, abs=1e-9)


def test_intervalos_de_80_cobrem_o_resultado() -> None:
    rng = np.random.default_rng(3)
    dentro = 0
    noites = 200
    for _ in range(noites):
        prior, contagens, base, real = _noite(
            rng, float(rng.uniform(0.2, 0.9)), float(rng.uniform(0.0, 0.8))
        )
        media, sd = _media_sd(analisar(prior, contagens, base, PARTICIPACAO, P))
        dentro += abs(real - media) <= 1.2816 * sd
    assert 0.72 <= dentro / noites <= 0.95


def test_miragem_do_voto_antecipado(monkeypatch: pytest.MonkeyPatch) -> None:
    """Com metade dos condados só com o antecipado, os modos corrigem a miragem."""
    erros: dict[bool, list[float]] = {True: [], False: []}
    for semente in range(30):
        prior, contagens, base, real = _noite(np.random.default_rng(100 + semente), 0.5, 0.1)
        for com_modos in (True, False):
            monkeypatch.setattr(
                modos, "ORDEM_CONTAGEM", frozenset({"NC"}) if com_modos else frozenset()
            )
            media, _ = _media_sd(analisar(prior, contagens, base, PARTICIPACAO, P))
            erros[com_modos].append(abs(media - real))
    assert np.mean(erros[True]) < 0.7 * np.mean(erros[False])
