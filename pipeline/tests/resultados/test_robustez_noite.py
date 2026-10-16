"""Robustez da recolha da noite eleitoral com falhas injetadas.

Três estados no mesmo ciclo (Florida, Geórgia e Alasca, com excertos reais de 2024), com
as fontes simuladas por ``httpx.MockTransport``: fonte em baixo, resposta vazia, ficheiro
corrompido, 403, 429 seguido de sucesso e um erro inesperado na leitura. Em todos os
casos, os outros estados seguem, o último ficheiro válido fica publicado e nada inválido
é escrito.
"""

import json
import time
from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import httpx
import pytest
from pydantic import ValidationError

from contratos.resultados import ResultadosEstado
from contratos.saude import SaudeRecolha
from pipeline.connectors.results.ak.conector import ConectorAK
from pipeline.connectors.results.comum import ConectorResultados
from pipeline.connectors.results.fl.conector import ConectorFL
from pipeline.connectors.results.ga.conector import ConectorGA
from pipeline.jobs import vigia
from pipeline.jobs.resultados import FALHAS_ALERTA, Recolha, executar

DADOS = Path(__file__).parent / "dados"
DATA = date(2024, 11, 5)
CONECTORES: list[ConectorResultados] = [ConectorFL(), ConectorGA(), ConectorAK()]
FICHEIROS = {
    "flelectionfiles.floridados.gov": (DADOS / "fl" / "resultados.txt").read_bytes(),
    "results.sos.ga.gov": (DADOS / "ga" / "estado.json").read_bytes(),
    "www.elections.alaska.gov": (DADOS / "ak" / "seccoes.csv").read_bytes(),
}

Comportamento = Callable[[httpx.Request], httpx.Response]


def _normal(pedido: httpx.Request) -> httpx.Response:
    return httpx.Response(200, content=FICHEIROS[pedido.url.host])


class Fontes:
    """Servidor simulado: cada anfitrião responde normalmente, salvo indicação."""

    def __init__(self) -> None:
        self.comportamento: dict[str, Comportamento] = {}
        self.pedidos: list[str] = []

    def __call__(self, pedido: httpx.Request) -> httpx.Response:
        self.pedidos.append(pedido.url.host)
        return self.comportamento.get(pedido.url.host, _normal)(pedido)


@pytest.fixture
def fontes() -> Fontes:
    return Fontes()


@pytest.fixture
def recolha(fontes: Fontes, tmp_path: Path) -> Recolha:
    return Recolha(
        DATA,
        tmp_path / "pub",
        tmp_path / "brutos",
        cliente=httpx.Client(transport=httpx.MockTransport(fontes)),
    )


def _publicados(recolha: Recolha) -> set[str]:
    return {p.name for p in recolha.saida.glob("*.json")}


def test_um_estado_corrompido_ou_bloqueado_nao_para_os_outros(
    fontes: Fontes, recolha: Recolha
) -> None:
    fontes.comportamento["results.sos.ga.gov"] = lambda _p: httpx.Response(
        200, content=b'{"ballotItems": [ {"truncado'
    )
    fontes.comportamento["www.elections.alaska.gov"] = lambda _p: httpx.Response(403)
    alterados = recolha.ciclo(CONECTORES)
    assert {p.name for p in alterados} == {"fl.json", "nacional.json", "parciais.json"}
    assert _publicados(recolha) == {"fl.json", "nacional.json", "parciais.json"}
    saude = recolha.saude().estados
    assert saude["FL"].falhas_seguidas == 0
    assert saude["GA"].falhas_seguidas == 1
    assert "403" in (saude["AK"].ultimo_erro or "")


def test_429_com_retry_after_volta_a_tentar_e_publica(fontes: Fontes, recolha: Recolha) -> None:
    respostas = iter(
        [httpx.Response(429, headers={"Retry-After": "0"}), None]  # depois, normal
    )

    def limitado(pedido: httpx.Request) -> httpx.Response:
        resposta = next(respostas, None)
        return resposta or _normal(pedido)

    fontes.comportamento["www.elections.alaska.gov"] = limitado
    recolha.ciclo(CONECTORES)
    assert "ak.json" in _publicados(recolha)
    assert fontes.pedidos.count("www.elections.alaska.gov") == 2


