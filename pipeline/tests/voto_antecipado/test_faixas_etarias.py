import polars as pl
import pytest

from pipeline.comum.faixas_etarias import (
    CANONICA,
    CANONICA_PARA_LARGA,
    FAIXA_DESCONHECIDA,
    LARGA,
    NCSBE,
)


@pytest.mark.parametrize(
    ("idade", "esperada"),
    [
        (17, "18-24"),
        (18, "18-24"),
        (24, "18-24"),
        (25, "25-29"),
        (64, "50-64"),
        (65, "65-74"),
        (75, "75+"),
        (110, "75+"),
        (16, FAIXA_DESCONHECIDA),
        (130, FAIXA_DESCONHECIDA),
        (None, FAIXA_DESCONHECIDA),
    ],
)
def test_classificacao_canonica(idade: int | None, esperada: str) -> None:
    assert CANONICA.classificar(idade) == esperada


@pytest.mark.parametrize("esquema", [CANONICA, LARGA, NCSBE])
def test_expressao_polars_igual_a_python(esquema: object) -> None:
    from pipeline.comum.faixas_etarias import EsquemaFaixas  # noqa: PLC0415

    assert isinstance(esquema, EsquemaFaixas)
    idades = [None, 0, 16, *range(17, 121)]
    tabela = pl.DataFrame({"idade": pl.Series(idades, dtype=pl.Int16)})
    obtido = tabela.select(esquema.expressao())["faixa"].to_list()
    assert obtido == [esquema.classificar(i) for i in idades]


def test_faixas_canonicas_cobrem_todas_as_idades_sem_sobreposicao() -> None:
    for idade in range(17, 116):
        assert sum(f.contem(idade) for f in CANONICA.faixas) == 1


def test_faixa_larga_e_soma_exata_das_canonicas() -> None:
    for idade in range(17, 116):
        assert CANONICA_PARA_LARGA[CANONICA.classificar(idade)] == LARGA.classificar(idade)
