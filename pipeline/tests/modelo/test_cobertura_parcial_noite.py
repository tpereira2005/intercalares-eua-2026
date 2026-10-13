"""Modelo C com estados acompanhados só por alguns condados (cobertura parcial)."""

from datetime import UTC, datetime

import pytest

from contratos.base import Fonte, Metadados
from contratos.estados import CodigoEstado
from contratos.resultados import CoberturaParcial, ResultadosParciais, UnidadeContagem
from pipeline.modelo.noite.corrida import Parametros, PriorCorrida, analisar
from pipeline.modelo.noite.entrada import Base, Contagem, de_parciais
from pipeline.modelo.noite.repeticao import finais, juntar

AGORA = datetime(2026, 11, 3, 21, tzinfo=UTC)
P = Parametros()
# Três condados de referência; o primeiro (48201, Harris) é o único acompanhado.
BASE = {"48201": Base(1_600_000, 4.0), "48029": Base(800_000, 1.0), "48113": Base(600_000, -10.0)}


def _harris(d: int, r: int) -> Contagem:
    return Contagem("TX-S", "48201", d, r, 20_000, seccoes_reportadas=1000, seccoes_totais=1000)


def test_corrida_estadual_so_com_um_condado_fica_parcial() -> None:
    prior = PriorCorrida("TX-S", "TX", -4.0, 5.0)
    a = analisar(prior, [_harris(640_000, 500_000)], BASE, 0.72, P, parcial=True)
    assert a.votos_esperados is not None
    assert a.fracao_contada is not None
    # Só o condado acompanhado conta como apurado: o resto do estado fica por prever.
    assert 0.3 < a.fracao_contada < 0.6
    assert a.gama > 1.0
    assert a.s_chapeu is not None


def test_corrida_estadual_parcial_e_simetrica() -> None:
    prior = PriorCorrida("TX-S", "TX", -4.0, 5.0)
    espelho = PriorCorrida("TX-S", "TX", 4.0, 5.0)
    base_e = {u: Base(b.votos, -b.margem) for u, b in BASE.items()}
    a = analisar(prior, [_harris(640_000, 500_000)], BASE, 0.72, P, parcial=True)
    b = analisar(espelho, [_harris(500_000, 640_000)], base_e, 0.72, P, parcial=True)
    assert b.alfa == pytest.approx(-a.alfa)
    assert b.beta == pytest.approx(a.beta)
    assert b.gama == pytest.approx(a.gama)
    assert b.s_chapeu == pytest.approx(-(a.s_chapeu or 0.0))


def test_distrito_num_estado_parcial_nao_se_da_por_completo() -> None:
    prior = PriorCorrida("TX-07", "TX", 10.0, 6.0)
    partes = [
        Contagem("TX-07", "48201", 150_000, 100_000, 5_000, seccoes_reportadas=200,
                 seccoes_totais=200),
        Contagem("TX-07", "48157", 30_000, 40_000, 1_000, seccoes_reportadas=50,
                 seccoes_totais=50),
    ]  # fmt: skip
    completo = analisar(prior, partes, {}, 0.72, P)
    assert completo.fracao_contada == pytest.approx(1 - P.residuo_seccoes)
    parcial = analisar(prior, partes, {}, 0.72, P, parcial=True)
    # Sem saber quanto falta do distrito, a margem final fica a da previsão; os votos
    # contados continuam a ser mostrados.
    assert parcial.votos_esperados is None
    assert parcial.alfa == prior.media
    assert parcial.votos_contados == 326_000
    assert parcial.margem_contada is not None


def test_converte_a_cobertura_parcial() -> None:
    fonte = Fonte(nome="Sintética", url="https://example.org/", obtida_em=AGORA)
    parciais = ResultadosParciais(
        metadados=Metadados(gerado_em=AGORA, fontes=(fonte,)),
        ano=2026,
        instante=AGORA,
        unidades=(
            UnidadeContagem(corrida="TX-S", unidade="48201", votos_d=10, votos_r=8, votos_outros=0),
        ),
        cobertura_parcial=(
            CoberturaParcial(estado=CodigoEstado.TX, condados=("48201",), nota="Só Harris"),
        ),
    )
    assert de_parciais(parciais).parciais == frozenset({"TX"})


def _parciais_estado(
    estado: str, corrida: str, unidade: str, *, parcial: bool
) -> ResultadosParciais:
    fonte = Fonte(nome="Sintética", url="https://example.org/", obtida_em=AGORA)
    cobertura = (
        (CoberturaParcial(estado=CodigoEstado(estado), condados=(unidade,), nota="parcial"),)
        if parcial
        else ()
    )
    return ResultadosParciais(
        metadados=Metadados(gerado_em=AGORA, fontes=(fonte,)),
        ano=2024,
        instante=AGORA,
        reconstruido=True,
        unidades=(
            UnidadeContagem(
                corrida=corrida, unidade=unidade, votos_d=60, votos_r=40, votos_outros=0
            ),
        ),
        cobertura_parcial=cobertura,
    )


def test_juntar_mantem_a_cobertura_parcial_e_finais_a_ignora() -> None:
    nc = _parciais_estado("NC", "NC-S", "37001", parcial=False)
    tx = _parciais_estado("TX", "TX-S", "48201", parcial=True)
    junto = juntar([nc, tx])
    assert de_parciais(junto).parciais == frozenset({"TX"})
    assert set(finais(junto)) == {"NC-S"}
