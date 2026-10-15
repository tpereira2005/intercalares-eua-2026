"""Resultados introduzidos à mão, para os estados que recusam pedidos automáticos.

Na noite eleitoral, quem acompanha copia da página oficial do estado os totais das corridas
mais disputadas (Senado, governador e distritos em jogo) e introdu-los com o workflow
**Resultado manual** (``.github/workflows/resultado-manual.yml``), que corre
``pipeline.jobs.resultado_manual``. As entradas ficam em ``manual.json``, um ficheiro da
Release ``resultados-2026``; a recolha lê-o a cada ciclo e cria um ``ConectorManual`` por
estado presente. As corridas saem com ``manual = True`` e o site mostra-as com o selo
"introduzido manualmente".

Onde há fonte estadual aberta (``registo.CONECTORES``), os números vêm dela e a entrada
manual é recusada. Nos estados acompanhados só por alguns condados (Texas com Harris,
Arizona com Maricopa), a entrada manual fica **sobreposta**: publica-se à parte
(``tx-manual.json``) e as corridas introduzidas substituem, no resumo nacional e nos
parciais, as dos condados.
"""

import re
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Literal

import polars as pl
from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, HttpUrl, model_validator

from contratos.estados import CodigoEstado
from contratos.resultados import Cargo
from pipeline.comum.erros import ErroFormatoFonte
from pipeline.connectors.results.comum import ConectorResultados, ObterTexto, Pedido
from pipeline.connectors.results.condados.conector import ConectorCondados
from pipeline.transform.resultados.montar import (
    COLUNAS_UNIDADES,
    COLUNAS_VOTOS,
    DescricaoCorrida,
    Leitura,
)

FICHEIRO = "manual.json"
ID_CORRIDA = re.compile(r"^([A-Z]{2})-(S|G|\d{2})(-especial)?$")
ESCALA_PERCENTAGEM = 1000
"""Uma percentagem ("87%") guarda-se como 870 de 1000 unidades, sem tipo de unidade."""


class CandidatoManual(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    nome: str = Field(min_length=1)
    partido: Literal["dem", "rep", "outro"]
    votos: int = Field(ge=0)


class EntradaManual(BaseModel):
    """Os totais de uma corrida tal como a página oficial os mostra num instante."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    corrida: str = Field(pattern=ID_CORRIDA.pattern)
    candidatos: tuple[CandidatoManual, ...] = Field(min_length=1)
    reportadas: int = Field(ge=0)
    totais: int = Field(gt=0)
    seccoes: bool
    """``True`` quando o apuramento são secções (``"1234/2000"``); ``False`` quando a
    página só dá uma percentagem (guardada em milésimas)."""

    fonte: HttpUrl
    introduzido_em: AwareDatetime

    @model_validator(mode="after")
    def _coerente(self) -> "EntradaManual":
        if self.reportadas > self.totais:
            msg = f"{self.corrida}: mais unidades apuradas do que existentes"
            raise ValueError(msg)
        nomes = [c.nome for c in self.candidatos]
        if len(set(nomes)) != len(nomes):
            msg = f"{self.corrida}: candidatos repetidos"
            raise ValueError(msg)
        return self

    @property
    def estado(self) -> CodigoEstado:
        return CodigoEstado(self.corrida[:2])

    def descricao(self) -> DescricaoCorrida:
        m = ID_CORRIDA.match(self.corrida)
        if m is None:  # o padrão do campo já o garante
            msg = f"Corrida inválida: {self.corrida}"
            raise ValueError(msg)
        cargo: Cargo = (
            "senado" if m.group(2) == "S" else "governador" if m.group(2) == "G" else "camara"
        )
        distrito = None if cargo != "camara" else int(m.group(2))
        nome = {"senado": "Senado", "governador": "Governador"}.get(
            cargo, f"Câmara, distrito {distrito}"
        )
        return DescricaoCorrida(
            id=self.corrida,
            nome_fonte=f"{nome} (introduzido manualmente)",
            cargo=cargo,
            distrito=distrito,
            especial=m.group(3) is not None,
            notas=(f"Introduzido manualmente a partir de {self.fonte}",),
        )


class FicheiroManual(BaseModel):
    model_config = ConfigDict(extra="forbid")

    entradas: tuple[EntradaManual, ...] = ()

    @model_validator(mode="after")
    def _uma_por_corrida(self) -> "FicheiroManual":
        ids = [e.corrida for e in self.entradas]
        if len(set(ids)) != len(ids):
            msg = "Corridas repetidas em manual.json"
            raise ValueError(msg)
        return self

    def estados(self) -> set[CodigoEstado]:
        return {e.estado for e in self.entradas}


def aceita_manual(conector: ConectorResultados | None) -> bool:
    """Sem conector, ou só com alguns condados, o estado aceita entradas manuais."""
    return conector is None or isinstance(conector, ConectorCondados)


def _id(nome: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", nome.lower()).strip("-") or "candidato"


def ler_ficheiro(caminho: Path) -> FicheiroManual:
    try:
        return FicheiroManual.model_validate_json(caminho.read_bytes())
    except ValueError as erro:
        msg = f"{caminho.name} inválido: {erro}"
        raise ErroFormatoFonte(msg) from erro


@dataclass(frozen=True, slots=True)
class ConectorManual:
    estado: CodigoEstado
    url: str
    nome_fonte: str = "Página oficial do estado (introduzido manualmente)"
    licenca: str | None = "Registo público"
    sobreposto: bool = False
    """``True`` num estado que também tem um conector automático de alguns condados."""

    def pedidos(self, data: date, obter: ObterTexto) -> list[Pedido]:
        del data, obter
        return [Pedido(self.url, FICHEIRO)]

    def ler(self, pasta: Path, data: date) -> Leitura:
        del data
        entradas = [e for e in ler_ficheiro(pasta / FICHEIRO).entradas if e.estado == self.estado]
        votos = [
            (e.corrida, _id(c.nome), c.nome, c.partido, None, "estado", None, c.votos)
            for e in entradas
            for c in e.candidatos
        ]
        unidades = [(e.corrida, "estado", None, e.reportadas, e.totais) for e in entradas]
        seccoes = {e.seccoes for e in entradas}
        atualizado: datetime | None = max((e.introduzido_em for e in entradas), default=None)
        return Leitura(
            corridas=tuple(e.descricao() for e in entradas),
            votos=pl.DataFrame(votos, schema=COLUNAS_VOTOS, orient="row"),
            unidades=pl.DataFrame(unidades, schema=COLUNAS_UNIDADES, orient="row"),
            tipo_unidade="seccao" if seccoes == {True} else None,
            atualizado_fonte=atualizado,
            manual=True,
        )
