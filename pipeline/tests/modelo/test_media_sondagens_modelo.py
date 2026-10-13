"""Média de sondagens: pesos simétricos, um voto por instituto e corte estrito."""

from datetime import date, timedelta

import pytest

from pipeline.modelo.fontes.sondagens import Sondagem
from pipeline.modelo.media import media

CORTE = date(2026, 11, 1)


def _s(instituto: str, dias: int, dem: float, rep: float, **kw: object) -> Sondagem:
    base: dict[str, object] = {
        "corrida": "NC-S",
        "ano": 2026,
        "instituto": instituto,
        "fim": CORTE - timedelta(days=dias),
        "amostra": 600,
        "populacao": "lv",
        "partidaria": False,
        "dem": dem,
        "rep": rep,
    }
    base.update(kw)
    return Sondagem(**base)  # type: ignore[arg-type]


def test_corte_e_janela() -> None:
    assert media([_s("A", 0, 50, 40)], CORTE) is None
    assert media([_s("A", 61, 50, 40)], CORTE) is None
    m = media([_s("A", 1, 50, 40)], CORTE)
    assert m is not None
    assert m.margem == pytest.approx(10.0)


def test_cada_instituto_conta_uma_vez() -> None:
    m = media([_s("A", 2, 50, 40), _s("A", 2 + 1, 50, 40), _s("B", 2, 40, 50)], CORTE)
    assert m is not None
    assert m.institutos == 2
    assert m.margem == pytest.approx(0.0, abs=0.5)


def test_pesos_simetricos() -> None:
    a = [_s("A", 3, 52, 44, partidaria=True), _s("B", 10, 47, 49, populacao="rv")]
    b = [_s("A", 3, 44, 52, partidaria=True), _s("B", 10, 49, 47, populacao="rv")]
    ma, mb = media(a, CORTE), media(b, CORTE)
    assert ma is not None
    assert mb is not None
    assert ma.margem == pytest.approx(-mb.margem)


def test_prefere_eleitores_provaveis_da_mesma_sondagem() -> None:
    m = media([_s("A", 3, 50, 40, populacao="rv"), _s("A", 3, 46, 44)], CORTE)
    assert m is not None
    assert m.margem == pytest.approx(2.0)
