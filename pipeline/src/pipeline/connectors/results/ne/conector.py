"""Conector de resultados do Nebraska.

O Secretary of State publica CSV a pedido em ``electionresults.nebraska.gov/resultsCSV.aspx``
(parâmetros ``type`` e ``map``): ``type=SW`` traz as corridas estaduais (Senado e
governador, entre outras) e ``type=CG`` os três distritos da Câmara. Cada ficheiro tem uma
linha por candidato com os votos totais e as secções apuradas (``PrecinctsReporting``, no
formato ``="12/438"``). A fonte só publica o total de cada corrida (sem condados) e não
separa os votos por tipo.

O endereço mostra sempre a eleição em curso: não há arquivo de eleições passadas (o
parâmetro ``eid`` é ignorado), por isso o ensaio geral com dados de 2022 ou 2024 não é
possível. O nome da corrida da Câmara não traz o distrito (``For Representative in Congress
- 2  Year Term``; o "2" é a duração do mandato), que vem em ``AreaNum`` (``District 01``).
"""

import csv
import re
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import polars as pl

from contratos.estados import CodigoEstado
from pipeline.comum.erros import ErroFormatoFonte
from pipeline.connectors.results.comum import ObterTexto, Pedido, identificar_corrida, partido
from pipeline.transform.resultados.montar import (
    COLUNAS_UNIDADES,
    COLUNAS_VOTOS,
    DescricaoCorrida,
    Leitura,
)

BASE = "https://electionresults.nebraska.gov/resultsCSV.aspx?text=All&type={tipo}&map=DIST"
FICHEIROS = {"SW": "estado.csv", "CG": "camara.csv"}
"""Tipo de corrida da fonte e ficheiro local. ``SW`` (estaduais) e ``CG`` (Câmara)."""
CAMPOS = frozenset(
    {"RaceName", "PartyCode", "AreaType", "AreaNum", "CandidateID", "CandidateName",
     "CurrentDateTime", "CandidateVotes", "PrecinctsReporting"}
)  # fmt: skip
_APURADAS = re.compile(r"(\d+)\s*/\s*(\d+)")
_DISTRITO = re.compile(r"(\d+)")
_FUSO = ZoneInfo("America/Chicago")


def _limpo(texto: str) -> str:
    """A fonte separa os nomes com espaços duplos e deixa um espaço no fim."""
    return " ".join(texto.split())


def _corrida(linha: dict[str, str]) -> DescricaoCorrida | None:
    nome = _limpo(linha["RaceName"])
    if linha["AreaType"].strip() == "CG":
        m = _DISTRITO.search(linha["AreaNum"])
        if m is None:
            return None
        distrito = int(m.group(1))
        return DescricaoCorrida(f"NE-{distrito:02d}", nome, "camara", distrito)
    desc = identificar_corrida(CodigoEstado.NE, nome.removeprefix("For "))
    if desc is None or desc.cargo not in {"senado", "governador"}:
        return None
    return desc


@dataclass(frozen=True, slots=True)
class ConectorNE:
    estado: CodigoEstado = CodigoEstado.NE
    nome_fonte: str = "Nebraska Secretary of State, Election Results"
    licenca: str | None = "Registo público (Neb. Rev. Stat. 84-712)"

    def pedidos(self, data: date, obter: ObterTexto) -> list[Pedido]:
        del data, obter
        return [Pedido(BASE.format(tipo=t), f) for t, f in FICHEIROS.items()]

    def ler(self, pasta: Path, data: date) -> Leitura:
        del data
        corridas: dict[str, DescricaoCorrida] = {}
        votos: list[tuple[object, ...]] = []
        unidades: dict[str, tuple[int, int]] = {}
        atualizado: datetime | None = None
        for ficheiro in FICHEIROS.values():
            caminho = pasta / ficheiro
            with caminho.open(encoding="utf-8-sig", newline="") as f:
                leitor = csv.DictReader(f)
                if not set(leitor.fieldnames or ()) >= CAMPOS:
                    msg = f"{caminho.name}: colunas inesperadas {leitor.fieldnames}"
                    raise ErroFormatoFonte(msg)
                for linha in leitor:
                    desc = _corrida(linha)
                    if desc is None:
                        continue
                    apuradas = _APURADAS.search(linha["PrecinctsReporting"])
                    if apuradas is None:
                        msg = f"{caminho.name}: secções ilegíveis {linha['PrecinctsReporting']!r}"
                        raise ErroFormatoFonte(msg)
                    corridas[desc.id] = desc
                    unidades[desc.id] = (int(apuradas.group(1)), int(apuradas.group(2)))
                    nome = _limpo(linha["CandidateName"])
                    rotulo = linha["PartyCode"].strip()
                    votos.append(
                        (desc.id, linha["CandidateID"].strip(), nome, partido(rotulo),
                         rotulo or None, "estado", None, int(linha["CandidateVotes"] or 0))
                    )  # fmt: skip
                    instante = _instante(linha["CurrentDateTime"])
                    if instante is not None and (atualizado is None or instante > atualizado):
                        atualizado = instante
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


def _instante(texto: str) -> datetime | None:
    """``10/14/2026 10:47:30 AM``, na hora do Centro (a fonte não indica o fuso)."""
    try:
        return datetime.strptime(texto.strip(), "%m/%d/%Y %I:%M:%S %p").replace(tzinfo=_FUSO)
    except ValueError:
        return None
