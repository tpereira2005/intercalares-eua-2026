import json
from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta

import polars as pl
import pytest
from polars.testing import assert_frame_equal

from contratos.base import Fonte
from contratos.estados import CodigoEstado
from contratos.voto_antecipado_agregado import VotoAntecipadoAgregado
from pipeline.comum.calendario import eleicao_geral
from pipeline.transform.early_vote import agregado as ag
from pipeline.transform.early_vote.relatorio import LIMIAR_POPULACAO

FabricaBoletins = Callable[..., pl.DataFrame]

IDENTIFICADORES = {"ncid", "eleitor", "_eleitor", "idade", "data_pedido", "data_devolucao"}


def _fonte() -> Fonte:
    return Fonte.model_validate(
        {
            "nome": "Teste",
            "url": "https://exemplo.org/f.csv",
            "obtida_em": datetime(2026, 10, 13, tzinfo=UTC),
        }
    )


def _montar(atual: pl.DataFrame, base: pl.DataFrame, dados_ate: date) -> VotoAntecipadoAgregado:
    return ag.montar(
        estado=CodigoEstado.PA,
        atual=ag.cubos(atual, eleicao_geral("PA", 2026)),
        bases=[ag.cubos(base, eleicao_geral("PA", 2022))],
        dados_ate=dados_ate,
        dimensoes=("faixa", "partido", "modalidade", "condado", "distrito"),
        modalidades=("correio", "presencial"),
        fontes=[_fonte()],
        nomes_condados={"42001": "Adams"},
        gerado_em=datetime(2026, 10, 13, tzinfo=UTC),
    )


def test_cubos_contam_todos_os_boletins(fb: FabricaBoletins) -> None:
    boletins = fb(1)
    cubos = ag.cubos(boletins, eleicao_geral("PA", 2026))
    assert cubos.pedidos["n"].sum() == boletins.height
    assert ag.total_votos(cubos.votos, -1000) == boletins["data_devolucao"].count()
    assert not IDENTIFICADORES & set(cubos.votos.columns)
    assert not IDENTIFICADORES & set(cubos.pedidos.columns)


def test_cubos_recusam_colunas_em_falta(fb: FabricaBoletins) -> None:
    with pytest.raises(ValueError, match="Faltam colunas"):
        ag.cubos(fb(1).drop("distrito"), eleicao_geral("PA", 2026))


def test_votos_ate_d_coincidem_com_a_contagem_direta(fb: FabricaBoletins) -> None:
    boletins = fb(2)
    eleicao = eleicao_geral("PA", 2026)
    cubos = ag.cubos(boletins, eleicao)
    for d in (40, 20, 5, 0):
        dia = eleicao.data - timedelta(days=d)
        direto = boletins.filter(pl.col("data_devolucao") <= dia).height
        assert ag.total_votos(cubos.votos, d) == direto


def test_comparacao_quotas_somam_um_e_ritmo_e_coerente(fb: FabricaBoletins) -> None:
    eleicao = eleicao_geral("PA", 2026)
    atual = ag.cubos(fb(3), eleicao).votos
    base = ag.cubos(fb(4, ano=2022), eleicao_geral("PA", 2022)).votos
    tabela = ag.comparacao(atual, base, 10, ["faixa", "partido"])
    for dim in ("faixa", "partido"):
        partes = tabela.filter((pl.col("dimensao") == dim) & (pl.col("categoria") != "total"))
        assert partes["quota"].sum() == pytest.approx(1.0)
        assert partes["quota_base"].sum() == pytest.approx(1.0)
    total = tabela.filter((pl.col("dimensao") == "partido") & (pl.col("categoria") == "total")).row(
        0, named=True
    )
    assert total["ritmo"] == pytest.approx(total["votos"] / total["votos_base"] - 1)


def test_pedidos_dividem_se_em_devolvidos_e_pendentes(fb: FabricaBoletins) -> None:
    boletins = fb(5)
    eleicao = eleicao_geral("PA", 2026)
    cubos = ag.cubos(boletins, eleicao)
    d = 15
    dia = eleicao.data - timedelta(days=d)
    tabela = ag.pedidos(cubos.pedidos, d)
    total = tabela.filter((pl.col("faixa") == "total") & (pl.col("partido") == "total")).row(
        0, named=True
    )
    pedidos = boletins.filter(pl.col("data_pedido") <= dia)
    assert total["pedidos"] == pedidos.height
    assert total["devolvidos"] == pedidos.filter(pl.col("data_devolucao") <= dia).height
    assert total["pendentes"] == total["pedidos"] - total["devolvidos"]


