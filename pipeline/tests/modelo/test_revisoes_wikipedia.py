"""Histórico de revisões da Wikipedia: última revisão de cada dia e recuo nos 429."""

from datetime import UTC, date, datetime

import httpx

from pipeline.modelo.fontes import wikipedia
from pipeline.modelo.fontes.revisoes import Revisao, ultima_por_dia


def _r(oldid: int, dia: int, hora: int) -> Revisao:
    return Revisao(oldid, datetime(2026, 1, dia, hora, tzinfo=UTC))


def test_ultima_revisao_de_cada_dia() -> None:
    revisoes = [_r(1, 1, 10), _r(2, 1, 23), _r(3, 3, 0), _r(4, 3, 12), _r(9, 1, 5)]
    por_dia = ultima_por_dia(revisoes, date(2026, 1, 1), date(2026, 1, 4))
    assert {d.day: r.oldid for d, r in por_dia.items()} == {1: 2, 2: 2, 3: 4, 4: 4}


def test_sem_revisao_anterior_o_dia_fica_de_fora() -> None:
    por_dia = ultima_por_dia([_r(5, 3, 8)], date(2026, 1, 1), date(2026, 1, 3))
    assert list(por_dia) == [date(2026, 1, 3)]


def test_recuo_exponencial_respeita_o_retry_after() -> None:
    sem = httpx.Response(429)
    assert [wikipedia.espera(sem, t) for t in range(3)] == [16.0, 32.0, 64.0]
    com = httpx.Response(429, headers={"Retry-After": "120"})
    assert wikipedia.espera(com, 0) == 120.0
    assert wikipedia.espera(com, 3) == 128.0
