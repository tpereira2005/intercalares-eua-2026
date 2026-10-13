import json
from datetime import UTC, date, datetime

import polars as pl
import pytest

from contratos.base import Fonte
from contratos.estados import CodigoEstado
from contratos.resultados import ResultadosEstado
from pipeline.transform.resultados import ensaio
from pipeline.transform.resultados.montar import (
    COLUNAS_UNIDADES,
    COLUNAS_VOTOS,
    DescricaoCorrida,
    Leitura,
    montar,
    nacional,
)

DATA = date(2026, 11, 3)
CORRIDAS = (
    DescricaoCorrida("NC-S", "US SENATE", "senado"),
    DescricaoCorrida("NC-01", "US HOUSE OF REPRESENTATIVES DISTRICT 01", "camara", 1),
)


def _fonte() -> Fonte:
    return Fonte.model_validate(
        {"nome": "Teste", "url": "https://exemplo.org/r.txt", "obtida_em": datetime.now(UTC)}
    )


def _leitura(fator: int = 1, *, trocar: bool = False) -> Leitura:
    dem, rep = ("rep", "dem") if trocar else ("dem", "rep")
    linhas = [
        # corrida, candidato, nome, partido, fonte, nível, código, votos
        ("NC-S", "a", "Ana", dem, "DEM", "condado", "37001", 100 * fator),
        ("NC-S", "b", "Bruno", rep, "REP", "condado", "37001", 80 * fator),
        ("NC-S", "c", "Carla", "outro", "LIB", "condado", "37001", 5 * fator),
        ("NC-S", "a", "Ana", dem, "DEM", "condado", "37003", 40 * fator),
        ("NC-S", "b", "Bruno", rep, "REP", "condado", "37003", 90 * fator),
        ("NC-S", "c", "Carla", "outro", "LIB", "condado", "37003", 2 * fator),
        ("NC-01", "d", "Diana", dem, "DEM", "condado", "37001", 70 * fator),
        ("NC-01", "e", "Eva", rep, "REP", "condado", "37001", 60 * fator),
    ]
    votos = pl.DataFrame(linhas, schema=COLUNAS_VOTOS, orient="row")
    unidades = pl.DataFrame(
        [
            ("NC-S", "condado", "37001", 3 * fator, 10),
            ("NC-S", "condado", "37003", 2 * fator, 8),
            ("NC-01", "condado", "37001", 3 * fator, 10),
        ],
        schema=COLUNAS_UNIDADES,
        orient="row",
    )
    return Leitura(CORRIDAS, votos, unidades, "seccao", datetime(2026, 11, 3, 23, tzinfo=UTC))


def _montar(leitura: Leitura) -> ResultadosEstado:
    return montar(
        estado=CodigoEstado.NC,
        data_eleicao=DATA,
        leitura=leitura,
        fontes=[_fonte()],
        nomes_geo={"37001": "Alamance", "37003": "Alexander"},
        gerado_em=datetime(2026, 11, 3, 23, 1, tzinfo=UTC),
    )


def test_totais_somam_os_condados_e_validam() -> None:
    r = _montar(_leitura())
    senado = next(c for c in r.corridas if c.id == "NC-S")
    assert [(c.id, c.votos) for c in senado.candidatos] == [("b", 170), ("a", 140), ("c", 7)]
    assert senado.total == 317
    assert (senado.unidades_reportadas, senado.unidades_totais) == (5, 18)
    assert {g.nome for g in senado.geografia} == {"Alamance", "Alexander"}
    assert ResultadosEstado.model_validate(json.loads(r.model_dump_json())) == r


def test_linha_estado_da_fonte_prevalece_sobre_a_soma() -> None:
    leitura = _leitura()
    extra = pl.DataFrame(
        [("NC-01", "d", "Diana", "dem", "DEM", "estado", None, 75)],
        schema=COLUNAS_VOTOS,
        orient="row",
    )
    leitura = Leitura(
        leitura.corridas,
        pl.concat([leitura.votos, extra]),
        leitura.unidades,
        "seccao",
    )
    camara = next(c for c in _montar(leitura).corridas if c.id == "NC-01")
    assert {c.id: c.votos for c in camara.candidatos} == {"d": 75, "e": 0}


def test_partidos_por_normalizar_sao_recusados() -> None:
    leitura = _leitura()
    leitura = Leitura(
        leitura.corridas,
        leitura.votos.with_columns(pl.lit("DEM").alias("partido")),
        leitura.unidades,
        "seccao",
    )
    with pytest.raises(ValueError, match="não normalizados"):
        _montar(leitura)


def test_troca_de_rotulos_partidarios_troca_o_resumo() -> None:
    normal = nacional([(_montar(_leitura()), "nc.json")], data_eleicao=DATA)
    trocado = nacional([(_montar(_leitura(trocar=True)), "nc.json")], data_eleicao=DATA)
    for a, b in zip(normal.corridas, trocado.corridas, strict=True):
        assert (a.votos_dem, a.votos_rep, a.votos_outros) == (
            b.votos_rep,
            b.votos_dem,
            b.votos_outros,
        )
        assert a.total == b.total
        assert a.apuramento == b.apuramento


def test_sequencia_deteta_descidas_e_aceita_subidas() -> None:
    um, dois = _montar(_leitura(1)), _montar(_leitura(2))
    assert ensaio.verificar_sequencia([um, dois]) == []
    problemas = ensaio.verificar_sequencia([dois, um])
    assert {p.corrida for p in problemas} == {"NC-S", "NC-01"}
    assert any("unidades" in p.descricao for p in problemas)
