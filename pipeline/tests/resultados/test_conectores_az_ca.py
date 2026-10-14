"""Conectores do condado de Maricopa (Arizona) e da Califórnia.

O ficheiro de Maricopa é o oficial de 2026 (a zero, de 21 de setembro) reduzido a três
corridas e três secções por corrida, com votos e tipos de voto inventados (a fonte ainda não
tem votos). Os da Califórnia são excertos dos JSON de 14 de outubro de 2026.
"""

from datetime import UTC, date, datetime
from pathlib import Path

import polars as pl
import pytest

from contratos.base import Fonte
from contratos.estados import CodigoEstado
from pipeline.comum.erros import ErroDescarga, ErroFormatoFonte
from pipeline.connectors.results.ca.conector import ConectorCA
from pipeline.connectors.results.condados.conector import ConectorCondados
from pipeline.connectors.results.condados.maricopa import FonteMaricopa, procurar_ficheiro
from pipeline.connectors.results.registo import CONECTORES, DISTRITOS
from pipeline.transform.resultados import ensaio
from pipeline.transform.resultados.avaliacao import linhas
from pipeline.transform.resultados.montar import Leitura, montar
from pipeline.transform.resultados.parciais import montar_parciais

DADOS = Path(__file__).parent / "dados"
DATA = date(2026, 11, 3)
ARIZONA = ConectorCondados(CodigoEstado.AZ, (FonteMaricopa(),))

PAGINA = """
<p class="mb-1"><small><a href="/asset/jcr:e59c/Results%20File%20Descriptions.pdf"
 target="_blank">Results File Descriptions.pdf</a></small></p>
<p class="mb-1"><small><a href="/asset/jcr:bd0c/Zero%20for%20Web%20-%20Gen%202026.txt"
 target="_blank">2026 November General Election Results.txt</a></small></p>
<p class="mb-1"><small><a href="/asset/jcr:5f56/WCAG_Zero.pdf" target="_blank">
 2026 November General Election Results.pdf</a></small></p>
<p class="mb-1"><small><a href="/asset/jcr:1111/Primary.txt" target="_blank">
 2026 July Primary Election Results.txt</a></small></p>
"""


def _fonte() -> Fonte:
    return Fonte.model_validate(
        {"nome": "Teste", "url": "https://exemplo.org/r.json", "obtida_em": datetime.now(UTC)}
    )


def _votos(leitura: Leitura, corrida: str) -> dict[str, int]:
    tabela = leitura.votos.filter(pl.col("corrida") == corrida)
    return dict(zip(tabela["nome"].to_list(), tabela["votos"].to_list(), strict=True))


@pytest.fixture
def pasta(tmp_path: Path) -> Path:
    destino = tmp_path / "04013"
    destino.mkdir()
    (destino / "resultados.txt").write_bytes((DADOS / "maricopa" / "resultados.txt").read_bytes())
    return tmp_path


def test_estados_registados() -> None:
    assert isinstance(CONECTORES[CodigoEstado.AZ], ConectorCondados)
    assert isinstance(CONECTORES[CodigoEstado.CA], ConectorCA)
    assert DISTRITOS[CodigoEstado.AZ] == 9
    assert DISTRITOS[CodigoEstado.CA] == 52


# --- Maricopa -----------------------------------------------------------------------------


def test_maricopa_procura_o_ficheiro_na_pagina() -> None:
    url = procurar_ficheiro(PAGINA, 2026)
    assert url == (
        "https://elections.maricopa.gov/asset/jcr:bd0c/Zero%20for%20Web%20-%20Gen%202026.txt"
    )


def test_maricopa_pedidos_vao_para_a_subpasta_do_condado() -> None:
    vistos: list[str] = []

    def obter(url: str) -> str:
        vistos.append(url)
        return PAGINA

    pedidos = ARIZONA.pedidos(DATA, obter)
    assert vistos == ["https://elections.maricopa.gov/results-and-data/election-results.html"]
    assert [p.ficheiro for p in pedidos] == ["04013/resultados.txt"]
    assert pedidos[0].url.endswith("Gen%202026.txt")


@pytest.mark.parametrize("ano", [2022, 2024])
def test_maricopa_sem_ficheiro_de_eleicoes_passadas(ano: int) -> None:
    with pytest.raises(ErroDescarga, match=f"eleição geral de {ano}"):
        ARIZONA.pedidos(date(ano, 11, 5), lambda _url: PAGINA)


def test_maricopa_corridas_e_cobertura(pasta: Path) -> None:
    leitura = ARIZONA.ler(pasta, DATA)
    # Sem as corridas legislativas do estado; sem Senado (não há em 2026).
    assert {c.id for c in leitura.corridas} == {"AZ-01", "AZ-G"}
    cargos = {c.id: (c.cargo, c.distrito) for c in leitura.corridas}
    assert cargos == {"AZ-01": ("camara", 1), "AZ-G": ("governador", None)}
    assert leitura.cobertura_condados == ("04013",)
    assert set(leitura.votos["nivel"]) == {"condado"}
    assert set(leitura.votos["codigo"]) == {"04013"}


