"""Junta as fontes de vários condados de um estado num só conector de resultados.

Cada fonte trata de um condado e guarda os ficheiros numa subpasta com o FIPS. A leitura
junta as unidades dos condados, sem linha do estado, e marca a cobertura como parcial.
Um condado que falhe faz falhar o ciclo do estado (o último ficheiro válido continua
publicado), como nos outros conectores.
"""

from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Protocol

import polars as pl

from contratos.estados import CodigoEstado
from pipeline.connectors.results.comum import ObterTexto, Pedido
from pipeline.transform.resultados.montar import DescricaoCorrida, Leitura


class FonteCondado(Protocol):
    @property
    def fips(self) -> str: ...

    @property
    def nome_fonte(self) -> str: ...

    def pedidos(self, data: date, obter: ObterTexto) -> list[Pedido]: ...

    def ler(self, pasta: Path, data: date) -> Leitura: ...


@dataclass(frozen=True, slots=True)
class ConectorCondados:
    estado: CodigoEstado
    fontes: tuple[FonteCondado, ...]
    licenca: str | None = "Registo público"

    @property
    def nome_fonte(self) -> str:
        return "; ".join(f.nome_fonte for f in self.fontes)

    def pedidos(self, data: date, obter: ObterTexto) -> list[Pedido]:
        return [
            Pedido(p.url, f"{f.fips}/{p.ficheiro}", sentinela=p.sentinela)
            for f in self.fontes
            for p in f.pedidos(data, obter)
        ]

    def ler(self, pasta: Path, data: date) -> Leitura:
        leituras = [f.ler(pasta / f.fips, data) for f in self.fontes]
        corridas: dict[str, DescricaoCorrida] = {}
        for leitura in leituras:
            for c in leitura.corridas:
                corridas.setdefault(c.id, c)
        modalidades = [x.modalidades for x in leituras if x.modalidades is not None]
        return Leitura(
            corridas=tuple(corridas.values()),
            votos=pl.concat([x.votos for x in leituras]),
            unidades=pl.concat([x.unidades for x in leituras]),
            tipo_unidade="seccao",
            atualizado_fonte=max(
                (x.atualizado_fonte for x in leituras if x.atualizado_fonte), default=None
            ),
            modalidades=pl.concat(modalidades) if modalidades else None,
            cobertura_condados=tuple(f.fips for f in self.fontes),
        )
