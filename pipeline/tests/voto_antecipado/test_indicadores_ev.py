from collections.abc import Callable

import numpy as np
import polars as pl
import pytest
from polars.testing import assert_frame_equal

from pipeline.transform.early_vote import indicadores as ind
from pipeline.transform.early_vote.cubos import cubo_demografico, cubo_geografico

FabricaPainel = Callable[..., pl.DataFrame]


@pytest.fixture
def base(fabrica_painel: FabricaPainel) -> pl.DataFrame:
    return cubo_demografico(fabrica_painel(1))


@pytest.fixture
def atual(fabrica_painel: FabricaPainel) -> pl.DataFrame:
    return cubo_demografico(fabrica_painel(2, n=4500, taxa_extra=0.05))


def test_serie_e_cumulativa_e_coincide_com_contagens(base: pl.DataFrame) -> None:
    dias = list(range(40, -1, -1))
    serie = ind.serie(base, ["faixa"], dias)
    for _, grupo in serie.group_by("faixa"):
        votos = grupo.sort("dias_antes", descending=True)["votos"].to_list()
        assert votos == sorted(votos)
    for d in (40, 20, 5, 0):
        esperado = ind.contagens(base, d, ["faixa"]).select("faixa", "votos")
        obtido = serie.filter(pl.col("dias_antes") == d).select("faixa", "votos")
        assert obtido.sort("faixa").equals(esperado.sort("faixa"))


def test_serie_inclui_votos_anteriores_ao_primeiro_dia(base: pl.DataFrame) -> None:
    serie = ind.serie(base, ["faixa"], [10, 5, 0])
    primeiro = serie.filter(pl.col("dias_antes") == 10)["votos"].sum()
    assert primeiro == ind.contagens(base, 10, ["faixa"])["votos"].sum()


def test_decomposicao_shapley_soma_a_variacao_da_quota(
    base: pl.DataFrame, atual: pl.DataFrame
) -> None:
    tabela = ind.comparacao(atual, base, 10)
    variacao = (tabela["quota"] - tabela["quota_base"]).to_numpy()
    soma = (tabela["efeito_recenseamento"] + tabela["efeito_participacao"]).to_numpy()
    np.testing.assert_allclose(soma, variacao, atol=1e-12)
    assert tabela["quota"].sum() == pytest.approx(1.0)


def test_shapley_isola_cada_efeito() -> None:
    r = np.array([0.5, 0.5])
    t = np.array([0.2, 0.4])
    so_recenseamento = ind.decomposicao_shapley(r, t, np.array([0.6, 0.4]), t)
    np.testing.assert_allclose(so_recenseamento[1], 0.0, atol=1e-15)
    so_participacao = ind.decomposicao_shapley(r, t, r, np.array([0.3, 0.4]))
    np.testing.assert_allclose(so_participacao[0], 0.0, atol=1e-15)


def test_esperado_e_desvio(base: pl.DataFrame, atual: pl.DataFrame) -> None:
    tabela = ind.comparacao(atual, base, 15)
    for linha in tabela.iter_rows(named=True):
        if not linha["registados_base"]:
            continue
        esperado = linha["registados"] * linha["votos_base"] / linha["registados_base"]
        assert linha["esperado"] == pytest.approx(esperado)
        assert linha["desvio"] == pytest.approx(linha["votos"] / esperado - 1)


def test_intervalo_do_desvio_contem_o_desvio_do_mesmo_dia(
    base: pl.DataFrame, atual: pl.DataFrame
) -> None:
    tabela = ind.comparacao(atual, base, 15).drop_nulls("desvio")
    assert tabela.height > 0
    assert (tabela["desvio_min"] <= tabela["desvio"] + 1e-12).all()
    assert (tabela["desvio"] <= tabela["desvio_max"] + 1e-12).all()
    # Mais votos de referência até mais tarde: o desvio desce quando a taxa se lê depois.
    assert (tabela["desvio_max"] > tabela["desvio_min"]).any()


