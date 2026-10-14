"""Leitor comum da API JSON da Enhanced Voting, usada pela Geórgia e pela Virgínia.

O ficheiro do estado (``.../api/elections/<Estado>/<eleição>/data``) traz todas as corridas
com os votos por candidato, o apuramento por unidade (condados, na Geórgia; condados e
cidades independentes, na Virgínia) e, por candidato, os votos por tipo (``groupResults``).
Os ficheiros por unidade, que a API também serve, não os pedimos a cada ciclo.
Antes de a página da eleição existir, a API responde 204 sem conteúdo.
"""

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

import polars as pl

from contratos.estados import CodigoEstado
from pipeline.comum.erros import ErroFormatoFonte
from pipeline.connectors.results.comum import identificar_corrida, modalidade, partido
from pipeline.transform.resultados.montar import (
    COLUNAS_MODALIDADES,
    COLUNAS_UNIDADES,
    COLUNAS_VOTOS,
    DescricaoCorrida,
    Leitura,
)

FICHEIRO = "estado.json"
_SUFIXOS = re.compile(r"(\s*\((I|Dem|Rep|Lib|Ind|Grn|Green)\))+\s*$", re.IGNORECASE)


def texto(valor: Any) -> str:
    """Os textos vêm como ``[{"languageId": "en", "text": ...}]``."""
    if isinstance(valor, list) and valor and isinstance(valor[0], dict):
        return str(valor[0].get("text", ""))
    return str(valor or "")


def ler_estado(pasta: Path, estado: CodigoEstado) -> Leitura:
    """Lê ``estado.json`` (Senado, Câmara e governador) sem rede."""
    caminho = pasta / FICHEIRO
    conteudo = caminho.read_text(encoding="utf-8-sig")
    if not conteudo.strip():
        msg = "A página da eleição ainda não existe (resposta vazia)"
        raise ErroFormatoFonte(msg)
    try:
        dados = json.loads(conteudo)
        itens = dados["ballotItems"]
        atualizado = dados["election"].get("lastUpdated")
    except (json.JSONDecodeError, KeyError, TypeError) as erro:
        msg = f"{caminho.name}: formato inesperado"
        raise ErroFormatoFonte(msg) from erro
    corridas: list[DescricaoCorrida] = []
    votos: list[tuple[object, ...]] = []
    unidades: list[tuple[object, ...]] = []
    modalidades: list[tuple[object, ...]] = []
    for item in itens:
        desc = identificar_corrida(estado, texto(item.get("name")))
        if desc is None or item.get("contestType") != "Candidate":
            continue
        corridas.append(desc)
        apuramento = item.get("reportingStatus") or {}
        if "reportingUnits" in apuramento and "totalUnits" in apuramento:
            unidades.append(
                (desc.id, "estado", None, int(apuramento["reportingUnits"]),
                 int(apuramento["totalUnits"]))
            )  # fmt: skip
        for opcao in item["summaryResults"]["ballotOptions"]:
            rotulo = (opcao.get("party") or {}).get("abbreviation") or ""
            nome = _SUFIXOS.sub("", texto(opcao.get("name"))).strip()
            if opcao.get("isWriteIn"):
                rotulo = rotulo or "Write-in"
            cand = str(opcao.get("nativeId") or opcao["id"])
            votos.append(
                (desc.id, cand, nome, partido(rotulo),
                 rotulo or None, "estado", None, int(opcao.get("voteCount") or 0))
            )  # fmt: skip
            modalidades.extend(
                (desc.id, cand, "estado", None, modalidade(texto(g.get("groupName"))),
                 int(g.get("voteCount") or 0))
                for g in opcao.get("groupResults") or ()
            )  # fmt: skip
    return Leitura(
        corridas=tuple({d.id: d for d in corridas}.values()),
        votos=pl.DataFrame(votos, schema=COLUNAS_VOTOS, orient="row"),
        unidades=pl.DataFrame(unidades, schema=COLUNAS_UNIDADES, orient="row"),
        tipo_unidade="condado",
        modalidades=pl.DataFrame(modalidades, schema=COLUNAS_MODALIDADES, orient="row"),
        atualizado_fonte=datetime.fromisoformat(atualizado) if atualizado else None,
    )
