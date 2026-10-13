from pathlib import Path

import polars as pl
import pytest

from pipeline.comum.erros import ErroFormatoFonte
from pipeline.connectors.early_vote.nc.boletins import ESQUEMA_BOLETINS, ler_boletins, votantes

# Linhas sintéticas: nomes, moradas e identificadores inventados, presentes só para
# confirmar que a leitura os descarta.
CABECALHO_BOLETINS = (
    "county_desc,voter_reg_num,ncid,voter_last_name,voter_first_name,voter_middle_name,race,"
    "ethnicity,gender,age,voter_street_address,voter_city,voter_state,voter_zip,"
    "ballot_mail_street_address,ballot_mail_city,ballot_mail_state,ballot_mail_zip,"
    "other_mail_addr1,other_mail_addr2,other_city_state_zip,relative_request_name,"
    "relative_request_address,relative_request_city,relative_request_state,"
    "relative_request_zip,election_dt,voter_party_code,precinct_desc,cong_dist_desc,"
    "nc_house_desc,nc_senate_desc,ballot_req_delivery_type,ballot_req_type,"
    "ballot_request_party,ballot_req_dt,ballot_send_dt,ballot_rtn_dt,ballot_rtn_status,"
    "site_name,sdr,mail_veri_status"
)


def linha_boletim(
    ncid: str,
    *,
    condado: str = "WAKE",
    idade: int = 40,
    partido: str = "DEM",
    raca: str = "WHITE",
    etnia: str = "NOT HISPANIC or NOT LATINO",
    genero: str = "F",
    distrito: int = 2,
    tipo: str = "MAIL",
    devolucao: str = "10/20/2026",
    estado: str = "ACCEPTED",
    sdr: str = " ",
    nome: str = "FICTICIO",
) -> str:
    campos = [
        condado, "000000000001", ncid, nome, "TESTE", "", raca, etnia, genero, str(idade),
        '1 RUA "INVENTADA", APT 2', "RALEIGH", "NC", "27601", "", "", "", "", "", "", "",
        " ", " ", " ", " ", " ", "11/03/2026", partido, "PRECINTO 1",
        f"CONGRESSIONAL DISTRICT {distrito}", "NC HOUSE DISTRICT 1", "NC SENATE DISTRICT 1",
        "MAIL", tipo, partido, "09/01/2026", "09/10/2026", devolucao, estado, " ", sdr, " ",
    ]  # fmt: skip
    return ",".join('"' + c.replace('"', '""') + '"' for c in campos)


def _ficheiro(tmp_path: Path, linhas: list[str], cabecalho: str = CABECALHO_BOLETINS) -> Path:
    caminho = tmp_path / "absentee_20261103.csv"
    caminho.write_text(cabecalho + "\n" + "\n".join(linhas) + "\n", encoding="utf-8")
    return caminho


def test_normaliza_e_descarta_dados_pessoais(tmp_path: Path) -> None:
    caminho = _ficheiro(
        tmp_path,
        [
            linha_boletim("AA1", idade=70, partido="REP", raca="BLACK or AFRICAN AMERICAN"),
            linha_boletim("AA2", condado="NEW HANOVER", tipo="ONE-STOP", partido="LIB"),
        ],
    )
    resultado = ler_boletins(caminho)
    tabela = resultado.boletins
    assert dict(tabela.schema) == ESQUEMA_BOLETINS
    texto = str(tabela.rows())
    assert "FICTICIO" not in texto
    assert "INVENTADA" not in texto
    primeira, segunda = tabela.sort("ncid").iter_rows(named=True)
    assert primeira["partido"] == "rep"
    assert primeira["raca"] == "negra"
    assert primeira["etnia"] == "nao_hispanica"
    assert primeira["fips_condado"] == "37183"
    assert primeira["distrito"] == 2
    assert primeira["modalidade"] == "correio"
    assert segunda["modalidade"] == "presencial"
    assert segunda["partido"] == "outro"
    assert segunda["fips_condado"] == "37129"


def test_estados_e_registo_no_dia(tmp_path: Path) -> None:
    caminho = _ficheiro(
        tmp_path,
        [
            linha_boletim("A", estado="ACCEPTED - CURED"),
            linha_boletim("B", estado="PENDING CURE"),
            linha_boletim("C", estado="SPOILED"),
            linha_boletim("D", estado=" ", devolucao=" "),
            linha_boletim("E", estado="ESTADO NOVO", tipo="ONE-STOP", sdr="Y"),
        ],
    )
    resultado = ler_boletins(caminho)
    estados = dict(resultado.boletins.select("ncid", "estado_boletim").iter_rows())
    assert estados == {
        "A": "aceite",
        "B": "pendente",
        "C": "anulado",
        "D": "por_devolver",
        "E": "desconhecido",
    }
    assert resultado.estados_desconhecidos == {"ESTADO NOVO": 1}
    sdr = resultado.boletins.filter(pl.col("registo_no_dia"))["ncid"].to_list()
    assert sdr == ["E"]


def test_votantes_conta_o_primeiro_boletim_valido_de_cada_eleitor(tmp_path: Path) -> None:
    caminho = _ficheiro(
        tmp_path,
        [
            linha_boletim("X", estado="SPOILED", devolucao="10/01/2026"),
            linha_boletim("X", tipo="ONE-STOP", devolucao="10/16/2026"),
            linha_boletim("X", devolucao="10/20/2026"),
            linha_boletim("Y", estado=" ", devolucao=" "),
            linha_boletim("Z", estado="RETURNED AFTER DEADLINE", devolucao="11/04/2026"),
        ],
    )
    tabela = votantes(ler_boletins(caminho).boletins)
    linhas = {r["ncid"]: r for r in tabela.iter_rows(named=True)}
    assert set(linhas) == {"X", "Z"}
    assert linhas["X"]["modalidade"] == "presencial"
    assert str(linhas["X"]["data_devolucao"]) == "2026-10-16"


def test_falha_quando_a_modalidade_deixa_de_ser_reconhecida(tmp_path: Path) -> None:
    caminho = _ficheiro(tmp_path, [linha_boletim(f"N{i}", tipo="DRONE") for i in range(10)])
    with pytest.raises(ErroFormatoFonte, match="formato da fonte"):
        ler_boletins(caminho)


def test_ficheiro_de_2018_sem_etnia(tmp_path: Path) -> None:
    cabecalho = CABECALHO_BOLETINS.replace("ethnicity,", "")
    linha = linha_boletim("A").replace('"NOT HISPANIC or NOT LATINO",', "")
    tabela = ler_boletins(_ficheiro(tmp_path, [linha], cabecalho)).boletins
    assert tabela["etnia"].to_list() == ["nao_indicada"]
    assert tabela["genero"].to_list() == ["feminino"]
