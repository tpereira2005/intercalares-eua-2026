"""Conectores da Pensilvânia, do Maine e da Florida com linhas sintéticas (nenhum dado real)."""

from datetime import UTC, date, datetime
from pathlib import Path

import polars as pl
import pytest

from pipeline.comum.calendario import eleicao_geral
from pipeline.comum.erros import ErroFormatoFonte
from pipeline.connectors.early_vote.agregados import CONECTORES, ultimo_dia_completo
from pipeline.connectors.early_vote.fl import fontes as fontes_fl
from pipeline.connectors.early_vote.fl.ler import juntar_arquivo, ler_estatisticas
from pipeline.connectors.early_vote.me import fontes as fontes_me
from pipeline.connectors.early_vote.me.ler import ler_boletins
from pipeline.connectors.early_vote.pa import codigos as codigos_pa
from pipeline.connectors.early_vote.pa.fontes import url_pedidos
from pipeline.connectors.early_vote.pa.ler import ler_pedidos
from pipeline.transform.early_vote.agregado import COLUNAS_BOLETINS

PA_2026 = """\
"countyname","party","dateofbirth","appissuedate","ballotreturneddate","congressional","ballot_status"
"ADAMS","REP","1959-09","2026-01-28T00:00:00.000",,"13TH CONGRESSIONAL DISTRICT","Pending"
"PHILADELPHIA","DEM","2001-03","2026-09-02","2026-10-07","3RD CONGRESSIONAL DISTRICT","Recorded"
"YORK","OTH","1980-12","2026-09-10","2026-10-01","10TH CONGRESSIONAL DISTRICT","Cancelled"
"MCKEAN","LIB","1950-01","2026-08-01","2026-10-02","15TH CONGRESSIONAL DISTRICT","Vote Recorded"
"""

PA_2022 = """\
"countyname","party","dateofbirth","appissuedate","ballotreturneddate","congressional"
"ADAMS","D","1959-01-10T00:00:00.000","2022-10-11","2022-10-20","13TH CONGRESSIONAL DISTRICT"
"ERIE","NF","1990-05-02T00:00:00.000","2022-10-01T00:00:00.000",,"16TH CONGRESSIONAL DISTRICT"
"""

ME_ANTIGO = (
    "MUNICIPALITY|CH|DES|VOTER ID|P|W/P|CG|SS|SR|CC|REQTYPE|REQDATE|REQDEN|ISSTYPE|ISSDATE"
    "|RECTYPE|RECDATE|DUP|ACC OR REJ|REJRSN|\n"
    """\
VILA A|||900000001|D|1-1|2|4|30|1|ER|10/14/2022||MV|10/14/2022|DV|11/08/2022 04:31 pm||ACC||
VILA A|||900000002|R|1-1|2|4|30|1|VP|10/20/2022||VP|10/20/2022|VP|10/20/2022 10:00 am||ACC||
VILA B|||900000003|U|1-1|1|4|30|1|WV|10/01/2022||MV|10/02/2022||||||
VILA B|||900000004|G|1-1|1|4|30|1|WV|10/01/2022||MV|10/02/2022|MA|10/09/2022 09:00 am|1|ACC||
VILA B|||900000004|G|1-1|1|4|30|1|WV|10/01/2022||MV|10/12/2022|MA|10/15/2022 09:00 am|2|ACC||
"""
)

ME_2026 = (
    "RES MUNICIPALITY|DES|Voter Record #|P|IB|W-P|CG|SS|SR|DA|CC|Ballot Type|Req Type|Req Date"
    "|Issued Type|Issued Date|Rec Type|Rec Date|Rec Time|DUP|Status|CH|REJ\n"
    """\
VILA A|O|900000001|D||1-1|2|4|30|5|1|RB|UR|02/25/2026|EL|09/17/2026|||||||
VILA A|O|900000002|R||1-1|1|4|30|5|1|RB|VP|10/05/2026|VP|10/05/2026|VP|10/05/2026|10:00 AM||ACT||
"""
)

FL_CABECALHO = (
    "ElectionNumber\tElectionDate\tElectionName\tCountyName\tStatType\tTotalRep\tTotalDem"
    "\tTotalOth\tTotalNpa\tGrandTotal\tCompileDate\n"
)


