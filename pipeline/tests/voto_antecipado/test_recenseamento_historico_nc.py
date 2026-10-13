import zipfile
from datetime import date
from pathlib import Path

import polars as pl

from pipeline.comum.condados import nomes
from pipeline.connectors.early_vote.nc.codigos import CONDADOS, FIPS_CONDADO, NOME_CONDADO
from pipeline.connectors.early_vote.nc.historico import ler_historico
from pipeline.connectors.early_vote.nc.recenseamento import (
    COLUNAS_ATUAL,
    COLUNAS_RETRATO,
    anos_nascimento,
    corrigir_idade,
    ler_ficheiro_eleitores,
    ler_retrato,
    recenseados_atuais,
)


def _tsv(colunas: tuple[str, ...], linhas: list[dict[str, str]], extra: str = "last_name") -> str:
    cabecalho = [*colunas, extra]
    corpo = ["\t".join(f'"{linha.get(c, "")}"' for c in cabecalho) for linha in linhas]
    return "\n".join(["\t".join(f'"{c}"' for c in cabecalho), *corpo]) + "\n"


def test_ficheiro_de_eleitores_atual(tmp_path: Path) -> None:
    base = {
        "county_desc": "WAKE",
        "party_cd": "UNA",
        "race_code": "A",
        "ethnic_code": "HL",
        "gender_code": "M",
        "registr_dt": "01/05/2024",
        "cong_dist_abbrv": "13",
        "last_name": "FICTICIO",
    }
    linhas = [
        {**base, "ncid": "A1", "status_cd": "A", "birth_year": "2000"},
        {**base, "ncid": "A2", "status_cd": "I", "birth_year": "1950"},
        {**base, "ncid": "A3", "status_cd": "R", "birth_year": "1940"},
        {**base, "ncid": "A4", "status_cd": "D", "birth_year": "1990"},
    ]
    caminho = tmp_path / "ncvoter.txt"
    caminho.write_text(_tsv(COLUNAS_ATUAL, linhas), encoding="utf-8")
    eleitores = ler_ficheiro_eleitores(caminho)
    assert "last_name" not in eleitores.columns
    recenseados = recenseados_atuais(eleitores, 2026)
    assert recenseados["ncid"].to_list() == ["A1", "A2"]
    assert recenseados["idade"].to_list() == [26, 76]
    linha = recenseados.row(0, named=True)
    assert linha["partido"] == "nao_afiliado"
    assert linha["raca"] == "asiatica"
    assert linha["etnia"] == "hispanica"
    assert linha["distrito"] == 13
    assert linha["data_registo"] == date(2024, 1, 5)
    # Os removidos ficam disponíveis para corrigir idades de anos anteriores.
    assert set(anos_nascimento(eleitores)["ncid"]) == {"A1", "A2", "A3", "A4"}


def test_retrato_utf16_com_datas_iso_e_correcao_da_idade(tmp_path: Path) -> None:
    base = {
        "county_desc": "DURHAM",
        "party_cd": "DEM",
        "race_code": "B",
        "ethnic_code": "NL",
        "sex_code": "F",
        "cong_dist_abbrv": "04    ",
    }
    linhas = [
        {**base, "ncid": "R1", "status_cd": "A ", "age": "29", "registr_dt": "2010-03-01"},
        {**base, "ncid": "R2", "status_cd": "R ", "age": "80", "registr_dt": "1990-01-01"},
        {**base, "ncid": "R3", "status_cd": "I ", "age": "64", "registr_dt": "xx/xx/xxxx"},
    ]
    arquivo = tmp_path / "VR_Snapshot_20221108.zip"
    with zipfile.ZipFile(arquivo, "w") as z:
        z.writestr("snap.txt", _tsv(COLUNAS_RETRATO, linhas).encode("utf-16"))
    retrato = ler_retrato(arquivo).sort("ncid")
    assert retrato["ncid"].to_list() == ["R1", "R3"]
    assert retrato["data_registo"].to_list() == [date(2010, 3, 1), None]
    assert retrato["distrito"].to_list() == [4, 4]
    nascimentos = pl.DataFrame(
        {"ncid": ["R1"], "ano_nascimento": pl.Series([1992], dtype=pl.Int16)}
    )
    corrigido = corrigir_idade(retrato, nascimentos, 2022).sort("ncid")
    assert corrigido["idade"].to_list() == [30, 64]


def test_historico_fica_com_o_voto_antecipado_quando_ha_dois_registos(tmp_path: Path) -> None:
    linhas = [
        {"ncid": "H1", "election_lbl": "11/08/2022", "voting_method": "ELECTION DAY IN-PERSON"},
        {"ncid": "H1", "election_lbl": "11/08/2022", "voting_method": "ABSENTEE ONESTOP"},
        {"ncid": "H2", "election_lbl": "11/08/2022", "voting_method": "ABSENTEE BY MAIL"},
        {"ncid": "H3", "election_lbl": "11/06/2018", "voting_method": "PROVISIONAL"},
        {"ncid": "H4", "election_lbl": "05/17/2022", "voting_method": "ABSENTEE ONESTOP"},
        {"ncid": "H5", "election_lbl": "11/08/2022", "voting_method": "ELIGIBLE DID NOT VOTE"},
    ]
    caminho = tmp_path / "ncvhis.txt"
    caminho.write_text(_tsv(("ncid", "election_lbl", "voting_method"), linhas), encoding="utf-8")
    historico = ler_historico(caminho, {2018: date(2018, 11, 6), 2022: date(2022, 11, 8)})
    obtido = {(r["ncid"], r["ano"]): r["metodo"] for r in historico.iter_rows(named=True)}
    assert obtido == {
        ("H1", 2022): "antecipado",
        ("H2", 2022): "antecipado",
        ("H3", 2018): "dia_eleicao",
    }


def test_fips_dos_condados_nc_seguem_o_census() -> None:
    """A posição na lista da NCSBE não dá o FIPS: McDowell é 37111 e Macon 37113."""
    assert len(set(FIPS_CONDADO.values())) == len(CONDADOS) == 100
    assert {k: FIPS_CONDADO[k] for k in ("MACON", "MADISON", "MARTIN", "MCDOWELL")} == {
        "MACON": "37113",
        "MADISON": "37115",
        "MARTIN": "37117",
        "MCDOWELL": "37111",
    }
    assert nomes("NC") == NOME_CONDADO
