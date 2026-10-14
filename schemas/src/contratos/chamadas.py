"""Chamadas de vencedor feitas pelas redações na noite eleitoral.

O Escrutínio não declara vencedores. Quando uma redação (por exemplo, a Associated
Press) chama uma corrida, a chamada é registada à mão, com a fonte, e o site mostra-a
ao lado da contagem e da projeção. Retirar uma chamada é apagá-la do ficheiro.
"""

from typing import Literal, Self

from pydantic import AwareDatetime, Field, HttpUrl, model_validator

from contratos.base import Metadados, ModeloContrato

LadoChamada = Literal["D", "R", "outro"]
"""O lado do vencedor, com a mesma regra da previsão (um independente apoiado pelos
democratas conta como D)."""


class ChamadaRedacao(ModeloContrato):
    corrida: str = Field(pattern=r"^[A-Z]{2}-(\d{2}|S|S-especial)$")
    """Identificador da corrida na previsão."""

    vencedor: LadoChamada
    candidato: str | None = Field(default=None, min_length=1)
    redacao: str = Field(min_length=1)
    """Quem fez a chamada, por exemplo "Associated Press"."""

    url: HttpUrl
    """Página da redação com a chamada."""

    hora: AwareDatetime
    """Hora da chamada, tal como a redação a publicou (ou a do registo, sem ela)."""

    registada_em: AwareDatetime


class ChamadasRedacoes(ModeloContrato):
    """Chamadas em vigor, uma por corrida, pela ordem em que foram registadas."""

    metadados: Metadados
    ano: int
    chamadas: tuple[ChamadaRedacao, ...]

    @model_validator(mode="after")
    def _uma_por_corrida(self) -> Self:
        vistas: set[str] = set()
        for c in self.chamadas:
            if c.corrida in vistas:
                msg = f"{c.corrida}: mais do que uma chamada"
                raise ValueError(msg)
            vistas.add(c.corrida)
        return self
