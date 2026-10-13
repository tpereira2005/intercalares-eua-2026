"""Conectores de resultados lidos sobre excertos reais dos ficheiros oficiais (agregados
públicos por condado, sem dados de eleitores)."""

import functools
import http.server
import threading
import zipfile
from collections.abc import Iterator
from datetime import UTC, date, datetime
from pathlib import Path

import pytest

from contratos.base import Fonte
from contratos.estados import CodigoEstado
from pipeline.connectors.results.clarity.conector import CAROLINA_DO_SUL
from pipeline.connectors.results.comum import identificar_corrida, partido
from pipeline.connectors.results.fl.conector import ConectorFL
from pipeline.connectors.results.ga.conector import ConectorGA
from pipeline.connectors.results.nc.conector import ConectorNC
from pipeline.jobs.resultados import Recolha, executar
from pipeline.transform.resultados import ensaio
from pipeline.transform.resultados.avaliacao import csv_avaliacao
from pipeline.transform.resultados.montar import Leitura, montar
from pipeline.transform.resultados.parciais import montar_parciais


def _fonte() -> Fonte:
    return Fonte.model_validate(
        {"nome": "Teste", "url": "https://exemplo.org/r.txt", "obtida_em": datetime.now(UTC)}
    )


DADOS = Path(__file__).parent / "dados"


@pytest.fixture
def pasta_sc(tmp_path: Path) -> Path:
    """O site Clarity serve o XML dentro de um zip; o excerto está versionado sem zip."""
    with zipfile.ZipFile(tmp_path / "detailxml.zip", "w") as z:
        z.write(DADOS / "sc" / "detail.xml", "detail.xml")
    return tmp_path


def _totais(leitura: Leitura, corrida: str) -> dict[str, int]:
    estado = leitura.votos.filter(
        (leitura.votos["corrida"] == corrida) & (leitura.votos["nivel"] == "estado")
    )
    tabela = estado if estado.height else leitura.votos.filter(leitura.votos["corrida"] == corrida)
    return {
        nome: int(tabela.filter(tabela["nome"] == nome)["votos"].sum())
        for nome in tabela["nome"].unique().to_list()
    }


@pytest.mark.parametrize(
    ("nome", "esperado"),
    [
        ("US SENATE (VOTE FOR 1)", "NC-S"),
        ("United States Senator", "NC-S"),
        ("U.S. Senate - Unexpired Term", "NC-S-especial"),
        ("US HOUSE OF REPRESENTATIVES DISTRICT 01 (VOTE FOR 1)", "NC-01"),
        ("Representative in Congress, District 27", "NC-27"),
        ("U.S.  House of Representatives, District  1", "NC-01"),
        ("US House Dist 13", "NC-13"),
        ("13TH CONGRESSIONAL DISTRICT", "NC-13"),
        ("Governor and Lieutenant Governor", "NC-G"),
        ("Lieutenant Governor", None),
        ("State  House of Representatives, District  1", None),
        ("NC SUPREME COURT ASSOCIATE JUSTICE SEAT 03", None),
    ],
)
def test_identificar_corrida(nome: str, esperado: str | None) -> None:
    desc = identificar_corrida(CodigoEstado.NC, nome)
    assert (desc.id if desc else None) == esperado


def test_partidos_sao_so_tres_rotulos() -> None:
    assert [partido(p) for p in ("DEM", "Rep", "Democratic Party", "LIB", "", None)] == [
        "dem", "rep", "dem", "outro", "outro", "outro"
    ]  # fmt: skip


def test_carolina_do_norte_2022() -> None:
    leitura = ConectorNC().ler(DADOS / "nc", date(2022, 11, 8))
    ids = {c.id for c in leitura.corridas}
    assert ids == {"NC-S", "NC-01", "NC-11"}
    senado = _totais(leitura, "NC-S")
    assert senado["Ted Budd"] == 1_905_786
    assert senado["Cheri Beasley"] == 1_784_049
    alamance = leitura.votos.filter(
        (leitura.votos["codigo"] == "37001") & (leitura.votos["nome"] == "Ted Budd")
    )
    assert alamance["votos"].to_list() == [32_866]


def test_carolina_do_norte_usa_o_fips_do_census_e_nao_a_ordem_da_ncsbe() -> None:
    """O ficheiro 56 da NCSBE é Macon (FIPS 37113); a ordem alfabética da NCSBE põe
    McDowell (37111) depois de Martin, ao contrário do Census."""
    leitura = ConectorNC().ler(DADOS / "nc", date(2022, 11, 8))
    budd = leitura.votos.filter(leitura.votos["nome"] == "Ted Budd")
    assert set(budd["codigo"].drop_nulls().to_list()) == {"37001", "37113"}


def test_florida_2024() -> None:
    leitura = ConectorFL().ler(DADOS / "fl", date(2024, 11, 5))
    assert {c.id for c in leitura.corridas} >= {"FL-S", "FL-03", "FL-26", "FL-27"}
    assert set(leitura.votos["codigo"].unique().to_list()) <= {"12001", "12003", "12086", "12109"}
    assert "outro" in leitura.votos["partido"].to_list()


