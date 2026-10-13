from pathlib import Path

import httpx
import pytest

from pipeline.comum.descarga import USER_AGENT, descarregar
from pipeline.comum.erros import ErroDescarga


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
