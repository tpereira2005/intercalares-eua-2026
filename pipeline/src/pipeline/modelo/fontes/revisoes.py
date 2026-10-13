"""Histórico de revisões de uma página da Wikipedia (para reconstruir séries passadas).

A lista de revisões vem da API (``action=query&prop=revisions``), com o mesmo User-Agent,
pausa entre pedidos e recuo exponencial nos 429 que ``wikipedia.obter``. Cada página da
lista fica em cache: uma lista já obtida nunca volta a ser pedida.
"""

import json
import time
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import httpx

from pipeline.comum.erros import ErroDescarga
from pipeline.modelo.fontes import wikipedia

URL_API = "https://en.wikipedia.org/w/api.php"


@dataclass(frozen=True, slots=True)
class Revisao:
    oldid: int
    instante: datetime


def _pedido(params: dict[str, str], cliente: httpx.Client) -> dict[str, object]:
    for tentativa in range(wikipedia.TENTATIVAS):
        try:
            resposta = cliente.get(URL_API, params=params)
        except httpx.HTTPError:
            time.sleep(wikipedia.PAUSA_SEGUNDOS * 4 * 2**tentativa)
            continue
        if resposta.status_code == 200:
            time.sleep(wikipedia.PAUSA_SEGUNDOS)
            dados: dict[str, object] = resposta.json()
            return dados
        time.sleep(wikipedia.espera(resposta, tentativa))
    raise ErroDescarga(f"Não foi possível listar as revisões ({params.get('titles')})")


def listar(
    titulo: str, inicio: date, fim: date, pasta: Path, cliente: httpx.Client
) -> list[Revisao]:
    """Revisões de ``titulo`` entre ``inicio`` e ``fim`` (inclusive), da mais antiga à mais
    recente, mais a última revisão anterior a ``inicio`` (o estado da página nesse dia)."""
    pasta.mkdir(parents=True, exist_ok=True)
    base = {
        "action": "query",
        "prop": "revisions",
        "titles": titulo,
        "rvprop": "ids|timestamp",
        "rvlimit": "500",
        "format": "json",
        "formatversion": "2",
    }
    antes = {**base, "rvlimit": "1", "rvdir": "older", "rvstart": f"{inicio.isoformat()}T00:00:00Z"}
    paginas = [_em_cache(pasta / f"antes-{inicio}.json", antes, cliente)]
    continuar: str | None = None
    n = 0
    while True:
        params = {
            **base,
            "rvdir": "newer",
            "rvstart": f"{inicio.isoformat()}T00:00:00Z",
            "rvend": f"{(fim + timedelta(days=1)).isoformat()}T00:00:00Z",
        }
        if continuar:
            params["rvcontinue"] = continuar
        pagina = _em_cache(pasta / f"{inicio}-{fim}-{n}.json", params, cliente)
        paginas.append(pagina)
        seguinte = pagina.get("continue")
        if not isinstance(seguinte, dict) or "rvcontinue" not in seguinte:
            break
        continuar = str(seguinte["rvcontinue"])
        n += 1
    revisoes: dict[int, Revisao] = {}
    for pagina in paginas:
        for r in _revisoes(pagina):
            revisoes[r.oldid] = r
    return sorted(revisoes.values(), key=lambda r: r.instante)


def _em_cache(caminho: Path, params: dict[str, str], cliente: httpx.Client) -> dict[str, object]:
    if caminho.exists():
        dados: dict[str, object] = json.loads(caminho.read_text(encoding="utf-8"))
        return dados
    novo = _pedido(params, cliente)
    caminho.write_text(json.dumps(novo), encoding="utf-8")
    return novo


def _revisoes(pagina: dict[str, object]) -> list[Revisao]:
    consulta = pagina.get("query")
    if not isinstance(consulta, dict):
        return []
    resultado: list[Revisao] = []
    for p in consulta.get("pages", []):
        for r in p.get("revisions", []):
            instante = datetime.fromisoformat(r["timestamp"].replace("Z", "+00:00"))
            resultado.append(Revisao(int(r["revid"]), instante))
    return resultado


def ultima_por_dia(revisoes: list[Revisao], inicio: date, fim: date) -> dict[date, Revisao]:
    """Para cada dia, a última revisão feita até ao fim desse dia (UTC)."""
    resultado: dict[date, Revisao] = {}
    ordenadas = sorted(revisoes, key=lambda r: r.instante)
    i = 0
    atual: Revisao | None = None
    dia = inicio
    while dia <= fim:
        limite = datetime.combine(dia + timedelta(days=1), datetime.min.time(), tzinfo=UTC)
        while i < len(ordenadas) and ordenadas[i].instante < limite:
            atual = ordenadas[i]
            i += 1
        if atual is not None:
            resultado[dia] = atual
        dia += timedelta(days=1)
    return resultado
