from pathlib import Path

import httpx
import pytest

from pipeline.comum.descarga import USER_AGENT, descarregar, obter_texto
from pipeline.comum.erros import ErroBloqueio, ErroDescarga


def test_pedido_condicional_reutiliza_copia_local(tmp_path: Path) -> None:
    pedidos: list[httpx.Request] = []

    def responder(pedido: httpx.Request) -> httpx.Response:
        pedidos.append(pedido)
        if pedido.headers.get("if-none-match") == '"v1"':
            return httpx.Response(304)
        return httpx.Response(
            200, content=b"dados", headers={"ETag": '"v1"', "Last-Modified": "Mon, 12 Oct 2026"}
        )

    destino = tmp_path / "f.zip"
    with httpx.Client(transport=httpx.MockTransport(responder)) as cliente:
        primeira = descarregar("https://exemplo.org/f.zip", destino, cliente=cliente)
        segunda = descarregar("https://exemplo.org/f.zip", destino, cliente=cliente)
    assert primeira.alterado
    assert not segunda.alterado
    assert destino.read_bytes() == b"dados"
    assert pedidos[0].headers["user-agent"] == USER_AGENT
    assert pedidos[1].headers["if-modified-since"] == "Mon, 12 Oct 2026"


def test_tenta_de_novo_em_erros_do_servidor(tmp_path: Path) -> None:
    respostas = iter([httpx.Response(503), httpx.Response(200, content=b"ok")])
    with httpx.Client(transport=httpx.MockTransport(lambda _p: next(respostas))) as cliente:
        resultado = descarregar(
            "https://exemplo.org/g.zip", tmp_path / "g.zip", cliente=cliente, espera_inicial=0
        )
    assert resultado.alterado


def test_nao_insiste_em_erros_do_cliente_e_nao_deixa_ficheiro(tmp_path: Path) -> None:
    with (
        httpx.Client(transport=httpx.MockTransport(lambda _p: httpx.Response(404))) as cliente,
        pytest.raises(ErroDescarga),
    ):
        descarregar("https://exemplo.org/h.zip", tmp_path / "h.zip", cliente=cliente)
    assert not (tmp_path / "h.zip").exists()


def test_desafio_do_waf_e_um_bloqueio_e_nao_um_ficheiro_vazio(tmp_path: Path) -> None:
    """O AWS WAF responde 202 com corpo vazio; nunca deve passar por um ficheiro válido."""
    desafio = httpx.Response(202, headers={"x-amzn-waf-action": "challenge"})
    with (
        httpx.Client(transport=httpx.MockTransport(lambda _p: desafio)) as cliente,
        pytest.raises(ErroBloqueio, match="desafio anti-robô"),
    ):
        descarregar("https://exemplo.org/w.zip", tmp_path / "w.zip", cliente=cliente)
    assert not (tmp_path / "w.zip").exists()


@pytest.mark.parametrize(
    ("resposta", "erro"),
    [
        (httpx.Response(202, headers={"x-amzn-waf-action": "challenge"}), ErroBloqueio),
        (httpx.Response(403, headers={"cf-mitigated": "challenge"}), ErroBloqueio),
        (httpx.Response(202), ErroDescarga),
    ],
)
def test_obter_texto_recusa_desafios_e_respostas_vazias(
    resposta: httpx.Response, erro: type[Exception]
) -> None:
    with (
        httpx.Client(transport=httpx.MockTransport(lambda _p: resposta)) as cliente,
        pytest.raises(erro),
    ):
        obter_texto(cliente, "https://exemplo.org/current_ver.txt")
