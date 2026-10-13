"""Vigia da noite eleitoral: avisa quando uma fonte ou a própria recolha param.

Uso::

    uv run python -m pipeline.jobs.vigia --saude data/publicado/resultados/saude.json
    uv run python -m pipeline.jobs.vigia --saude https://github.com/<repo>/releases/download/resultados-2026/saude.json

Lê o ``saude.json`` que a recolha (``pipeline.jobs.resultados``) escreve a cada ciclo e
envia para a Release a cada 5 minutos. Há alerta quando:

* o próprio ``saude.json`` tem mais de ``--maximo`` minutos (a recolha parou: job
  cancelado, cadeia de relançamentos interrompida, limite do Actions), salvo se todos os
  estados já estavam apurados (fim normal da noite);
* um estado tem o campo ``alerta`` preenchido (falhas seguidas, ou sem dados novos há
  muito tempo com a contagem por acabar).

Escreve um resumo em Markdown (para o corpo de um issue) e termina com o código 1 quando
há alertas, para o workflow ``vigia-noite.yml`` abrir ou atualizar o issue.
"""

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx

from pipeline.comum.descarga import USER_AGENT

MAXIMO_MINUTOS = 12.0
"""Idade máxima do ``saude.json``: dois envios de 5 minutos e margem."""


def ler(origem: str) -> dict[str, Any]:
    if origem.startswith(("http://", "https://")):
        resposta = httpx.get(
            origem, headers={"User-Agent": USER_AGENT}, follow_redirects=True, timeout=30
        )
        resposta.raise_for_status()
        dados = resposta.json()
    else:
        dados = json.loads(Path(origem).read_text(encoding="utf-8"))
    if not isinstance(dados, dict):
        msg = "saude.json: formato inesperado"
        raise ValueError(msg)
    return dados


def alertas(saude: dict[str, Any], agora: datetime, maximo_minutos: float) -> list[str]:
    resultado: list[str] = []
    try:
        gerado = datetime.fromisoformat(str(saude.get("gerado_em")))
    except ValueError:
        return ["saude.json sem hora de geração válida."]
    idade = (agora - gerado).total_seconds() / 60
    estados = saude.get("estados") or {}
    acabou = bool(estados) and all(
        isinstance(e, dict) and e.get("apurado") for e in estados.values()
    )
    if idade > maximo_minutos and not acabou:
        resultado.append(
            f"A recolha parou: saude.json com {idade:.0f} minutos (máximo {maximo_minutos:.0f})."
        )
    if not estados:
        resultado.append("A recolha não tem nenhum estado.")
    for uf, estado in sorted(estados.items()):
        if isinstance(estado, dict) and estado.get("alerta"):
            resultado.append(f"{uf}: {estado['alerta']}")
    return resultado


def resumo(saude: dict[str, Any], lista: list[str]) -> str:
    linhas = [
        "## Vigia da noite eleitoral",
        "",
        f"saude.json gerado em {saude.get('gerado_em')}.",
        "",
        *(f"- {a}" for a in lista),
        "",
        "| Estado | Último sucesso | Última alteração | Falhas seguidas | Apurado |",
        "| --- | --- | --- | --- | --- |",
    ]
    for uf, e in sorted((saude.get("estados") or {}).items()):
        if isinstance(e, dict):
            linhas.append(
                f"| {uf} | {e.get('ultimo_sucesso') or '·'} | {e.get('ultima_alteracao') or '·'}"
                f" | {e.get('falhas_seguidas', 0)} | {'sim' if e.get('apurado') else 'não'} |"
            )
    linhas += ["", "O que fazer: docs/noite-eleitoral-operacao.md."]
    return "\n".join(linhas)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--saude", required=True, help="ficheiro ou endereço do saude.json")
    parser.add_argument("--maximo", type=float, default=MAXIMO_MINUTOS, help="minutos")
    parser.add_argument("--resumo", type=Path, help="onde escrever o resumo em Markdown")
    args = parser.parse_args(argv)
    try:
        saude = ler(args.saude)
    except (httpx.HTTPError, ValueError, OSError) as erro:
        saude = {"gerado_em": None, "estados": {}}
        lista = [f"Não consegui ler o saude.json ({erro}): a recolha não está a publicar."]
    else:
        lista = alertas(saude, datetime.now(UTC), args.maximo)
    texto = resumo(saude, lista)
    if args.resumo:
        args.resumo.write_text(texto, encoding="utf-8")
    sys.stdout.write(texto + "\n")
    return 1 if lista else 0


if __name__ == "__main__":
    raise SystemExit(main())
