import json
from collections.abc import Callable
from datetime import UTC, date, datetime
from pathlib import Path

import polars as pl
import pytest

from contratos.base import Fonte
from contratos.estados import CodigoEstado
from contratos.voto_antecipado import VotoAntecipadoEstado
from pipeline.comum.calendario import ELEICOES_NC
from pipeline.transform.early_vote.cubos import cubo_demografico, cubo_geografico
from pipeline.transform.early_vote.relatorio import LIMIAR_POPULACAO, CubosAno, montar

FabricaPainel = Callable[..., pl.DataFrame]


@pytest.fixture
def cubos(fabrica_painel: FabricaPainel) -> Callable[[int, int], CubosAno]:
    def fazer(ano: int, semente: int) -> CubosAno:
        painel = fabrica_painel(semente)
        return CubosAno(ELEICOES_NC[ano], cubo_demografico(painel), cubo_geografico(painel))

    return fazer


def _fonte() -> Fonte:
    return Fonte.model_validate(
        {
            "nome": "Teste",
            "url": "https://exemplo.org/absentee.zip",
            "obtida_em": datetime(2026, 10, 13, tzinfo=UTC),
        }
    )


def test_relatorio_valida_contra_o_contrato_e_e_serializavel(
    cubos: Callable[[int, int], CubosAno],
) -> None:
    atual = cubos(2026, 10)
    relatorio = montar(
        estado=CodigoEstado.NC,
        atual=atual,
        bases=[cubos(2022, 11), cubos(2018, 12)],
        dados_ate=date(2026, 10, 24),
        fontes=[_fonte()],
        nomes_condados={"37183": "Wake"},
        avisos=["aviso de teste"],
        gerado_em=datetime(2026, 10, 25, tzinfo=UTC),
    )
    assert relatorio.dias_antes == 10
    assert [c.ano for c in relatorio.ciclos] == [2026, 2022, 2018]
    assert {linha.ano_base for linha in relatorio.comparacao} == {2022, 2018}
    # 2018 não tem histórico individual de referência; 2026 e 2022 têm.
    assert {linha.ano for linha in relatorio.historico} == {2026, 2022}
    dias_2026 = {p.dias_antes for p in relatorio.serie if p.ano == 2026}
    assert min(dias_2026) == 10
    assert max(dias_2026) == 60
    dias_2022 = {p.dias_antes for p in relatorio.serie if p.ano == 2022}
    assert min(dias_2022) == 0
    total = next(
        p
        for p in relatorio.serie
        if p.ano == 2026 and p.dias_antes == 10 and p.faixa == "total"
        and p.partido == "total" and p.modalidade == "total"
    )  # fmt: skip
    assert total.votos == relatorio.ciclos[0].votos_antecipados
    nomes = {(g.nivel, g.codigo): g.nome for g in relatorio.geografia}
    assert nomes[("condado", "37183")] == "Wake"
    assert nomes[("distrito", "1")] == "NC-01"
    texto = relatorio.model_dump_json()
    assert VotoAntecipadoEstado.model_validate(json.loads(texto)) == relatorio


def test_recusa_dados_posteriores_a_eleicao(cubos: Callable[[int, int], CubosAno]) -> None:
    with pytest.raises(ValueError, match="posteriores"):
        montar(
            estado=CodigoEstado.NC,
            atual=cubos(2026, 1),
            bases=[],
            dados_ate=date(2026, 11, 4),
            fontes=[_fonte()],
            nomes_condados={},
        )


def test_series_por_modalidade_somam_o_total(cubos: Callable[[int, int], CubosAno]) -> None:
    relatorio = montar(
        estado=CodigoEstado.NC,
        atual=cubos(2026, 5),
        bases=[],
        dados_ate=date(2026, 10, 30),
        fontes=[_fonte()],
        nomes_condados={},
    )
    serie = pl.DataFrame([p.model_dump() for p in relatorio.serie])
    modos = serie.filter((pl.col("partido") == "total") & (pl.col("modalidade") != "total"))
    soma = modos.group_by("faixa", "dias_antes").agg(pl.col("votos").sum())
    total = serie.filter((pl.col("partido") == "total") & (pl.col("modalidade") == "total"))
    juntos = total.join(soma, on=["faixa", "dias_antes"], suffix="_modos")
    assert (juntos["votos"] == juntos["votos_modos"]).all()


IDENTIFICADORES = {
    "ncid",
    "voter_reg_num",
    "last_name",
    "first_name",
    "res_street_address",
    "morada",
    "data_nascimento",
    "ano_nascimento",
    "idade",
}
"""Colunas que identificam (ou ajudam a identificar) um eleitor: nunca saem do painel.

``nome`` não está aqui porque no ficheiro publicado é o nome do condado ou da fonte."""

PASTA_REFERENCIA = Path(__file__).resolve().parents[3] / "data" / "reference" / "nc"


def _campos(valor: object) -> set[str]:
    if isinstance(valor, dict):
        return set(valor) | {c for v in valor.values() for c in _campos(v)}
    if isinstance(valor, list):
        return {c for v in valor for c in _campos(v)}
    return set()


def test_cubos_nao_tem_colunas_identificadoras(fabrica_painel: FabricaPainel) -> None:
    painel = fabrica_painel(3)
    assert "ncid" in painel.columns
    for cubo in (cubo_demografico(painel), cubo_geografico(painel)):
        assert not IDENTIFICADORES & set(cubo.columns)


def test_cubos_de_referencia_versionados_nao_tem_colunas_identificadoras() -> None:
    ficheiros = sorted(PASTA_REFERENCIA.glob("cubo_*.parquet"))
    assert ficheiros, "faltam os cubos de referência"
    for ficheiro in ficheiros:
        assert not IDENTIFICADORES & set(pl.read_parquet_schema(ficheiro)), ficheiro.name


def test_publicado_sem_identificadores_nem_celulas_pequenas(fabrica_painel: FabricaPainel) -> None:
    # Painel pequeno para haver de certeza células com 1 a 9 recenseados.
    painel = fabrica_painel(4, 300)
    atual = CubosAno(ELEICOES_NC[2026], cubo_demografico(painel), cubo_geografico(painel))
    relatorio = montar(
        estado=CodigoEstado.NC,
        atual=atual,
        bases=[],
        dados_ate=date(2026, 10, 24),
        fontes=[_fonte()],
        nomes_condados={},
    )
    dados = json.loads(relatorio.model_dump_json())
    assert not IDENTIFICADORES & _campos(dados)
    populacoes = [
        linha.get("registados", linha.get("habituais"))
        for chave in ("serie", "comparacao", "historico", "reserva", "geografia", "cruzamentos")
        for linha in dados[chave]
    ]
    assert populacoes
    assert all(p == 0 or p >= LIMIAR_POPULACAO for p in populacoes)
    # O total do ciclo continua a contar toda a gente, incluindo as células suprimidas.
    assert relatorio.ciclos[0].registados == painel.height