def test_maricopa_nomes_partidos_e_candidatos_especiais(pasta: Path) -> None:
    leitura = ARIZONA.ler(pasta, DATA)
    governador = leitura.votos.filter(pl.col("corrida") == "AZ-G")
    partidos = dict(zip(governador["nome"], governador["partido"], strict=True))
    assert partidos["KATIE HOBBS"] == "dem"
    assert partidos["ANDY BIGGS"] == "rep"
    assert partidos["RISA LOMBARDO"] == "outro"
    # Candidato de inscrição manual qualificado: conta como "outro" mesmo com a sigla REP.
    assert partidos["GERTRITRUDE GONZALEZ"] == "outro"
    assert partidos["Write-in"] == "outro"
    assert not any(n.startswith("*") for n in governador["nome"])
    # Aspas do nome mantêm-se na fonte mas saem do nome.
    camara = _votos(leitura, "AZ-01")
    assert "THOMAS JAY FEELY IV" in camara
    assert camara["AMISH SHAH"] == 357
    assert camara["THOMAS JAY FEELY IV"] == 416


def test_maricopa_totais_batem_com_a_soma_das_seccoes(pasta: Path) -> None:
    leitura = ARIZONA.ler(pasta, DATA)
    assert _votos(leitura, "AZ-G")["ANDY BIGGS"] == 700
    assert _votos(leitura, "AZ-G")["KATIE HOBBS"] == 295
    assert _votos(leitura, "AZ-G")["KATIE HOBBS"] == 155 + 140  # secções 1 e 2


def test_maricopa_seccoes_apuradas(pasta: Path) -> None:
    leitura = ARIZONA.ler(pasta, DATA)
    unidades = {r["corrida"]: (r["reportadas"], r["totais"]) for r in leitura.unidades.to_dicts()}
    # 2 de 3 secções com resultados em cada corrida do excerto.
    assert unidades == {"AZ-01": (2, 3), "AZ-G": (2, 3)}
    assert set(leitura.unidades["nivel"]) == {"condado"}
    assert leitura.tipo_unidade == "seccao"


def test_maricopa_modalidades_somam_o_total_de_cada_candidato(pasta: Path) -> None:
    leitura = ARIZONA.ler(pasta, DATA)
    assert leitura.modalidades is not None
    assert set(leitura.modalidades["modalidade"]) <= {
        "correio",
        "dia_eleicao",
        "provisorio",
        "outro",
    }
    por_modo = leitura.modalidades.group_by("corrida", "candidato").agg(pl.col("votos").sum())
    juntos = leitura.votos.select("corrida", "candidato", "votos").join(
        por_modo, on=["corrida", "candidato"], suffix="_modos"
    )
    assert juntos.height == leitura.votos.height
    assert (juntos["votos"] == juntos["votos_modos"]).all()
    hobbs = leitura.modalidades.filter(
        (pl.col("corrida") == "AZ-G") & (pl.col("candidato") == "KATIE HOBBS")
    )
    modos = dict(zip(hobbs["modalidade"], hobbs["votos"], strict=True))
    # "Early Vote" (114) e "Early A.R.S. 16-579" (26) são correio; 142 no dia; 8 provisórios.
    assert modos == {"correio": 140, "dia_eleicao": 142, "provisorio": 8, "outro": 5}


def test_maricopa_cobertura_parcial_fora_da_avaliacao_e_parciais(pasta: Path) -> None:
    leitura = ARIZONA.ler(pasta, DATA)
    resultado = montar(
        estado=CodigoEstado.AZ, data_eleicao=DATA, leitura=leitura, fontes=[_fonte()]
    )
    assert resultado.cobertura == "condados"
    assert resultado.condados_cobertos == ("04013",)
    assert linhas([resultado]) == []  # nunca entra na avaliação da previsão
    parciais = montar_parciais(
        [leitura], ano=2026, instante=datetime(2026, 11, 4, tzinfo=UTC), fontes=[_fonte()]
    )
    # Os parciais do Modelo C só levam Senado e Câmara (o governador não entra).
    assert {u.corrida for u in parciais.unidades} == {"AZ-01"}
    assert {u.unidade for u in parciais.unidades} == {"04013"}  # sem "total" do estado
    assert [c.estado for c in parciais.cobertura_parcial] == [CodigoEstado.AZ]


def test_maricopa_ensaio_sem_descidas(pasta: Path) -> None:
    leitura = ARIZONA.ler(pasta, DATA)
    retratos = [
        montar(estado=CodigoEstado.AZ, data_eleicao=DATA, leitura=p, fontes=[_fonte()])
        for p in ensaio.progressao(leitura, 4, semente=3)
    ]
    assert ensaio.verificar_sequencia(retratos) == []


def test_maricopa_colunas_inesperadas(tmp_path: Path) -> None:
    (tmp_path / "04013").mkdir()
    (tmp_path / "04013" / "resultados.txt").write_text("A\tB\n1\t2\n", "utf-8")
    with pytest.raises(ErroFormatoFonte, match="colunas inesperadas"):
        ARIZONA.ler(tmp_path, DATA)