def _fl(tipo: str, linhas: list[tuple[str, int, int, int, int]], data: str) -> str:
    texto = FL_CABECALHO
    soma = sum(sum(x[1:]) for x in linhas)
    texto += (
        f"1\t11/03/2026\t2026 General\tState Totals\t{tipo}\t0\t0\t0\t0\t{soma:,}\t{data}  8:04AM\n"
    )
    for nome, rep, dem, oth, npa in linhas:
        texto += (
            f"1\t11/03/2026\t2026 General\t{nome}\t{tipo}\t{rep:,}\t{dem:,}\t{oth}\t{npa}"
            f"\t{rep + dem + oth + npa:,}\t{data}  8:04AM\n"
        )
    return texto


def _escrever(pasta: Path, nome: str, texto: str) -> Path:
    caminho = pasta / nome
    caminho.write_text(texto, encoding="utf-8")
    return caminho


def test_pa_normaliza_pedidos_e_anula_cancelados(tmp_path: Path) -> None:
    tabela, rel = ler_pedidos(_escrever(tmp_path, "pa.csv", PA_2026), eleicao_geral("PA", 2026))
    assert rel.linhas_invalidas == 0
    assert tabela.columns == list(COLUNAS_BOLETINS)
    linhas = tabela.rows(named=True)
    assert [x["partido"] for x in linhas] == ["rep", "dem", "outro", "outro"]
    assert linhas[1]["idade"] == 25
    assert linhas[1]["fips_condado"] == "42101"
    assert linhas[3]["fips_condado"] == "42083"
    assert linhas[1]["distrito"] == 3
    assert linhas[1]["data_devolucao"] == date(2026, 10, 7)
    # Cancelado: o boletim existe como pedido, mas não conta como devolvido.
    assert linhas[2]["data_devolucao"] is None
    assert linhas[0]["data_pedido"] == date(2026, 1, 28)


def test_pa_anos_antigos_sem_estado_do_boletim(tmp_path: Path) -> None:
    tabela, _ = ler_pedidos(_escrever(tmp_path, "pa.csv", PA_2022), eleicao_geral("PA", 2022))
    assert tabela["partido"].to_list() == ["dem", "outro"]
    assert tabela["idade"].to_list() == [63, 32]
    assert tabela["data_devolucao"].to_list() == [date(2022, 10, 20), None]


def test_pa_recusa_condados_desconhecidos(tmp_path: Path) -> None:
    errado = PA_2022.replace('"ERIE"', '"NARNIA"').replace('"ADAMS"', '"GONDOR"')
    with pytest.raises(ErroFormatoFonte, match="condado"):
        ler_pedidos(_escrever(tmp_path, "pa.csv", errado), eleicao_geral("PA", 2022))


def test_pa_tem_67_condados_e_url_sem_coordenadas() -> None:
    assert len(codigos_pa.FIPS_CONDADO) == 67
    assert codigos_pa.FIPS_CONDADO["YORK"] == "42133"
    assert codigos_pa.NOME_CONDADO["42083"] == "McKean"
    url = url_pedidos(2026)
    assert "latitude" not in url
    assert "ballot_status" in url
    assert "ballot_status" not in url_pedidos(2022)


def test_me_ficheiro_antigo_um_boletim_por_eleitor(tmp_path: Path) -> None:
    tabela, _ = ler_boletins(_escrever(tmp_path, "me.txt", ME_ANTIGO), eleicao_geral("ME", 2022))
    assert set(tabela.columns) == set(COLUNAS_BOLETINS)
    assert tabela.height == 4
    por_partido = {x["partido"]: x for x in tabela.rows(named=True)}
    assert por_partido["rep"]["modalidade"] == "presencial"
    assert por_partido["dem"]["modalidade"] == "correio"
    assert por_partido["dem"]["data_devolucao"] == date(2022, 11, 8)
    assert por_partido["nao_afiliado"]["data_devolucao"] is None
    # Duplicado: conta a primeira receção.
    assert por_partido["outro"]["data_devolucao"] == date(2022, 10, 9)
    assert tabela["idade"].null_count() == tabela.height


def test_me_ficheiro_2026_com_nomes_novos(tmp_path: Path) -> None:
    tabela, _ = ler_boletins(_escrever(tmp_path, "me.txt", ME_2026), eleicao_geral("ME", 2026))
    assert tabela.height == 2
    assert tabela.filter(pl.col("partido") == "rep")["modalidade"].item() == "presencial"
    assert tabela["distrito"].sort().to_list() == [1, 2]


