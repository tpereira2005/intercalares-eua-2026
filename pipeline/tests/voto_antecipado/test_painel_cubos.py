from datetime import date

import polars as pl

from pipeline.comum.calendario import EleicaoGeral
from pipeline.connectors.early_vote.nc.processar import ultimo_dia_completo
from pipeline.transform.early_vote.cubos import cubo_demografico, cubo_final, cubo_geografico
from pipeline.transform.early_vote.painel import construir_painel

ATRIBUTOS = {
    "fips_condado": "37183",
    "distrito": 2,
    "partido": "dem",
    "raca": "branca",
    "etnia": "nao_hispanica",
    "genero": "feminino",
}


def _registados() -> pl.DataFrame:
    linhas = [
        ("V1", 30, date(2010, 1, 1)),  # votou antecipado em 2022, vota agora
        ("V2", 70, date(2000, 1, 1)),  # votou no dia em 2022, antecipa agora
        ("V3", 45, date(2015, 1, 1)),  # absteve-se em 2022, vota agora
        ("V4", 19, date(2025, 3, 1)),  # recenseou-se depois de 2022
        ("V5", 55, None),  # sem data de registo nem histórico
    ]
    return pl.DataFrame(
        [{"ncid": n, "idade": i, "data_registo": d, **ATRIBUTOS} for n, i, d in linhas]
    ).cast({"idade": pl.Int16, "distrito": pl.Int8})


def _votantes() -> pl.DataFrame:
    linhas = [
        ("V1", "correio", date(2026, 10, 1), False, 30),
        ("V2", "presencial", date(2026, 10, 16), False, 70),
        ("V3", "presencial", date(2026, 10, 20), False, 45),
        ("S1", "presencial", date(2026, 10, 18), True, 22),  # registo no próprio dia
    ]
    return pl.DataFrame(
        [
            {
                "ncid": n,
                "modalidade": m,
                "data_devolucao": d,
                "registo_no_dia": s,
                "idade": i,
                **ATRIBUTOS,
            }
            for n, m, d, s, i in linhas
        ]
    ).cast({"idade": pl.Int16, "distrito": pl.Int8})


def _historico() -> pl.DataFrame:
    return pl.DataFrame(
        {
            "ncid": ["V1", "V2", "V1"],
            "ano": pl.Series([2022, 2022, 2018], dtype=pl.Int16),
            "metodo": ["antecipado", "dia_eleicao", "dia_eleicao"],
        }
    )


def test_painel_classifica_historico_e_inclui_registos_no_dia(
    eleicao_teste: EleicaoGeral,
) -> None:
    painel = construir_painel(
        _registados(),
        _votantes(),
        historico=_historico(),
        eleicao=eleicao_teste,
        data_referencia=date(2022, 11, 8),
        distrito_atual=pl.DataFrame(
            {"ncid": ["V1"], "distrito_atual": pl.Series([9], dtype=pl.Int8)}
        ),
    )
    linhas = {r["ncid"]: r for r in painel.iter_rows(named=True)}
    assert set(linhas) == {"V1", "V2", "V3", "V4", "V5", "S1"}
    assert linhas["V1"]["grupo"] == "antecipado_na_referencia"
    assert linhas["V2"]["grupo"] == "dia_eleicao_na_referencia"
    assert linhas["V3"]["grupo"] == "absteve_se_na_referencia"
    assert linhas["V4"]["grupo"] == "recenseado_apos_referencia"
    assert linhas["V5"]["grupo"] == "absteve_se_na_referencia"
    assert linhas["S1"]["grupo"] == "recenseado_apos_referencia"
    assert linhas["V1"]["dias_antes"] == 33
    assert linhas["V4"]["modalidade"] == "nao_votou"
    assert linhas["V4"]["dias_antes"] is None
    assert linhas["V1"]["faixa"] == "30-39"
    assert linhas["S1"]["faixa"] == "18-24"
    assert linhas["V1"]["distrito_atual"] == 9
    assert linhas["V2"]["distrito_atual"] == 2


def test_sem_historico_quando_nao_ha_referencia(eleicao_teste: EleicaoGeral) -> None:
    painel = construir_painel(
        _registados(), _votantes(), historico=None, eleicao=eleicao_teste, data_referencia=None
    )
    assert painel["grupo"].unique().to_list() == ["sem_historico"]


def test_cubos_preservam_totais(eleicao_teste: EleicaoGeral) -> None:
    painel = construir_painel(
        _registados(),
        _votantes(),
        historico=_historico(),
        eleicao=eleicao_teste,
        data_referencia=date(2022, 11, 8),
    )
    demo = cubo_demografico(painel)
    geo = cubo_geografico(painel)
    assert demo["n"].sum() == geo["n"].sum() == painel.height
    assert "ncid" not in demo.columns
    assert "ncid" not in geo.columns
    votos = demo.filter(pl.col("modalidade") != "nao_votou")["n"].sum()
    assert votos == 4


def test_ultimo_dia_completo_ignora_o_dia_da_geracao() -> None:
    votos = pl.DataFrame(
        {"data_devolucao": [date(2026, 10, 11), date(2026, 10, 12), date(2026, 10, 13)]}
    )
    eleicao = date(2026, 11, 3)
    assert ultimo_dia_completo(votos, eleicao, date(2026, 10, 13)) == date(2026, 10, 12)
    assert ultimo_dia_completo(votos, eleicao, None) == date(2026, 10, 13)
    tardios = pl.DataFrame({"data_devolucao": [date(2022, 11, 7), date(2022, 11, 12)]})
    assert ultimo_dia_completo(tardios, date(2022, 11, 8), date(2022, 11, 19)) == date(2022, 11, 7)


def test_cubo_final_conta_quem_votou_antecipado_e_no_dia() -> None:
    cubo = cubo_final(
        _registados(),
        _historico(),
        2022,
        pl.DataFrame({"ncid": ["V1"], "distrito_atual": pl.Series([9], dtype=pl.Int8)}),
    )
    assert cubo.columns == ["fips_condado", "distrito_atual", "faixa", "partido", "metodo", "n"]
    linhas = {
        (r["faixa"], r["metodo"], r["distrito_atual"]): r["n"] for r in cubo.iter_rows(named=True)
    }
    assert linhas == {("30-39", "antecipado", 9): 1, ("65-74", "dia_eleicao", 2): 1}
    assert cubo_final(_registados(), _historico(), 2018)["n"].sum() == 1