def test_comparacao_consigo_propria_e_neutra(base: pl.DataFrame) -> None:
    tabela = ind.comparacao(base, base, 12)
    assert tabela["desvio"].abs().max() == pytest.approx(0.0)
    assert tabela["efeito_recenseamento"].abs().max() == pytest.approx(0.0)
    assert tabela["efeito_participacao"].abs().max() == pytest.approx(0.0)


def test_contributos_historicos_somam_a_taxa(base: pl.DataFrame) -> None:
    d = 8
    contributos = (
        ind.decomposicao_historico(base, d).group_by("faixa").agg(pl.col("contributo").sum())
    )
    taxas = ind.contagens(base, d, ["faixa"]).with_columns(
        (pl.col("votos") / pl.col("registados")).alias("taxa")
    )
    juntos = contributos.join(taxas, on="faixa")
    np.testing.assert_allclose(juntos["contributo"].to_numpy(), juntos["taxa"].to_numpy())


def test_reserva(base: pl.DataFrame) -> None:
    tabela = ind.reserva(base, 5)
    assert (tabela["habituais"] == tabela["ja_votaram"] + tabela["restantes"]).all()
    habituais = base.filter(pl.col("grupo").is_in(ind.GRUPOS_HABITUAIS))["n"].sum()
    assert tabela["habituais"].sum() == habituais


def test_cruzamento_por_modalidade_soma_a_taxa_total(base: pl.DataFrame) -> None:
    d = 3
    por_modo = ind.cruzamento(base, d, "modalidade").group_by("faixa").agg(pl.col("votos").sum())
    total = ind.contagens(base, d, ["faixa"]).select("faixa", "votos")
    assert por_modo.sort("faixa").equals(total.sort("faixa"))


def test_geografia_tem_total_por_unidade(fabrica_painel: FabricaPainel) -> None:
    geo = cubo_geografico(fabrica_painel(3))
    tabela = ind.geografia(geo, 0, "fips_condado")
    totais = tabela.filter(pl.col("faixa") == ind.TOTAL)
    partes = (
        tabela.filter(pl.col("faixa") != ind.TOTAL)
        .group_by("fips_condado")
        .agg(pl.col("votos").sum(), pl.col("registados").sum())
    )
    assert (
        totais.drop("faixa")
        .sort("fips_condado")
        .equals(partes.select(totais.drop("faixa").columns).sort("fips_condado"))
    )
    assert set(tabela["faixa"]) <= {"18-29", "30-49", "50-64", "65+", "desconhecida", "total"}


def _trocar_partidos(cubo: pl.DataFrame) -> pl.DataFrame:
    return cubo.with_columns(pl.col("partido").replace({"dem": "rep", "rep": "dem"}))


def test_troca_de_rotulos_partidarios_troca_os_resultados(
    base: pl.DataFrame, atual: pl.DataFrame
) -> None:
    """Teste de simetria (plano, secção 5.5): nenhuma regra favorece um partido."""
    d = 10

    def comparar(a: pl.DataFrame, b: pl.DataFrame) -> pl.DataFrame:
        return ind.comparacao(a, b, d, por="partido")

    def reservar(a: pl.DataFrame, _b: pl.DataFrame) -> pl.DataFrame:
        return ind.reserva(a, d, ("partido",))

    def cruzar(a: pl.DataFrame, _b: pl.DataFrame) -> pl.DataFrame:
        return ind.cruzamento(a, d, "partido")

    def seriar(a: pl.DataFrame, _b: pl.DataFrame) -> pl.DataFrame:
        return ind.serie(a, ["partido"], [20, 10, 0])

    funcoes = [comparar, reservar, cruzar, seriar]
    for funcao in funcoes:
        original = funcao(atual, base)
        trocado = funcao(_trocar_partidos(atual), _trocar_partidos(base))
        coluna = "partido" if "partido" in original.columns else "categoria"
        reposto = trocado.with_columns(pl.col(coluna).replace({"dem": "rep", "rep": "dem"}))
        chaves = [c for c in original.columns if original[c].dtype == pl.String]
        if "dias_antes" in original.columns:
            chaves.append("dias_antes")
        assert_frame_equal(reposto.sort(chaves), original.sort(chaves), check_exact=False)