def test_troca_de_rotulos_partidarios_troca_os_resultados(fb: FabricaBoletins) -> None:
    eleicao = eleicao_geral("PA", 2026)
    boletins = fb(6)
    trocar = pl.col("partido").replace({"dem": "rep", "rep": "dem"})
    normal = ag.cubos(boletins, eleicao)
    trocado = ag.cubos(boletins.with_columns(trocar), eleicao)
    base = ag.cubos(fb(7, ano=2022), eleicao_geral("PA", 2022))
    base_trocada = ag.CubosAgregados(
        base.eleicao, base.votos.with_columns(trocar), base.pedidos.with_columns(trocar)
    )
    a = ag.comparacao(normal.votos, base.votos, 10, ["partido"])
    b = ag.comparacao(trocado.votos, base_trocada.votos, 10, ["partido"])
    b = b.with_columns(pl.col("categoria").replace({"dem": "rep", "rep": "dem"})).sort(
        "dimensao", "categoria"
    )
    assert_frame_equal(a, b, check_exact=False)
    ga = ag.geografia(normal.votos, 10, "fips_condado")
    gb = ag.geografia(trocado.votos, 10, "fips_condado").with_columns(
        pl.col("partido").replace({"dem": "rep", "rep": "dem"})
    )
    assert_frame_equal(ga, gb.sort("fips_condado", "partido"))


def test_relatorio_valida_e_nao_publica_identificadores_nem_pedidos_pequenos(
    fb: FabricaBoletins,
) -> None:
    relatorio = _montar(fb(8, n=400), fb(9, n=400, ano=2022), date(2026, 10, 20))
    assert relatorio.dias_antes == 14
    assert [c.ano for c in relatorio.ciclos] == [2026, 2022]
    assert relatorio.ciclos[1].votos_mesmo_dia is not None
    dados = json.loads(relatorio.model_dump_json())
    assert VotoAntecipadoAgregado.model_validate(dados) == relatorio
    assert not IDENTIFICADORES & set(json.dumps(dados).replace('"', " ").split())
    assert all(p["pedidos"] == 0 or p["pedidos"] >= LIMIAR_POPULACAO for p in dados["pedidos"])
    total_serie = next(
        p
        for p in relatorio.serie
        if p.ano == 2026 and p.dias_antes == 14 and p.faixa == "total"
        and p.partido == "total" and p.modalidade == "total"
    )  # fmt: skip
    assert total_serie.votos == relatorio.ciclos[0].votos
    nomes = {(g.nivel, g.codigo): g.nome for g in relatorio.geografia}
    assert nomes[("condado", "42001")] == "Adams"
    assert nomes[("distrito", "1")] == "PA-01"


def test_relatorio_recusa_dados_posteriores_a_eleicao(fb: FabricaBoletins) -> None:
    with pytest.raises(ValueError, match="posteriores"):
        _montar(fb(1), fb(2, ano=2022), date(2026, 11, 4))


def test_geografia_por_faixa_e_do_mesmo_dia_do_ciclo(fb: FabricaBoletins) -> None:
    atual, base = fb(8, n=400), fb(9, n=400, ano=2022)
    relatorio = _montar(atual, base, date(2026, 10, 20))
    d = relatorio.dias_antes
    for nivel in ("condado", "distrito"):
        linhas = [g for g in relatorio.geografia if g.nivel == nivel]
        por_faixa = [g for g in linhas if g.faixa != "total"]
        assert por_faixa
        assert all(g.partido == "total" for g in por_faixa)
        # Por unidade, as faixas somam o total, e o total por faixa e por partido coincide.
        for ano in (2026, 2022):
            totais_faixa = {
                g.codigo: g.votos
                for g in linhas
                if g.ano == ano and g.faixa == "total" and g.partido == "total"
            }
            for codigo, total in totais_faixa.items():
                soma = sum(
                    g.votos
                    for g in por_faixa
                    if g.ano == ano and g.codigo == codigo and g.faixa != "total"
                )
                assert soma == total
    chaves = [(g.ano, g.nivel, g.codigo, g.faixa, g.partido) for g in relatorio.geografia]
    assert len(chaves) == len(set(chaves))
    # 2022 conta até ao mesmo dia do ciclo, não o total final.
    cubo_base = ag.cubos(base, eleicao_geral("PA", 2022)).votos
    total_2022 = sum(
        g.votos
        for g in relatorio.geografia
        if g.ano == 2022 and g.nivel == "condado" and g.faixa == "total" and g.partido == "total"
    )
    assert total_2022 == ag.total_votos(cubo_base.drop_nulls("fips_condado"), d)
