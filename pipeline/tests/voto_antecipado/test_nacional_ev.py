from collections.abc import Callable
from datetime import UTC, date, datetime

import polars as pl
import pytest

from contratos.base import Fonte
from contratos.estados import CodigoEstado
from pipeline.comum.calendario import eleicao_geral
from pipeline.transform.early_vote import agregado as ag
from pipeline.transform.early_vote import nacional


def _fonte() -> Fonte:
    return Fonte.model_validate(
        {
            "nome": "T",
            "url": "https://exemplo.org/x",
            "obtida_em": datetime(2026, 10, 13, tzinfo=UTC),
        }
    )


def test_linha_agregada_cita_os_numeros_do_estado(fb: Callable[..., pl.DataFrame]) -> None:
    relatorio = ag.montar(
        estado=CodigoEstado.PA,
        atual=ag.cubos(fb(11), eleicao_geral("PA", 2026)),
        bases=[ag.cubos(fb(12, ano=2022), eleicao_geral("PA", 2022))],
        dados_ate=date(2026, 10, 20),
        dimensoes=("faixa", "partido", "condado"),
        modalidades=("correio",),
        fontes=[_fonte()],
        nomes_condados={},
    )
    linha = nacional.linha_agregado(relatorio, "pa.json")
    assert linha.votos == relatorio.ciclos[0].votos
    assert linha.ano_base == 2022
    assert linha.votos_base == relatorio.ciclos[1].votos_mesmo_dia
    assert linha.votos_base
    assert linha.ritmo == pytest.approx(linha.votos / linha.votos_base - 1, abs=1e-6)
    dem = next(c for c in relatorio.comparacao if c.dimensao == "partido" and c.categoria == "dem")
    assert linha.quota_dem == pytest.approx(dem.quota)
    assert linha.quota_65_mais is not None
    assert 0 < linha.quota_65_mais < 1

    resumo = nacional.montar([linha], [_fonte()], ano=2026)
    assert resumo.votos == linha.votos
    assert resumo.estados[0].estado == CodigoEstado.PA


def test_estados_sem_dados_saem_quando_ha_ficheiro(fb: Callable[..., pl.DataFrame]) -> None:
    del fb
    sem_linhas = nacional.montar([], [_fonte()], ano=2026)
    assert {e.estado.value for e in sem_linhas.estados_sem_dados} >= {"GA", "TX"}
    assert all(e.motivo == "bloqueado" and e.nota for e in sem_linhas.estados_sem_dados)


def test_sinal_condados_separa_por_vencedor_e_pondera_a_margem() -> None:
    margens = {"37001": -20.0, "37003": 10.0, "37005": 0.0}
    sinal = nacional.sinal_condados(
        {"37001": 300, "37003": 100, "37005": 100, "99999": 50}, margens, 2026
    )
    assert sinal is not None
    assert (sinal.votos_trump, sinal.votos_harris) == (300, 100)
    assert sinal.margem_ponderada == pytest.approx((300 * -20 + 100 * 10) / 500)
    assert nacional.sinal_condados({"99999": 50}, margens, 2026) is None


def test_sinal_condados_e_simetrico() -> None:
    votos = {"37001": 300, "37003": 100}
    margens = {"37001": -20.0, "37003": 10.0}
    a = nacional.sinal_condados(votos, margens, 2026)
    b = nacional.sinal_condados(votos, {k: -v for k, v in margens.items()}, 2026)
    assert a is not None
    assert b is not None
    assert (a.votos_trump, a.votos_harris) == (b.votos_harris, b.votos_trump)
    assert a.margem_ponderada == pytest.approx(-(b.margem_ponderada or 0))