def test_georgia_2024() -> None:
    leitura = ConectorGA().ler(DADOS / "ga", date(2024, 11, 5))
    assert {c.id for c in leitura.corridas} == {"GA-02", "GA-13"}
    assert leitura.atualizado_fonte is not None
    assert all(" (" not in n for n in leitura.votos["nome"].to_list())


def test_carolina_do_sul_2022(pasta_sc: Path) -> None:
    leitura = CAROLINA_DO_SUL.ler(pasta_sc, date(2022, 11, 8))
    assert {c.id for c in leitura.corridas} == {"SC-S", "SC-01"}
    senado = leitura.votos.filter(leitura.votos["corrida"] == "SC-S")
    estado = senado.filter(senado["nivel"] == "estado")
    condados = senado.filter(senado["nivel"] == "condado")
    assert estado["votos"].sum() == condados["votos"].sum()
    assert "Tim Scott" in estado["nome"].to_list()
    assert condados["codigo"].n_unique() == 46


def test_ensaio_reconstroi_uma_noite_sem_descidas(pasta_sc: Path) -> None:
    leitura = CAROLINA_DO_SUL.ler(pasta_sc, date(2022, 11, 8))
    passos = ensaio.progressao(leitura, 6, semente=3)
    assert len(passos) == 6
    assert passos[-1] is leitura
    retratos = [
        montar(estado=CodigoEstado.SC, data_eleicao=date(2022, 11, 8), leitura=p, fontes=[_fonte()])
        for p in passos
    ]
    assert ensaio.verificar_sequencia(retratos) == []
    assert retratos[0].corridas[0].total < retratos[-1].corridas[0].total


def test_parciais_seguem_a_interface_do_modelo() -> None:
    nc = ConectorNC().ler(DADOS / "nc", date(2022, 11, 8))
    ga = ConectorGA().ler(DADOS / "ga", date(2024, 11, 5))
    parciais = montar_parciais(
        [nc, ga], ano=2022, instante=datetime(2022, 11, 9, tzinfo=UTC), fontes=[_fonte()]
    )
    por_chave = {(u.corrida, u.unidade): u for u in parciais.unidades}
    alamance = por_chave[("NC-S", "37001")]
    assert (alamance.votos_r, alamance.seccoes_totais) == (32_866, 38)
    assert sum(m.votos_r for m in alamance.por_modo) == alamance.votos_r
    assert {m.modo for m in alamance.por_modo} >= {"dia_eleicao", "correio"}
    assert ("GA-02", "total") in por_chave
    assert not any(u.corrida.endswith("-G") for u in parciais.unidades)


def test_csv_da_avaliacao_so_tem_corridas_apuradas() -> None:
    leitura = ConectorNC().ler(DADOS / "nc", date(2022, 11, 8))
    r = montar(estado=CodigoEstado.NC, data_eleicao=date(2022, 11, 8), leitura=leitura,
               fontes=[_fonte()])  # fmt: skip
    texto = csv_avaliacao([r])
    linhas = {ln.split(",")[0]: ln.split(",")[1:] for ln in texto.splitlines()[1:]}
    assert linhas["NC-S"][0] == "R"
    assert float(linhas["NC-S"][1]) == pytest.approx(
        100 * (1_784_049 - 1_905_786) / r.corridas[0].total, abs=1e-3
    )


class _Servidor(http.server.ThreadingHTTPServer):
    daemon_threads = True


@pytest.fixture
def espelho(tmp_path: Path) -> Iterator[str]:
    """Servidor local com o ficheiro da Florida no caminho do feed oficial."""
    destino = tmp_path / "espelho" / "flelectionfiles.floridados.gov" / "enightfilespublic"
    destino.mkdir(parents=True)
    (destino / "20241105_ElecResultsFL.txt").write_bytes(
        (DADOS / "fl" / "resultados.txt").read_bytes()
    )
    gestor = functools.partial(
        http.server.SimpleHTTPRequestHandler, directory=str(tmp_path / "espelho")
    )
    gestor.log_message = lambda *_: None  # type: ignore[attr-defined]
    servidor = _Servidor(("127.0.0.1", 0), gestor)
    fio = threading.Thread(target=servidor.serve_forever, daemon=True)
    fio.start()
    yield f"http://127.0.0.1:{servidor.server_address[1]}"
    servidor.shutdown()


def test_recolha_publica_so_quando_a_fonte_muda(espelho: str, tmp_path: Path) -> None:
    recolha = Recolha(date(2024, 11, 5), tmp_path / "pub", tmp_path / "brutos", espelho)
    primeiro = recolha.ciclo([ConectorFL()])
    assert {p.name for p in primeiro} == {"fl.json", "nacional.json", "parciais.json"}
    assert recolha.ciclo([ConectorFL()]) == []
    assert executar(recolha, [ConectorFL()], intervalo=0, ciclos=2) == 2
    assert len(list((tmp_path / "brutos" / "fl").iterdir())) == 2  # "atual" e um retrato
    assert len(list((tmp_path / "brutos" / "parciais").iterdir())) == 1
