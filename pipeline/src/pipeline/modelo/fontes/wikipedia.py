"""Descarga de páginas da Wikipedia em wikitexto, com cache local e respeito pelos limites.

Usamos ``index.php?action=raw`` (sem a API), um User-Agent identificado e uma pausa entre
pedidos. Uma página já descarregada não volta a ser pedida, a menos que se peça
``atualizar=True``; as revisões antigas (``oldid``) nunca mudam e ficam sempre em cache.
"""

import time
from pathlib import Path
from urllib.parse import quote

import httpx

from pipeline.comum.erros import ErroDescarga

USER_AGENT = (
    "EscrutinioBot/0.1 (+https://github.com/tpereira2005/intercalares-eua-2026; "
    "non-commercial election forecast)"
)
URL_BASE = "https://en.wikipedia.org/w/index.php"
PAUSA_SEGUNDOS = 4.0
TENTATIVAS = 6


class PaginaInexistente(ErroDescarga):
    """A página pedida não existe na Wikipedia (404)."""


def _nome_ficheiro(titulo: str, oldid: int | None) -> str:
    base = titulo.replace(" ", "_").replace("/", "_")
    return f"{base}@{oldid}.wiki" if oldid else f"{base}.wiki"


def obter(
    titulo: str,
    pasta: Path,
    *,
    oldid: int | None = None,
    atualizar: bool = False,
    cliente: httpx.Client | None = None,
) -> str:
    """Devolve o wikitexto de ``titulo`` (ou da revisão ``oldid``), usando a cache em ``pasta``."""
    pasta.mkdir(parents=True, exist_ok=True)
    caminho = pasta / _nome_ficheiro(titulo, oldid)
    if caminho.exists() and (oldid is not None or not atualizar):
        return caminho.read_text(encoding="utf-8")
    params = f"oldid={oldid}" if oldid else f"title={quote(titulo.replace(' ', '_'))}"
    url = f"{URL_BASE}?{params}&action=raw"
    proprio = cliente is None
    http = cliente or httpx.Client(headers={"User-Agent": USER_AGENT}, timeout=60.0)
    try:
        for tentativa in range(TENTATIVAS):
            try:
                resposta = http.get(url, follow_redirects=True)
            except httpx.HTTPError:
                time.sleep(PAUSA_SEGUNDOS * (tentativa + 1) * 3)
                continue
            if resposta.status_code == 404:
                raise PaginaInexistente(titulo)
            if resposta.status_code == 200:
                caminho.write_text(resposta.text, encoding="utf-8")
                time.sleep(PAUSA_SEGUNDOS)
                return resposta.text
            # 429 e 5xx: a Wikipedia pede para abrandar.
            time.sleep(PAUSA_SEGUNDOS * (tentativa + 1) * 4)
        raise ErroDescarga(f"Não foi possível obter {titulo!r} da Wikipedia")
    finally:
        if proprio:
            http.close()
