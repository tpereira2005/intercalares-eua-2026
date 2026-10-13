"""Entradas do Modelo C: contagens parciais por unidade e a eleição de referência.

As contagens seguem a interface combinada com a recolha de resultados: uma linha por
corrida e por unidade (FIPS do condado, ou ``total`` quando a fonte só dá o total da
corrida), com votos cumulativos do lado democrata, do lado republicano e dos outros.
"""

import csv
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from contratos.resultados import ResultadosParciais
from pipeline.comum.erros import ErroFormatoFonte

TOTAL = "total"


@dataclass(frozen=True, slots=True)
class Contagem:
    corrida: str
    """Identificador da previsão: ``PA-S``, ``NC-01``, ``OH-S-especial``."""

    unidade: str
    """FIPS do condado (5 dígitos) ou ``total``."""

    votos_d: int
    votos_r: int
    votos_outros: int
    fracao_contada: float | None = None
    """Fração do voto esperado já contada, quando a fonte a publica."""

    seccoes_reportadas: int | None = None
    seccoes_totais: int | None = None

    @property
    def fracao_seccoes(self) -> float | None:
        """Secções reportadas a dividir pelas existentes. É uma aproximação pior do que
        ``fracao_contada``: o voto antecipado chega muitas vezes antes das secções."""
        if self.seccoes_reportadas is None or not self.seccoes_totais:
            return None
        return min(self.seccoes_reportadas / self.seccoes_totais, 1.0)

    @property
    def votos(self) -> int:
        return self.votos_d + self.votos_r + self.votos_outros

    @property
    def margem(self) -> float | None:
        total = self.votos
        return 100.0 * (self.votos_d - self.votos_r) / total if total > 0 else None


@dataclass(frozen=True, slots=True)
class Instantaneo:
    """Todas as contagens conhecidas num instante (cumulativas)."""

    instante: datetime
    contagens: tuple[Contagem, ...]


@dataclass(frozen=True, slots=True)
class Base:
    """Resultado de uma unidade na eleição de referência (a presidencial anterior)."""

    votos: float
    margem: float
    """Margem D-R em pontos."""


Referencia = Mapping[str, Mapping[str, Base]]
"""Estado -> unidade (FIPS) -> resultado de referência."""


def de_parciais(parciais: ResultadosParciais) -> Instantaneo:
    """Converte o contrato da recolha de resultados nas entradas do estimador."""
    contagens = tuple(
        Contagem(
            corrida=u.corrida,
            unidade=u.unidade,
            votos_d=u.votos_d,
            votos_r=u.votos_r,
            votos_outros=u.votos_outros,
            fracao_contada=u.percentagem_contada,
            seccoes_reportadas=u.seccoes_reportadas,
            seccoes_totais=u.seccoes_totais,
        )
        for u in parciais.unidades
    )
    return Instantaneo(parciais.instante, contagens)


def agrupar(contagens: Iterable[Contagem]) -> dict[str, list[Contagem]]:
    por_corrida: dict[str, list[Contagem]] = {}
    for c in contagens:
        por_corrida.setdefault(c.corrida, []).append(c)
    return por_corrida


def ler_referencia(caminho: Path) -> dict[str, dict[str, Base]]:
    """Lê um CSV ``estado,fips,votos,margem`` (uma linha por condado)."""
    referencia: dict[str, dict[str, Base]] = {}
    with caminho.open(encoding="utf-8", newline="") as ficheiro:
        for linha in csv.DictReader(ficheiro):
            votos = float(linha["votos"])
            if votos <= 0:
                raise ErroFormatoFonte(f"Votos inválidos em {linha['fips']}")
            referencia.setdefault(linha["estado"], {})[linha["fips"]] = Base(
                votos, float(linha["margem"])
            )
    return referencia
