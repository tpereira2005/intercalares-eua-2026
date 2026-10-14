"""Conectores da Virgínia (Enhanced Voting) e do Nebraska (CSV do Secretary of State).

O excerto da Virgínia é o ficheiro oficial de 2024 reduzido ao Senado e a dois distritos da
Câmara. Os do Nebraska são o CSV de 14 de outubro de 2026 (boletins por abrir, votos a
zero); ``ne_apurado`` é o mesmo ficheiro com votos e secções inventados, só para testar a
leitura de uma corrida em curso.
"""

from dataclasses import replace
from datetime import UTC, date, datetime
from pathlib import Path

import polars as pl
import pytest

from contratos.base import Fonte
from contratos.estados import CodigoEstado
from pipeline.comum.erros import ErroFormatoFonte
from pipeline.connectors.results.comum import identificar_corrida, modalidade
from pipeline.connectors.results.ne.conector import ConectorNE
from pipeline.connectors.results.registo import CONECTORES, DISTRITOS
from pipeline.connectors.results.va.conector import ConectorVA, identificador
from pipeline.transform.resultados import ensaio
from pipeline.transform.resultados.montar import Leitura, montar
from pipeline.transform.resultados.parciais import montar_parciais

DADOS = Path(__file__).parent / "dados"
DATA_VA = date(2024, 11, 5)
DATA_NE = date(2026, 11, 3)


def _fonte() -> Fonte:
    return Fonte.model_validate(
        {"nome": "Teste", "url": "https://exemplo.org/r.json", "obtida_em": datetime.now(UTC)}
    )


def _votos(leitura: Leitura, corrida: str) -> dict[str, int]:
    tabela = leitura.votos.filter(pl.col("corrida") == corrida)
    return dict(zip(tabela["nome"].to_list(), tabela["votos"].to_list(), strict=True))


def test_estados_registados() -> None:
    assert isinstance(CONECTORES[CodigoEstado.VA], ConectorVA)
    assert isinstance(CONECTORES[CodigoEstado.NE], ConectorNE)
    assert DISTRITOS[CodigoEstado.VA] == 11
    assert DISTRITOS[CodigoEstado.NE] == 3


# --- Virgínia -----------------------------------------------------------------------------


def test_virginia_identificadores_das_eleicoes() -> None:
    assert identificador(date(2024, 11, 5)) == "2024NovemberGeneral"
    assert identificador(date(2026, 11, 3)) == "2026-November-General"
    pedidos = ConectorVA().pedidos(date(2026, 11, 3), lambda _url: "")
    assert [p.url for p in pedidos] == [
        "https://enr.elections.virginia.gov/results/public/api/elections/Virginia/"
        "2026-November-General/data"
    ]


def test_virginia_2024_corridas_e_totais() -> None:
    leitura = ConectorVA().ler(DADOS / "va", DATA_VA)
    assert {c.id for c in leitura.corridas} == {"VA-S", "VA-01", "VA-07"}
    assert {c.id: c.cargo for c in leitura.corridas}["VA-S"] == "senado"
    assert leitura.atualizado_fonte is not None
    assert all(" (" not in n for n in leitura.votos["nome"].to_list())
    senado = _votos(leitura, "VA-S")
    assert senado["Timothy M. Kaine"] == 2_417_115
    assert senado["Hung Cao"] == 2_019_911
    partidos = dict(zip(leitura.votos["nome"], leitura.votos["partido"], strict=True))
    assert (partidos["Timothy M. Kaine"], partidos["Hung Cao"]) == ("dem", "rep")
    assert partidos["Write-In"] == "outro"


def test_virginia_unidades_sao_as_localidades() -> None:
    leitura = ConectorVA().ler(DADOS / "va", DATA_VA)
    assert leitura.tipo_unidade == "condado"
    por_corrida = {
        r["corrida"]: (r["reportadas"], r["totais"]) for r in leitura.unidades.to_dicts()
    }
    assert por_corrida == {"VA-S": (133, 133), "VA-01": (18, 18), "VA-07": (11, 11)}


def test_virginia_modalidades_somam_o_total_de_cada_candidato() -> None:
    leitura = ConectorVA().ler(DADOS / "va", DATA_VA)
    assert leitura.modalidades is not None
    assert set(leitura.modalidades["modalidade"].unique()) == {
        "antecipado_presencial",
        "dia_eleicao",
        "correio",
        "provisorio",
        "outro",
    }
    por_modo = leitura.modalidades.group_by("corrida", "candidato").agg(pl.col("votos").sum())
    totais = leitura.votos.select("corrida", "candidato", "votos")
    juntos = totais.join(por_modo, on=["corrida", "candidato"], suffix="_modos")
    assert juntos.height == totais.height
    assert (juntos["votos"] == juntos["votos_modos"]).all()


@pytest.mark.parametrize(
    ("grupo", "esperado"),
    [
        ("Early Voting", "antecipado_presencial"),
        ("Election Day", "dia_eleicao"),
        ("Mailed Absentee", "correio"),
        ("Provisional", "provisorio"),
        ("Post-Election", "outro"),
    ],
)
def test_virginia_grupos_de_voto(grupo: str, esperado: str) -> None:
    assert modalidade(grupo) == esperado


