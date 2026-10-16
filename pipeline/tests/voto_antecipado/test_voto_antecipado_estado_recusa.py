"""Fonte que recusa o pedido: publica-se a última recolha, com aviso (linhas sintéticas)."""

import dataclasses
import json
from pathlib import Path

import httpx
import pytest

from contratos.estados import CodigoEstado
from pipeline.connectors.early_vote import agregados
from pipeline.jobs import voto_antecipado_estado

ME_2026 = (
    "RES MUNICIPALITY|DES|Voter Record #|P|IB|W-P|CG|SS|SR|DA|CC|Ballot Type|Req Type|Req Date"
    "|Issued Type|Issued Date|Rec Type|Rec Date|Rec Time|DUP|Status|CH|REJ\n"
    "VILA A|O|900000001|D||1-1|2|4|30|5|1|RB|UR|02/25/2026|EL|09/17/2026|||||||\n"
    "VILA A|O|900000002|R||1-1|1|4|30|5|1|RB|VP|10/05/2026|VP|10/05/2026|VP|10/05/2026|10:00 AM"
    "||ACT||\n"
)
URL_ANTERIOR = "https://www.maine.gov/sos/files/11-3-26%20AB%20Voter%20File.txt"


def _recusa(_: httpx.Client) -> str:
    pedido = httpx.Request("GET", "https://www.maine.gov/sos/elections-voting/voter-data")
    raise httpx.HTTPStatusError("403", request=pedido, response=httpx.Response(403))


@pytest.fixture
def maine_bloqueado(monkeypatch: pytest.MonkeyPatch) -> None:
    conector = dataclasses.replace(agregados.CONECTORES[CodigoEstado.ME], url_atual=_recusa)
    monkeypatch.setitem(agregados.CONECTORES, CodigoEstado.ME, conector)


def _copia_anterior(raiz: Path) -> None:
    pasta = raiz / "data" / "brutos" / "me"
    pasta.mkdir(parents=True)
    (pasta / "boletins_2026.txt").write_text(ME_2026, encoding="utf-8")
    meta = {
        "url": URL_ANTERIOR,
        "etag": '"abc"',
        "last_modified": None,
        "obtido_em": "2026-10-15T23:05:17+00:00",
    }
    (pasta / "boletins_2026.txt.meta.json").write_text(json.dumps(meta), encoding="utf-8")


@pytest.mark.usefixtures("maine_bloqueado")
def test_fonte_recusa_publica_a_ultima_recolha_com_aviso(tmp_path: Path) -> None:
    _copia_anterior(tmp_path)
    saida = tmp_path / "me.json"
    voto_antecipado_estado.executar(CodigoEstado.ME, tmp_path, saida, descarregar_=True)

    publicado = json.loads(saida.read_text(encoding="utf-8"))
    assert publicado["dados_ate"] == "2026-10-05"
    assert any(
        "não respondeu ao último pedido" in a and "15/10 às 23:05" in a for a in publicado["avisos"]
    )
    fonte = publicado["metadados"]["fontes"][0]
    assert fonte["url"] == URL_ANTERIOR
    assert fonte["obtida_em"].startswith("2026-10-15T23:05:17")


@pytest.mark.usefixtures("maine_bloqueado")
def test_fonte_recusa_sem_copia_anterior_falha(tmp_path: Path) -> None:
    with pytest.raises(httpx.HTTPStatusError):
        voto_antecipado_estado.executar(
            CodigoEstado.ME, tmp_path, tmp_path / "me.json", descarregar_=True
        )
