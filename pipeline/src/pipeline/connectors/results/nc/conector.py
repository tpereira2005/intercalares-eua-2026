"""Conector de resultados da Carolina do Norte.

A NCSBE publica, para cada eleição, um ficheiro JSON com o estado (``results_0.txt``) e
um por condado (``results_1.txt`` a ``results_100.txt``, pelos identificadores da NCSBE,
que seguem a ordem alfabética e não a dos códigos FIPS). Uma linha por candidato e
corrida, com os votos, as secções apuradas (``prt``) e o total de secções (``ptl``).
Os ficheiros de 2022 e 2024 continuam publicados no mesmo formato.
"""

import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import polars as pl

from contratos.estados import CodigoEstado
from pipeline.comum.erros import ErroFormatoFonte
from pipeline.connectors.early_vote.nc.codigos import CONDADOS, FIPS_CONDADO, NOME_CONDADO
from pipeline.connectors.results.comum import ObterTexto, Pedido, identificar_corrida, partido
from pipeline.transform.resultados.montar import (
    COLUNAS_MODALIDADES,
    COLUNAS_UNIDADES,
    COLUNAS_VOTOS,
    DescricaoCorrida,
    Leitura,
)

BASE = "https://er.ncsbe.gov/enr/{data:%Y%m%d}/data/results_{codigo}.txt"
CAMPOS = {"cnm", "bnm", "pty", "vct", "prt", "ptl", "cid"}
NOMES_GEO = NOME_CONDADO
MODALIDADES = {
    "evc": "antecipado_presencial",
    "ovc": "dia_eleicao",
    "avc": "correio",
    "pvc": "provisorio",
}
"""Colunas da NCSBE com os votos por tipo: one-stop, dia da eleição, correio, provisório."""


def _fips(cid: int) -> str:
    return FIPS_CONDADO[CONDADOS[cid - 1]]


@dataclass(frozen=True, slots=True)
class ConectorNC:
    estado: CodigoEstado = CodigoEstado.NC
    nome_fonte: str = "North Carolina State Board of Elections, Election Night Results"
    licenca: str | None = "Registo público (N.C.G.S. 132)"
    condados: bool = True
    """Pedir também os 100 ficheiros dos condados (mais pesado; ver ``recolha``)."""

    def pedidos(self, data: date, obter: ObterTexto) -> list[Pedido]:
        del obter
        codigos = [0, *range(1, len(CONDADOS) + 1)] if self.condados else [0]
        return [
            Pedido(BASE.format(data=data, codigo=c), f"results_{c}.txt", sentinela=c == 0)
            for c in codigos
        ]

    def ler(self, pasta: Path, data: date) -> Leitura:
        del data
        estado = pasta / "results_0.txt"
        if not estado.exists():
            msg = f"Falta {estado}"
            raise ErroFormatoFonte(msg)
        corridas: dict[str, DescricaoCorrida] = {}
        votos: list[tuple[object, ...]] = []
        unidades: list[tuple[object, ...]] = []
        modalidades: list[tuple[object, ...]] = []
        for caminho in sorted(pasta.glob("results_*.txt")):
            cid = int(caminho.stem.removeprefix("results_"))
            if cid > len(CONDADOS):
                continue
            nivel, codigo = ("estado", None) if cid == 0 else ("condado", _fips(cid))
            vistos: set[str] = set()
            for linha in _linhas(caminho):
                desc = corridas.get(linha["cnm"]) or identificar_corrida(self.estado, linha["cnm"])
                if desc is None:
                    continue
                corridas[linha["cnm"]] = desc
                votos.append(
                    (
                        desc.id,
                        linha["bnm"].strip(),
                        linha["bnm"].strip(),
                        partido(linha["pty"]),
                        linha["pty"].strip() or None,
                        nivel,
                        codigo,
                        int(linha["vct"]),
                    )
                )
                modalidades.extend(
                    (desc.id, linha["bnm"].strip(), nivel, codigo, m, int(linha[c]))
                    for c, m in MODALIDADES.items()
                    if linha.get(c, "").strip().isdigit()
                )
                if desc.id not in vistos:
                    vistos.add(desc.id)
                    unidades.append((desc.id, nivel, codigo, int(linha["prt"]), int(linha["ptl"])))
        return Leitura(
            corridas=tuple({d.id: d for d in corridas.values()}.values()),
            votos=pl.DataFrame(votos, schema=COLUNAS_VOTOS, orient="row"),
            unidades=pl.DataFrame(unidades, schema=COLUNAS_UNIDADES, orient="row"),
            tipo_unidade="seccao",
            modalidades=pl.DataFrame(modalidades, schema=COLUNAS_MODALIDADES, orient="row"),
        )


def _linhas(caminho: Path) -> list[dict[str, str]]:
    try:
        dados = json.loads(caminho.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError as erro:
        msg = f"{caminho.name} não é JSON válido"
        raise ErroFormatoFonte(msg) from erro
    if not isinstance(dados, list) or not all(
        isinstance(x, dict) and x.keys() >= CAMPOS for x in dados
    ):
        msg = f"{caminho.name}: formato inesperado"
        raise ErroFormatoFonte(msg)
    return [{k: str(v) for k, v in x.items()} for x in dados]