def test_maricopa_tipos_de_voto_acima_do_total(pasta: Path) -> None:
    ficheiro = pasta / "04013" / "resultados.txt"
    linhas_ = ficheiro.read_bytes().decode("utf-8").splitlines()
    cabecalho = linhas_[0].split("\t")
    i = cabecalho.index("Votes")
    # Primeira linha de total do condado do governador: sobe o tipo "dia da eleição".
    for n, linha in enumerate(linhas_):
        campos = linha.split("\t")
        if len(campos) > i and campos[2] == "Governor" and not campos[7]:
            campos[cabecalho.index("Votes_Election Day")] = "99999"
            linhas_[n] = "\t".join(campos)
            break
    ficheiro.write_bytes("\r\n".join(linhas_).encode("utf-8"))
    with pytest.raises(ErroFormatoFonte, match="excedem o total"):
        ARIZONA.ler(pasta, DATA)


# --- Califórnia ---------------------------------------------------------------------------


def test_california_pedidos() -> None:
    pedidos = ConectorCA().pedidos(DATA, lambda _url: "")
    assert [(p.url, p.ficheiro) for p in pedidos] == [
        ("https://media.sos.ca.gov/media/us-rep.json", "us-rep.json"),
        ("https://media.sos.ca.gov/media/governor.json", "governor.json"),
    ]


def test_california_so_o_total_de_cada_corrida() -> None:
    leitura = ConectorCA().ler(DADOS / "ca", DATA)
    # Distritos 1, 2 e 6 e governador; as linhas de condado ficam de fora.
    assert {c.id for c in leitura.corridas} == {"CA-01", "CA-02", "CA-06", "CA-G"}
    cargos = {c.id: (c.cargo, c.distrito) for c in leitura.corridas}
    assert cargos["CA-06"] == ("camara", 6)
    assert cargos["CA-G"] == ("governador", None)
    assert set(leitura.votos["nivel"]) == {"estado"}
    assert leitura.modalidades is None
    assert leitura.cobertura_condados == ()


def test_california_votos_partidos_e_apuramento() -> None:
    leitura = ConectorCA().ler(DADOS / "ca", DATA)
    governador = _votos(leitura, "CA-G")
    assert governador == {"Xavier Becerra": 289_268, "Steve Hilton": 622_492}
    partidos = dict(zip(leitura.votos["nome"], leitura.votos["partido"], strict=True))
    assert (partidos["Xavier Becerra"], partidos["Steve Hilton"]) == ("dem", "rep")
    assert partidos["Kevin Kiley"] == "outro"  # NPP
    unidades = {r["corrida"]: (r["reportadas"], r["totais"]) for r in leitura.unidades.to_dicts()}
    assert unidades["CA-G"] == (6_687, 23_860)
    assert unidades["CA-01"] == (275, 788)
    assert leitura.atualizado_fonte is not None
    assert leitura.atualizado_fonte.isoformat() == "2026-11-03T21:54:00-08:00"


def test_california_resultado_montado() -> None:
    leitura = ConectorCA().ler(DADOS / "ca", DATA)
    r = montar(estado=CodigoEstado.CA, data_eleicao=DATA, leitura=leitura, fontes=[_fonte()])
    assert r.cobertura == "estado"
    assert [c.id for c in r.corridas if c.cargo == "camara"] == ["CA-01", "CA-02", "CA-06"]
    governador = next(c for c in r.corridas if c.id == "CA-G")
    assert governador.total == 289_268 + 622_492


def test_california_recusa_ficheiro_de_outro_ano() -> None:
    with pytest.raises(ErroFormatoFonte, match="é de 2026, não de 2024"):
        ConectorCA().ler(DADOS / "ca", date(2024, 11, 5))


def test_california_formato_inesperado(tmp_path: Path) -> None:
    (tmp_path / "us-rep.json").write_text('{"a": 1}', "utf-8")
    (tmp_path / "governor.json").write_text("[]", "utf-8")
    with pytest.raises(ErroFormatoFonte, match="formato inesperado"):
        ConectorCA().ler(tmp_path, DATA)


def test_california_sem_corridas(tmp_path: Path) -> None:
    (tmp_path / "us-rep.json").write_text("[]", "utf-8")
    (tmp_path / "governor.json").write_text("[]", "utf-8")
    with pytest.raises(ErroFormatoFonte, match="nenhuma corrida"):
        ConectorCA().ler(tmp_path, DATA)


def test_california_dados_antes_do_fecho_contam_como_ensaio(tmp_path: Path) -> None:
    for f in (DADOS / "ca").iterdir():
        texto = f.read_text(encoding="utf-8").replace(
            "November 3, 2026, 9:", "November 3, 2026, 7:"
        )
        (tmp_path / f.name).write_text(texto, encoding="utf-8")
    leitura = ConectorCA().ler(tmp_path, DATA)
    assert len(leitura.corridas) == 4
    assert leitura.votos["votos"].sum() == 0
    assert leitura.unidades["reportadas"].sum() == 0
