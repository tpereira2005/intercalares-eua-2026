"""Condado de Harris (Texas): resultados da noite eleitoral do Harris County Clerk.

O site de resultados ao vivo (app.harrisvotes.com) lê um JSON público por eleição,
``appfiles.harrisvotes.com/harrisvotes/prd/Data/<código>/resultsbyballot.json``, onde o
código é o mês e o ano (``1124`` para novembro de 2024). Cada corrida traz os candidatos
com o partido entre parênteses, os votos por correspondência (``ab``), antecipados
presenciais (``ev``) e do dia da eleição (``ed``), o total (``tv``) e as secções
apuradas (``pr``) e totais (``tp``). O total inclui alguns votos que não vêm separados
por tipo (cerca de 0,1% em 2024); ficam em ``outro``. Os ficheiros de 2022 e 2024
continuam publicados.
"""

import json
import re
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import polars as pl

from contratos.estados import CodigoEstado
from pipeline.comum.erros import ErroFormatoFonte
from pipeline.connectors.results.comum import ObterTexto, Pedido, identificar_corrida, partido
from pipeline.transform.resultados.montar import (
    COLUNAS_MODALIDADES,
    COLUNAS_UNIDADES,
    COLUNAS_VOTOS,
    DescricaoCorrida,
    Leitura,
)

URL = "https://appfiles.harrisvotes.com/harrisvotes/prd/Data/{codigo}/resultsbyballot.json"
FICHEIRO = "resultsbyballot.json"
MODALIDADES = {"ab": "correio", "ev": "antecipado_presencial", "ed": "dia_eleicao"}
_PARTIDO = re.compile(r"^(?P<nome>.*?)\s*\((?P<partido>[A-Z]+)\)\s*$")


def codigo(data: date) -> str:
    return f"{data:%m%y}"


@dataclass(frozen=True, slots=True)
class FonteHarris:
    fips: str = "48201"
    nome_fonte: str = "Harris County Clerk, Election Results"

    def pedidos(self, data: date, obter: ObterTexto) -> list[Pedido]:
        del obter
        return [Pedido(URL.format(codigo=codigo(data)), FICHEIRO)]

    def ler(self, pasta: Path, data: date) -> Leitura:
        caminho = pasta / FICHEIRO
        try:
            dados = json.loads(caminho.read_text(encoding="utf-8-sig"))
            contests: list[dict[str, Any]] = dados["contests"]
            ec = str(dados["ec"])
        except (json.JSONDecodeError, KeyError, TypeError) as erro:
            msg = f"Harris, {caminho.name}: formato inesperado"
            raise ErroFormatoFonte(msg) from erro
        if ec != codigo(data):
            msg = f"Harris: o ficheiro é da eleição {ec}, esperava {codigo(data)}"
            raise ErroFormatoFonte(msg)
        corridas: dict[str, DescricaoCorrida] = {}
        votos: list[tuple[object, ...]] = []
        unidades: list[tuple[object, ...]] = []
        modalidades: list[tuple[object, ...]] = []
        for c in contests:
            desc = identificar_corrida(CodigoEstado.TX, str(c.get("t", "")))
            if desc is None:
                continue
            nomes = c.get("ca") or []
            totais = c.get("tv") or []
            if len(nomes) != len(totais):
                msg = f"Harris, {desc.id}: {len(nomes)} candidatos e {len(totais)} totais"
                raise ErroFormatoFonte(msg)
            corridas[desc.id] = desc
            for i, rotulo_nome in enumerate(nomes):
                m = _PARTIDO.match(str(rotulo_nome))
                nome, rotulo = (m["nome"], m["partido"]) if m else (str(rotulo_nome), "")
                nome = re.sub(r"\s+", " ", nome).strip()
                votos.append(
                    (desc.id, nome, nome, partido(rotulo), rotulo or None, "condado",
                     self.fips, _int(totais[i]))
                )  # fmt: skip
                por_tipo = {
                    m_: _int((c.get(k) or [])[i])
                    for k, m_ in MODALIDADES.items()
                    if len(c.get(k) or []) == len(nomes)
                }
                if por_tipo:
                    # O total inclui votos que o ficheiro não separa por tipo
                    # (provisórios, por exemplo): ficam em "outro".
                    resto = _int(totais[i]) - sum(por_tipo.values())
                    if resto < 0:
                        msg = f"Harris, {desc.id}: os tipos de voto excedem o total de {nome}"
                        raise ErroFormatoFonte(msg)
                    por_tipo["outro"] = resto
                modalidades.extend(
                    (desc.id, nome, "condado", self.fips, m_, n) for m_, n in por_tipo.items()
                )
            unidades.append((desc.id, "condado", self.fips, _int(c.get("pr")), _int(c.get("tp"))))
        atualizado = _data(dados.get("dt"))
        return Leitura(
            corridas=tuple(corridas.values()),
            votos=pl.DataFrame(votos, schema=COLUNAS_VOTOS, orient="row"),
            unidades=pl.DataFrame(unidades, schema=COLUNAS_UNIDADES, orient="row"),
            tipo_unidade="seccao",
            atualizado_fonte=atualizado,
            modalidades=pl.DataFrame(modalidades, schema=COLUNAS_MODALIDADES, orient="row"),
        )


def _int(valor: object) -> int:
    if isinstance(valor, bool) or not isinstance(valor, int) or valor < 0:
        msg = f"Harris: número inválido {valor!r}"
        raise ErroFormatoFonte(msg)
    return valor


def _data(valor: object) -> datetime | None:
    if not isinstance(valor, str):
        return None
    try:
        return datetime.fromisoformat(valor.replace("Z", "+00:00")).astimezone(UTC)
    except ValueError:
        return None
