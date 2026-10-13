"""Endereços das fontes da NCSBE."""

from datetime import date

BASE = "https://s3.amazonaws.com/dl.ncsbe.gov"
NOME_FONTE = "North Carolina State Board of Elections"
LICENCA = "Registo público (N.C. G.S. 132-1, 163-82.10)"


def _carimbo(data_eleicao: date) -> str:
    return data_eleicao.strftime("%Y%m%d")


def url_boletins(data_eleicao: date) -> str:
    c = _carimbo(data_eleicao)
    return f"{BASE}/ENRS/{data_eleicao:%Y_%m_%d}/absentee_{c}.zip"


def url_retrato_recenseamento(data_eleicao: date) -> str:
    return f"{BASE}/data/Snapshots/VR_Snapshot_{_carimbo(data_eleicao)}.zip"


URL_ELEITORES = f"{BASE}/data/ncvoter_Statewide.zip"
URL_HISTORICO = f"{BASE}/data/ncvhis_Statewide.zip"