def test_falha_depois_de_um_sucesso_mantem_o_ultimo_ficheiro_valido(
    fontes: Fontes, recolha: Recolha
) -> None:
    recolha.ciclo(CONECTORES)
    antes = (recolha.saida / "fl.json").read_text(encoding="utf-8")
    ResultadosEstado.model_validate_json(antes)

    # Resposta vazia (200 sem conteúdo, com outro ETag), depois a fonte em baixo.
    fontes.comportamento["flelectionfiles.floridados.gov"] = lambda _p: httpx.Response(
        200, content=b"", headers={"ETag": '"vazio"'}
    )
    assert "fl.json" not in {p.name for p in recolha.ciclo(CONECTORES)}

    def em_baixo(pedido: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("ligação recusada", request=pedido)

    fontes.comportamento["flelectionfiles.floridados.gov"] = em_baixo
    recolha.ciclo(CONECTORES)
    assert (recolha.saida / "fl.json").read_text(encoding="utf-8") == antes
    estado_fl = recolha.estados[ConectorFL().estado]
    assert estado_fl.falhas_seguidas == 2
    assert estado_fl.ultima_alteracao is not None


def test_erro_inesperado_na_leitura_fica_isolado(
    recolha: Recolha, monkeypatch: pytest.MonkeyPatch
) -> None:
    def rebenta(_self: object, _pasta: Path, _data: date) -> object:
        msg = "erro que nenhum conector previa"
        raise KeyError(msg)

    monkeypatch.setattr(ConectorGA, "ler", rebenta)
    recolha.ciclo(CONECTORES)
    assert {"fl.json", "ak.json"} <= _publicados(recolha)
    assert "ga.json" not in _publicados(recolha)
    assert "KeyError" in str(recolha.estados[ConectorGA().estado].ultimo_erro)


def test_alerta_depois_de_falhas_seguidas_e_vigia_avisa(
    fontes: Fontes, recolha: Recolha, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(time, "sleep", lambda _s: None)
    fontes.comportamento["results.sos.ga.gov"] = lambda _p: httpx.Response(503)
    executar(recolha, CONECTORES, intervalo=0, ciclos=FALHAS_ALERTA)
    saude = json.loads((recolha.saida / "saude.json").read_text(encoding="utf-8"))
    assert saude["estados"]["GA"]["alerta"].startswith(f"{FALHAS_ALERTA} falhas seguidas")
    assert saude["estados"]["FL"]["alerta"] is None
    agora = datetime.fromisoformat(saude["metadados"]["gerado_em"])
    lista = vigia.alertas(saude, agora, maximo_minutos=12)
    assert len(lista) == 1
    assert lista[0].startswith("GA:")


def test_vigia_avisa_quando_a_propria_recolha_para() -> None:
    gerado = datetime(2026, 11, 4, 2, 0, tzinfo=UTC)
    saude = {"gerado_em": gerado.isoformat(), "estados": {"NC": {"alerta": None}}}
    assert vigia.alertas(saude, gerado + timedelta(minutes=5), 12) == []
    lista = vigia.alertas(saude, gerado + timedelta(minutes=20), 12)
    assert lista
    assert lista[0].startswith("A recolha parou")


def test_fonte_parada_com_a_contagem_por_acabar_da_alerta(recolha: Recolha) -> None:
    recolha.ciclo(CONECTORES)
    estado = recolha.estados[ConectorAK().estado]
    agora = datetime.now(UTC)
    estado.ultima_alteracao = agora - timedelta(hours=1)
    # O excerto do Alasca tem as secções todas apuradas: parar aí é normal.
    assert estado.apurado()
    assert estado.alerta(agora) is None


def test_vigia_nao_avisa_depois_de_tudo_apurado() -> None:
    gerado = datetime(2026, 11, 4, 9, 0, tzinfo=UTC)
    saude = {"gerado_em": gerado.isoformat(), "estados": {"NC": {"apurado": True}}}
    assert vigia.alertas(saude, gerado + timedelta(hours=3), 12) == []


def test_fonte_lenta_nao_atrasa_os_outros_estados(fontes: Fontes, recolha: Recolha) -> None:
    def lenta(pedido: httpx.Request) -> httpx.Response:
        time.sleep(1.0)
        return _normal(pedido)

    fontes.comportamento["results.sos.ga.gov"] = lenta
    recolha.orcamento = 0.2
    inicio = time.monotonic()
    alterados = {p.name for p in recolha.ciclo(CONECTORES)}
    assert time.monotonic() - inicio < 0.9
    assert {"fl.json", "ak.json", "parciais.json"} <= alterados
    assert "ga.json" not in alterados
    assert recolha.em_curso() == {ConectorGA().estado}
    # Enquanto está em curso, a Geórgia não é lançada outra vez.
    recolha.ciclo(CONECTORES)
    assert fontes.pedidos.count("results.sos.ga.gov") == 1
    # Acaba em fundo e entra no ciclo seguinte.
    time.sleep(1.0)
    assert "ga.json" in {p.name for p in recolha.ciclo(CONECTORES)}


def test_retry_after_longo_poe_o_estado_em_pausa(
    fontes: Fontes, recolha: Recolha, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(time, "sleep", lambda _s: None)
    fontes.comportamento["www.elections.alaska.gov"] = lambda _p: httpx.Response(
        429, headers={"Retry-After": "120"}
    )
    recolha.ciclo(CONECTORES)
    pedidos = fontes.pedidos.count("www.elections.alaska.gov")
    estado = recolha.estados[ConectorAK().estado]
    assert estado.nao_antes is not None
    assert estado.nao_antes > datetime.now(UTC) + timedelta(seconds=100)
    recolha.ciclo(CONECTORES)
    assert fontes.pedidos.count("www.elections.alaska.gov") == pedidos
    assert estado.falhas_seguidas == 1


def test_leitura_falhada_volta_a_descarregar_sem_pedido_condicional(
    fontes: Fontes, recolha: Recolha
) -> None:
    condicionais: list[str | None] = []

    def truncado(pedido: httpx.Request) -> httpx.Response:
        condicionais.append(pedido.headers.get("If-None-Match"))
        if pedido.headers.get("If-None-Match") == '"v1"':
            return httpx.Response(304)
        return httpx.Response(200, content=b'{"ballotItems": [ {"trunc', headers={"ETag": '"v1"'})

    fontes.comportamento["results.sos.ga.gov"] = truncado
    recolha.ciclo(CONECTORES)
    recolha.ciclo(CONECTORES)
    # Sem o ETag guardado, o 304 não pode fazer passar por bom um ficheiro que não se leu.
    assert condicionais == [None, None]
    assert recolha.estados[ConectorGA().estado].falhas_seguidas == 2


def test_saude_segue_o_contrato_e_o_vigia_le_o_formato_antigo() -> None:
    gerado = datetime(2026, 11, 4, 2, 0, tzinfo=UTC)
    saude = SaudeRecolha.model_validate(
        {
            "metadados": {
                "gerado_em": gerado.isoformat(),
                "fontes": [{"nome": "Recolha", "url": "https://exemplo.org/", "obtida_em": gerado}],
            },
            "data_eleicao": "2026-11-03",
            "estados": {
                "TX-manual": {
                    "ultimo_sucesso": None,
                    "ultima_alteracao": None,
                    "falhas_seguidas": 0,
                    "ultimo_erro": None,
                    "apurado": False,
                    "alerta": None,
                }
            },
        }
    )
    novo = saude.model_dump(mode="json")
    assert vigia.alertas(novo, gerado + timedelta(minutes=5), 12) == []
    antigo = {"gerado_em": gerado.isoformat(), "estados": {}}
    assert vigia.alertas(antigo, gerado + timedelta(minutes=5), 12) == [
        "A recolha não tem nenhum estado."
    ]
    with pytest.raises(ValidationError):
        SaudeRecolha.model_validate({**novo, "estados": {"Texas": novo["estados"]["TX-manual"]}})
