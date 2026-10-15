"""Contrato das classificações de outros prognosticadores (Cook, Sabato, Inside Elections...).

Um ficheiro ``PrognosticosExternos`` por recolha, lido das tabelas de classificações da
Wikipedia. Serve para pôr a previsão do Escrutínio ao lado das outras e, depois de 3 de
novembro, para avaliar todas pela mesma régua. Congela com a previsão.
"""

from datetime import date
from typing import Literal

from pydantic import AwareDatetime, Field, HttpUrl

from contratos.base import Metadados, ModeloContrato

Categoria = Literal["seguro", "provavel", "inclinado", "ligeiro", "empate"]
"""Safe/Solid, Likely, Lean, Tilt e Tossup, por esta ordem de certeza."""


class Prognosticador(ModeloContrato):
    """Quem publica as classificações e a data da versão que a tabela cita."""

    chave: str = Field(pattern=r"^[a-z0-9-]+$")
    """Identificador estável, por exemplo ``cook`` ou ``sabato``."""

    nome: str = Field(min_length=1)
    data: date | None
    """Data da versão das classificações, como a tabela da Wikipedia a indica."""

    url: HttpUrl | None


class Classificacao(ModeloContrato):
    """Classificação de uma corrida por um prognosticador."""

    prognosticador: str = Field(pattern=r"^[a-z0-9-]+$")
    categoria: Categoria
    partido: Literal["D", "R", "I"] | None
    """Lado favorecido; ``None`` só no empate."""


class CorridaPrognosticos(ModeloContrato):
    """Classificações de uma corrida, com o mesmo ``id`` da ``PrevisaoCongresso``."""

    id: str = Field(pattern=r"^[A-Z]{2}-(\d{2}|S|S-especial)$")
    classificacoes: tuple[Classificacao, ...] = Field(min_length=1)


class PrognosticosExternos(ModeloContrato):
    """Classificações publicadas por outros prognosticadores para o Senado e a Câmara.

    Na Câmara só aparecem os distritos que pelo menos um prognosticador não dá como
    seguros, como na tabela de origem.
    """

    metadados: Metadados
    ano: int
    recolhido_em: AwareDatetime
    congelado: bool
    """Verdadeiro na versão de 1 de novembro, que serve para a avaliação."""

    prognosticadores_senado: tuple[Prognosticador, ...] = Field(min_length=1)
    prognosticadores_camara: tuple[Prognosticador, ...] = Field(min_length=1)
    senado: tuple[CorridaPrognosticos, ...] = Field(min_length=1)
    camara: tuple[CorridaPrognosticos, ...] = Field(min_length=1)