def test_me_encontra_o_ficheiro_de_2026_na_pagina() -> None:
    html = (
        '<a href="/sos/sites/maine.gov.sos/files/inline-files/E%26R%203.7.26.xlsx">x</a>'
        '<a href="/sos/sites/maine.gov.sos/files/inline-files/11-3-26%20AB%20Voter%20File'
        '%20as%20of%2010-9-26.txt">AB</a>'
    )
    url = fontes_me.url_atual(html)
    assert url is not None
    assert url.startswith("https://www.maine.gov/sos/sites/")
    assert url.endswith("10-9-26.txt")
    assert fontes_me.url_atual("<html></html>") is None


def test_fl_le_estatisticas_e_confere_o_total(tmp_path: Path) -> None:
    votado = _escrever(
        tmp_path,
        "v.txt",
        _fl(
            "Voted Vote-by-Mail",
            [("Alachua", 10, 20, 1, 5), ("Miami-Dade", 100, 90, 3, 40)],
            "10/13/2026",
        ),
    )
    pedido = _escrever(
        tmp_path,
        "p.txt",
        _fl("Vote-by-Mail Provided (Not Yet Returned)", [("St. Johns", 7, 3, 0, 2)], "10/12/2026"),
    )
    retrato = ler_estatisticas([votado, pedido])
    assert set(retrato["fips_condado"]) == {"12001", "12086", "12109"}
    assert retrato.filter(pl.col("tipo") == "correio")["n"].sum() == 269
    assert retrato.filter(pl.col("tipo") == "correio")["dados_ate"].unique().to_list() == [
        date(2026, 10, 12)
    ]
    assert retrato.filter(pl.col("tipo") == "pendentes")["n"].sum() == 12


def test_fl_recusa_totais_que_nao_conferem(tmp_path: Path) -> None:
    texto = _fl("Voted Vote-by-Mail", [("Alachua", 10, 20, 1, 5)], "10/13/2026").replace(
        "\t36\t10/13/2026  8:04AM\n1", "\t99\t10/13/2026  8:04AM\n1", 1
    )
    with pytest.raises(ErroFormatoFonte, match="somam"):
        ler_estatisticas([_escrever(tmp_path, "v.txt", texto)])


def test_fl_arquivo_mantem_um_retrato_por_dia(tmp_path: Path) -> None:
    def retrato(n: int, data: str) -> pl.DataFrame:
        return ler_estatisticas(
            [_escrever(tmp_path, "v.txt", _fl("Voted Vote-by-Mail", [("Bay", n, 0, 0, 0)], data))]
        )

    arquivo = juntar_arquivo(None, retrato(5, "10/12/2026"))
    arquivo = juntar_arquivo(arquivo, retrato(8, "10/13/2026"))
    arquivo = juntar_arquivo(arquivo, retrato(9, "10/13/2026"))
    rep = arquivo.filter(pl.col("partido") == "rep")
    assert rep.select("dados_ate", "n").rows() == [(date(2026, 10, 11), 5), (date(2026, 10, 12), 9)]


def test_fl_lista_os_ficheiros_da_pagina() -> None:
    html = (
        "https://electionfiles.floridados.gov/countyballotreportfiles/Stats_49894_VbmVoted.txt "
        "https://electionfiles.floridados.gov/countyballotreportfiles/Stats_49894_VbmProvided.txt "
        "https://electionfiles.floridados.gov/countyballotreportfiles/Stats_49894_VbmVoted.txt"
    )
    assert len(fontes_fl.urls_estatisticas(html)) == 2


def test_ultimo_dia_completo_exclui_o_dia_da_geracao() -> None:
    gerado = datetime(2026, 10, 13, 13, 49, tzinfo=UTC)
    assert ultimo_dia_completo(date(2026, 10, 13), gerado) == date(2026, 10, 12)
    assert ultimo_dia_completo(date(2026, 10, 10), gerado) == date(2026, 10, 10)
    # 02:00 UTC ainda é o dia anterior na costa leste.
    assert ultimo_dia_completo(date(2026, 10, 13), datetime(2026, 10, 13, 2, tzinfo=UTC)) == date(
        2026, 10, 11
    )
    assert ultimo_dia_completo(None, gerado) is None


def test_registo_dos_conectores_coerente() -> None:
    for estado, conector in CONECTORES.items():
        assert conector.estado == estado
        assert set(conector.anos_base) <= set(conector.urls_base)
        assert set(conector.dimensoes) <= {"faixa", "partido", "modalidade", "condado", "distrito"}
        assert conector.eleicao(2026).data == date(2026, 11, 3)
