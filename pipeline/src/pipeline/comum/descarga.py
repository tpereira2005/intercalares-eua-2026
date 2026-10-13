"""Descarga de ficheiros das fontes oficiais com pedidos condicionais.

Cada ficheiro descarregado fica acompanhado de um ``.meta.json`` com o ETag, o
Last-Modified e o momento da recolha. Na descarga seguinte enviamos ``If-None-Match`` e
``If-Modified-Since``: se a fonte responder 304, reutilizamos a cópia local e não
sobrecarregamos os servidores estaduais.
"""

import json
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import httpx

from pipeline.comum.erros import ErroBloqueio, ErroDescarga

USER_AGENT = "intercalares-eua-2026/0.1 (+https://github.com/tpereira2005/intercalares-eua-2026)"
TAMANHO_BLOCO = 1 << 20


def verificar_resposta(resposta: httpx.Response) -> None:
    """Falha com ``ErroBloqueio`` quando a resposta é um desafio anti-robô e com
    ``httpx.HTTPStatusError`` nos outros erros HTTP.

    O AWS WAF responde ao desafio com ``202 Accepted``, corpo vazio e o cabeçalho
    ``x-amzn-waf-action: challenge``; o Cloudflare com ``cf-mitigated: challenge``. Sem esta
    verificação, um 202 vazio passava por um ficheiro válido sem conteúdo.
    """
    waf = resposta.headers.get("x-amzn-waf-action") or resposta.headers.get("cf-mitigated")
    if waf:
        msg = (
            f"{resposta.url.host} recusou o pedido com um desafio anti-robô ({waf}, "
            f"HTTP {resposta.status_code}); não o contornamos"
        )
        raise ErroBloqueio(msg)
    resposta.raise_for_status()
    if resposta.status_code == httpx.codes.ACCEPTED:
        msg = f"{resposta.url}: HTTP 202 sem conteúdo (pedido aceite mas não servido)"
        raise ErroDescarga(msg)


def obter_texto(cliente: httpx.Client, url: str) -> str:
    """Pede um URL pequeno e devolve o texto, com as verificações de ``verificar_resposta``."""
    resposta = cliente.get(url)
    verificar_resposta(resposta)
    return resposta.text


@dataclass(frozen=True, slots=True)
class Descarga:
    url: str
    caminho: Path
    alterado: bool
    """``False`` quando a fonte respondeu 304 e reutilizámos a cópia local."""

    etag: str | None
    ultima_modificacao: str | None
    obtido_em: datetime


def _ler_meta(caminho: Path) -> dict[str, str]:
    meta = caminho.with_name(caminho.name + ".meta.json")
    if not (meta.exists() and caminho.exists()):
        return {}
    dados = json.loads(meta.read_text(encoding="utf-8"))
    return {k: str(v) for k, v in dados.items() if v is not None}


def _escrever_meta(caminho: Path, descarga: Descarga) -> None:
    meta = caminho.with_name(caminho.name + ".meta.json")
    meta.write_text(
        json.dumps(
            {
                "url": descarga.url,
                "etag": descarga.etag,
                "last_modified": descarga.ultima_modificacao,
                "obtido_em": descarga.obtido_em.isoformat(),
            },
            indent=2,
        ),
        encoding="utf-8",
    )


def descarregar(
    url: str,
    destino: Path,
    *,
    cliente: httpx.Client | None = None,
    tentativas: int = 4,
    espera_inicial: float = 2.0,
) -> Descarga:
    """Descarrega ``url`` para ``destino`` com pedido condicional e novas tentativas.

    O ficheiro é escrito primeiro num temporário e só substitui o anterior quando a
    descarga termina, para nunca deixar um ficheiro truncado no lugar de um válido.
    """
    destino.parent.mkdir(parents=True, exist_ok=True)
    meta = _ler_meta(destino)
    cabecalhos = {"User-Agent": USER_AGENT}
    if etag := meta.get("etag"):
        cabecalhos["If-None-Match"] = etag
    if modificado := meta.get("last_modified"):
        cabecalhos["If-Modified-Since"] = modificado

    proprio = cliente is None
    http = cliente or httpx.Client(timeout=httpx.Timeout(60.0, read=300.0), follow_redirects=True)
    try:
        ultimo_erro: Exception | None = None
        for tentativa in range(tentativas):
            try:
                return _uma_descarga(http, url, destino, cabecalhos, meta)
            except (httpx.TransportError, httpx.HTTPStatusError) as erro:
                ultimo_erro = erro
                if isinstance(erro, httpx.HTTPStatusError) and erro.response.status_code < 500:
                    break
                time.sleep(espera_inicial * (2**tentativa))
        msg = f"Falhou a descarga de {url}: {ultimo_erro}"
        raise ErroDescarga(msg) from ultimo_erro
    finally:
        if proprio:
            http.close()


def _uma_descarga(
    http: httpx.Client,
    url: str,
    destino: Path,
    cabecalhos: dict[str, str],
    meta: dict[str, str],
) -> Descarga:
    agora = datetime.now(UTC)
    with http.stream("GET", url, headers=cabecalhos) as resposta:
        if resposta.status_code == httpx.codes.NOT_MODIFIED:
            return Descarga(url, destino, False, meta.get("etag"), meta.get("last_modified"), agora)
        verificar_resposta(resposta)
        temporario = destino.with_name(destino.name + ".parcial")
        with temporario.open("wb") as saida:
            for bloco in resposta.iter_bytes(TAMANHO_BLOCO):
                saida.write(bloco)
        temporario.replace(destino)
        descarga = Descarga(
            url,
            destino,
            True,
            resposta.headers.get("etag"),
            resposta.headers.get("last-modified"),
            agora,
        )
    _escrever_meta(destino, descarga)
    return descarga
