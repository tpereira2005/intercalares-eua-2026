"""Conector de resultados da Califórnia.

O Secretary of State publica ficheiros JSON em ``media.sos.ca.gov/media/``, um por cargo:
``us-rep.json`` (Câmara) e ``governor.json`` (governador). Cada ficheiro é uma lista de
corridas com o título (``United States Representative District 1 - Districtwide
Results``), o apuramento em texto (``34.9% (275 of 788) precincts reporting``), a hora
(``October 14, 2026, 8:50 a.m.``, hora do Pacífico) e os candidatos com partido (``Dem``,
``Rep``, ``NPP``...) e votos com separador de milhares.

Além do total de cada corrida (``Districtwide`` ou ``Statewide``) há uma linha por condado
dentro de cada distrito; só se lê o total. A fonte não separa os votos por tipo e não guarda
eleições anteriores: os ficheiros mostram sempre a eleição em curso, por isso não há ensaio
geral. Não há corrida ao Senado dos EUA na Califórnia em 2026; o ``us-senate.json`` mantém os
resultados de 2024 e não se lê. Como os ficheiros não indicam a eleição, a leitura recusa um
ficheiro cuja hora seja de outro ano.

Antes da eleição, o Secretary of State publica nestes endereços dados de ensaio, com votos
fictícios. A lei da Califórnia não deixa divulgar resultados antes do fecho das urnas (20:00,
hora do Pacífico), por isso uma corrida com hora anterior conta como ensaio e é lida com zero
votos e zero secções apuradas.
"""

import json
import re
from dataclasses import dataclass
from datetime import date, datetime, time
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import polars as pl

from contratos.estados import CodigoEstado
from pipeline.comum.erros import ErroFormatoFonte
from pipeline.connectors.results.comum import ObterTexto, Pedido, partido
from pipeline.transform.resultados.montar import (
    COLUNAS_UNIDADES,
    COLUNAS_VOTOS,
    DescricaoCorrida,
    Leitura,
)

BASE = "https://media.sos.ca.gov/media/{ficheiro}"
FICHEIROS = {"camara": "us-rep.json", "governador": "governor.json"}
"""Cargo e nome do ficheiro na fonte (que é também o nome local)."""
_CAMARA = re.compile(r"^United States Representative District (\d{1,2}) - Districtwide Results$")
_GOVERNADOR = re.compile(r"^Governor - Statewide Results$")
_APURADAS = re.compile(r"\((\d[\d,]*) of (\d[\d,]*)\) precincts reporting")
_FUSO = ZoneInfo("America/Los_Angeles")
FECHO_URNAS = time(20)
"""Hora local do fecho das urnas; os dados com hora anterior são de ensaio."""


def _corrida(titulo: str) -> DescricaoCorrida | None:
    if m := _CAMARA.match(titulo.strip()):
        distrito = int(m.group(1))
        return DescricaoCorrida(f"CA-{distrito:02d}", titulo.strip(), "camara", distrito)
    if _GOVERNADOR.match(titulo.strip()):
        return DescricaoCorrida("CA-G", titulo.strip(), "governador")
    return None


def _inteiro(texto: object, campo: str) -> int:
    try:
        n = int(str(texto).replace(",", "").strip() or 0)
    except ValueError as erro:
        msg = f"Califórnia: {campo} inválido {texto!r}"
        raise ErroFormatoFonte(msg) from erro
    if n < 0:
        msg = f"Califórnia: {campo} negativo {texto!r}"
        raise ErroFormatoFonte(msg)
    return n


def _instante(texto: object) -> datetime | None:
    """``October 14, 2026, 8:50 a.m.``, na hora do Pacífico (a fonte não indica o fuso)."""
    limpo = str(texto).replace("a.m.", "AM").replace("p.m.", "PM").strip()
    try:
        return datetime.strptime(limpo, "%B %d, %Y, %I:%M %p").replace(tzinfo=_FUSO)
    except ValueError:
        return None


@dataclass(frozen=True, slots=True)
class ConectorCA:
    estado: CodigoEstado = CodigoEstado.CA
    nome_fonte: str = "California Secretary of State, Election Results"
    licenca: str | None = "Registo público (California Public Records Act)"

    def pedidos(self, data: date, obter: ObterTexto) -> list[Pedido]:
        del data, obter
        return [Pedido(BASE.format(ficheiro=f), f) for f in FICHEIROS.values()]

    def ler(self, pasta: Path, data: date) -> Leitura:
        corridas: dict[str, DescricaoCorrida] = {}
        votos: list[tuple[object, ...]] = []
        unidades: dict[str, tuple[int, int]] = {}
        atualizado: datetime | None = None
        fecho = datetime.combine(data, FECHO_URNAS, tzinfo=_FUSO)
        for ficheiro in FICHEIROS.values():
            caminho = pasta / ficheiro
            try:
                lista: list[dict[str, Any]] = json.loads(caminho.read_text(encoding="utf-8-sig"))
                for r in lista:
                    desc = _corrida(str(r["raceTitle"]))
                    if desc is None:
                        continue
                    instante = _instante(r.get("ReportingTime"))
                    if instante is not None and instante.year != data.year:
                        msg = (
                            f"Califórnia, {ficheiro}: o ficheiro é de {instante.year}, "
                            f"não de {data.year}"
                        )
                        raise ErroFormatoFonte(msg)
                    ensaio = instante is not None and instante < fecho
                    apuradas = _APURADAS.search(str(r["Reporting"]))
                    if apuradas is None:
                        msg = f"Califórnia, {desc.id}: apuramento ilegível {r['Reporting']!r}"
                        raise ErroFormatoFonte(msg)
                    corridas[desc.id] = desc
                    unidades[desc.id] = (
                        0 if ensaio else _inteiro(apuradas.group(1), "secções apuradas"),
                        _inteiro(apuradas.group(2), "secções"),
                    )
                    for c in r["candidates"]:
                        nome = " ".join(str(c["Name"]).split())
                        rotulo = str(c.get("Party") or "").strip()
                        votos.append(
                            (desc.id, nome, nome, partido(rotulo), rotulo or None, "estado", None,
                             0 if ensaio else _inteiro(c["Votes"], f"{desc.id} {nome}"))
                        )  # fmt: skip
                    if instante is not None and (atualizado is None or instante > atualizado):
                        atualizado = instante
            except (json.JSONDecodeError, KeyError, TypeError, AttributeError) as erro:
                msg = f"Califórnia, {ficheiro}: formato inesperado ({erro!r})"
                raise ErroFormatoFonte(msg) from erro
        if not corridas:
            msg = "Califórnia: nenhuma corrida de governador ou da Câmara nos ficheiros"
            raise ErroFormatoFonte(msg)
        return Leitura(
            corridas=tuple(corridas.values()),
            votos=pl.DataFrame(votos, schema=COLUNAS_VOTOS, orient="row"),
            unidades=pl.DataFrame(
                [(c, "estado", None, r, t) for c, (r, t) in unidades.items()],
                schema=COLUNAS_UNIDADES,
                orient="row",
            ),
            tipo_unidade="seccao",
            atualizado_fonte=atualizado,
        )
