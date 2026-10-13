"""Conector de resultados da Geórgia.

Desde 2024 a Geórgia publica os resultados numa API JSON (Enhanced Voting). O ficheiro do
estado traz todas as corridas com os votos por candidato e os condados apurados; os
condados têm ficheiros próprios, que não pedimos a cada ciclo (seriam 159 pedidos).
As eleições têm identificadores legíveis (``2022NovGen``, ``2024NovGen``); antes de a
página da eleição existir, a API responde 204 sem conteúdo.
"""

import json
import re
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any

import polars as pl

from contratos.estados import CodigoEstado
from pipeline.comum.erros import ErroFormatoFonte
from pipeline.connectors.results.comum import (
    ObterTexto,
    Pedido,
    identificar_corrida,
    modalidade,
    partido,
)
from pipeline.transform.resultados.montar import (
    COLUNAS_MODALIDADES,
    COLUNAS_UNIDADES,
    COLUNAS_VOTOS,
    DescricaoCorrida,
    Leitura,
)

URL = "https://results.sos.ga.gov/results/public/api/elections/Georgia/{eleicao}/data"
FICHEIRO = "estado.json"
_SUFIXOS = re.compile(r"(\s*\((I|Dem|Rep|Lib|Ind|Grn|Green)\))+\s*$", re.IGNORECASE)


def identificador(data: date) -> str:
    return f"{data.year}{data:%b}Gen"


def _texto(valor: Any) -> str:
    """Os textos vêm como ``[{"languageId": "en", "text": ...}]``."""
    if isinstance(valor, list) and valor and isinstance(valor[0], dict):
        return str(valor[0].get("text", ""))
    return str(valor or "")


@dataclass(frozen=True, slots=True)
class ConectorGA:
    estado: CodigoEstado = CodigoEstado.GA
    nome_fonte: str = "Georgia Secretary of State, Election Results"
    licenca: str | None = "Registo público (O.C.G.A. 50-18-70)"

    def pedidos(self, data: date, obter: ObterTexto) -> list[Pedido]:
        del obter
        return [Pedido(URL.format(eleicao=identificador(data)), FICHEIRO)]

    def ler(self, pasta: Path, data: date) -> Leitura:
        del data
        caminho = pasta / FICHEIRO
        texto = caminho.read_text(encoding="utf-8-sig")
        if not texto.strip():
            msg = "A página da eleição ainda não existe (resposta vazia)"
            raise ErroFormatoFonte(msg)
        try:
            dados = json.loads(texto)
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
            desc = identificar_corrida(self.estado, _texto(item.get("name")))
            if desc is None or item.get("contestType") != "Candidate":
                continue
            corridas.append(desc)
            estado = item.get("reportingStatus") or {}
            if "reportingUnits" in estado and "totalUnits" in estado:
                unidades.append(
                    (desc.id, "estado", None, int(estado["reportingUnits"]),
                     int(estado["totalUnits"]))
                )  # fmt: skip
            for opcao in item["summaryResults"]["ballotOptions"]:
                rotulo = (opcao.get("party") or {}).get("abbreviation") or ""
                nome = _SUFIXOS.sub("", _texto(opcao.get("name"))).strip()
                if opcao.get("isWriteIn"):
                    rotulo = rotulo or "Write-in"
                cand = str(opcao.get("nativeId") or opcao["id"])
                votos.append(
                    (desc.id, cand, nome, partido(rotulo),
                     rotulo or None, "estado", None, int(opcao.get("voteCount") or 0))
                )  # fmt: skip
                modalidades.extend(
                    (desc.id, cand, "estado", None, modalidade(_texto(g.get("groupName"))),
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
