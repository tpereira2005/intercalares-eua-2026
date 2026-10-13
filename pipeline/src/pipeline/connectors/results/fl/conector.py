"""Conector de resultados da Florida.

A Division of Elections publica um único ficheiro de texto separado por tabulações, com
uma linha por condado, corrida e candidato, e as secções apuradas em cada condado. As
corridas federais e de governador têm códigos fixos (``USS``, ``USR``, ``GOV``), por isso
não dependemos do nome. Os ficheiros de 2022 e 2024 continuam publicados; o de 2022
ficou com os votos a zero (é o retrato anterior à noite) e só serve para o formato.
"""

import csv
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import polars as pl

from contratos.estados import CodigoEstado
from pipeline.comum.condados import chave, fips_por_nome, nomes
from pipeline.comum.erros import ErroFormatoFonte
from pipeline.connectors.results.comum import ObterTexto, Pedido, partido
from pipeline.transform.resultados.montar import (
    COLUNAS_UNIDADES,
    COLUNAS_VOTOS,
    DescricaoCorrida,
    Leitura,
)

URL = "https://flelectionfiles.floridados.gov/enightfilespublic/{data:%Y%m%d}_ElecResultsFL.txt"
FICHEIRO = "resultados.txt"
CAMPOS = (
    "PartyCode", "RaceCode", "RaceName", "CountyName", "Juris1num", "Precincts",
    "PrecinctsReporting", "CanNameLast", "CanNameFirst", "CanNameMiddle", "CanVotes",
)  # fmt: skip


FIPS = fips_por_nome("FL")
NOMES_GEO = nomes("FL")


def _corrida(codigo: str, nome: str, distrito: str) -> DescricaoCorrida | None:
    if codigo == "USS":
        especial = "UNEXPIRED" in nome.upper() or "SPECIAL" in nome.upper()
        return DescricaoCorrida(
            "FL-S-especial" if especial else "FL-S", nome, "senado", especial=especial
        )
    if codigo == "USR":
        n = int(distrito)
        return DescricaoCorrida(f"FL-{n:02d}", nome, "camara", n)
    if codigo == "GOV":
        return DescricaoCorrida("FL-G", nome, "governador")
    return None


@dataclass(frozen=True, slots=True)
class ConectorFL:
    estado: CodigoEstado = CodigoEstado.FL
    nome_fonte: str = "Florida Division of Elections, Election Night Results"
    licenca: str | None = "Registo público (Fla. Stat. 119)"

    def pedidos(self, data: date, obter: ObterTexto) -> list[Pedido]:
        del obter
        return [Pedido(URL.format(data=data), FICHEIRO)]

    def ler(self, pasta: Path, data: date) -> Leitura:
        del data
        caminho = pasta / FICHEIRO
        with caminho.open(encoding="utf-8-sig", newline="") as f:
            leitor = csv.DictReader(f, delimiter="\t")
            if not set(CAMPOS) <= set(leitor.fieldnames or ()):
                msg = f"{caminho.name}: colunas inesperadas {leitor.fieldnames}"
                raise ErroFormatoFonte(msg)
            corridas: dict[str, DescricaoCorrida] = {}
            votos: list[tuple[object, ...]] = []
            unidades: dict[tuple[str, str], tuple[int, int]] = {}
            for linha in leitor:
                desc = _corrida(linha["RaceCode"].strip(), linha["RaceName"].strip(),
                                linha["Juris1num"].strip())  # fmt: skip
                if desc is None:
                    continue
                fips = FIPS.get(chave(linha["CountyName"]))
                if fips is None:
                    msg = f"Condado desconhecido: {linha['CountyName']!r}"
                    raise ErroFormatoFonte(msg)
                corridas[desc.id] = desc
                nome = " ".join(
                    p for p in (linha["CanNameFirst"], linha["CanNameMiddle"],
                                linha["CanNameLast"]) if p.strip()
                )  # fmt: skip
                codigo_partido = linha["PartyCode"].strip()
                votos.append(
                    (desc.id, f"{codigo_partido}:{nome}", nome, partido(codigo_partido),
                     codigo_partido or None, "condado", fips, int(linha["CanVotes"]))
                )  # fmt: skip
                unidades[(desc.id, fips)] = (
                    int(linha["PrecinctsReporting"]),
                    int(linha["Precincts"]),
                )
        return Leitura(
            corridas=tuple(corridas.values()),
            votos=pl.DataFrame(votos, schema=COLUNAS_VOTOS, orient="row"),
            unidades=pl.DataFrame(
                [(c, "condado", f, r, t) for (c, f), (r, t) in unidades.items()],
                schema=COLUNAS_UNIDADES,
                orient="row",
            ),
            tipo_unidade="seccao",
        )