@pytest.mark.parametrize(
    ("nome", "esperado"),
    [
        ("Member, United States Senate", "VA-S"),
        ("Member, House of Representatives (1st District)", "VA-01"),
        ("Member, House of Representatives (11th District)", "VA-11"),
        ("Member, House of Delegates (20th District)", None),
        ("Sheriff (Galax City, Grayson County)", None),
        ("Proposed Constitutional Amendment Question 1", None),
    ],
)
def test_virginia_reconhece_so_as_corridas_federais(nome: str, esperado: str | None) -> None:
    desc = identificar_corrida(CodigoEstado.VA, nome)
    assert (desc.id if desc else None) == esperado


def test_virginia_pagina_ainda_inexistente(tmp_path: Path) -> None:
    (tmp_path / "estado.json").write_text("", "utf-8")
    with pytest.raises(ErroFormatoFonte, match="ainda não existe"):
        ConectorVA().ler(tmp_path, DATA_VA)


def test_virginia_ensaio_e_parciais() -> None:
    leitura = ConectorVA().ler(DADOS / "va", DATA_VA)
    retratos = [
        montar(estado=CodigoEstado.VA, data_eleicao=DATA_VA, leitura=p, fontes=[_fonte()])
        for p in ensaio.progressao(leitura, 5, semente=1)
    ]
    assert ensaio.verificar_sequencia(retratos) == []
    parciais = montar_parciais(
        [leitura], ano=2024, instante=datetime(2024, 11, 6, tzinfo=UTC), fontes=[_fonte()]
    )
    total = next(u for u in parciais.unidades if u.corrida == "VA-S" and u.unidade == "total")
    assert sum(m.votos_d for m in total.por_modo) == total.votos_d == 2_417_115


# --- Nebraska -----------------------------------------------------------------------------


def test_nebraska_pedidos() -> None:
    pedidos = ConectorNE().pedidos(DATA_NE, lambda _url: "")
    assert [p.url for p in pedidos] == [
        "https://electionresults.nebraska.gov/resultsCSV.aspx?text=All&type=SW&map=DIST",
        "https://electionresults.nebraska.gov/resultsCSV.aspx?text=All&type=CG&map=DIST",
    ]


def test_nebraska_corridas_do_feed_de_2026() -> None:
    leitura = ConectorNE().ler(DADOS / "ne", DATA_NE)
    assert {c.id for c in leitura.corridas} == {"NE-S", "NE-G", "NE-01", "NE-02", "NE-03"}
    cargos = {c.id: (c.cargo, c.distrito) for c in leitura.corridas}
    assert cargos["NE-S"] == ("senado", None)
    assert cargos["NE-G"] == ("governador", None)
    # "- 2  Year Term" é a duração do mandato, não o distrito.
    assert cargos["NE-01"] == ("camara", 1)
    assert cargos["NE-03"] == ("camara", 3)
    assert leitura.atualizado_fonte is not None
    assert (
        leitura.atualizado_fonte.replace(tzinfo=None).isoformat() == "2026-10-14T10:48:40"
    )  # o mais recente dos dois ficheiros
    assert leitura.modalidades is None
    assert leitura.votos["votos"].sum() == 0


def test_nebraska_nomes_e_partidos() -> None:
    leitura = ConectorNE().ler(DADOS / "ne", DATA_NE)
    senado = leitura.votos.filter(pl.col("corrida") == "NE-S")
    nomes = dict(zip(senado["nome"], senado["partido"], strict=True))
    assert nomes["Pete Ricketts"] == "rep"
    assert nomes["Dan Osborn"] == "outro"  # candidatura por petição
    rotulos = dict(zip(senado["nome"], senado["partido_fonte"], strict=True))
    assert rotulos["Dan Osborn"] == "PET"
    governador = leitura.votos.filter(pl.col("corrida") == "NE-G")
    assert "Jim Pillen and Joe Kelly" in governador["nome"].to_list()


def test_nebraska_corrida_em_curso() -> None:
    leitura = ConectorNE().ler(DADOS / "ne_apurado", DATA_NE)
    unidades = {r["corrida"]: (r["reportadas"], r["totais"]) for r in leitura.unidades.to_dicts()}
    assert unidades["NE-S"] == (661, 1322)
    assert unidades["NE-01"] == (219, 438)
    assert unidades["NE-02"] == (167, 334)
    assert unidades["NE-03"] == (319, 639)
    assert set(leitura.votos["nivel"]) == {"estado"}
    r = montar(estado=CodigoEstado.NE, data_eleicao=DATA_NE, leitura=leitura, fontes=[_fonte()])
    senado = next(c for c in r.corridas if c.id == "NE-S")
    assert senado.total == sum(_votos(leitura, "NE-S").values()) > 0
    assert [c.id for c in r.corridas if c.cargo == "camara"] == ["NE-01", "NE-02", "NE-03"]


def test_nebraska_ensaio_sem_descidas() -> None:
    leitura = ConectorNE().ler(DADOS / "ne_apurado", DATA_NE)
    # O ensaio parte de ficheiros finais (todas as secções apuradas).
    leitura = replace(leitura, unidades=leitura.unidades.with_columns(reportadas=pl.col("totais")))
    retratos = [
        montar(estado=CodigoEstado.NE, data_eleicao=DATA_NE, leitura=p, fontes=[_fonte()])
        for p in ensaio.progressao(leitura, 4, semente=2)
    ]
    assert ensaio.verificar_sequencia(retratos) == []


def test_nebraska_colunas_inesperadas(tmp_path: Path) -> None:
    (tmp_path / "estado.csv").write_text("A,B\n1,2\n", "utf-8")
    (tmp_path / "camara.csv").write_text("A,B\n1,2\n", "utf-8")
    with pytest.raises(ErroFormatoFonte, match="colunas inesperadas"):
        ConectorNE().ler(tmp_path, DATA_NE)
