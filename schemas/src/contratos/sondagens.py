"""Contrato das sondagens publicadas para o site (página de sondagens).

Um ficheiro ``SondagensCongresso`` por atualização diária. Reúne as sondagens que o modelo
usa, com as médias calculadas pelo mesmo método da previsão (``docs/metodologia/
previsao.md``, secção 4), para que o site mostre exatamente o que entra no modelo. As
margens estão em pontos percentuais do total, sempre D-R (positivo favorece o lado
democrata).
"""

from datetime import date
from typing import Literal

from pydantic import Field

from contratos.base import Metadados, ModeloContrato
from contratos.estados import CodigoEstado
from contratos.previsao import CamaraCongresso, Probabilidade

PopulacaoSondagem = Literal["lv", "rv", "a", "?"]
"""Eleitores prováveis, registados, adultos ou desconhecida."""


class MetodoMedia(ModeloContrato):
    """Parâmetros da média de sondagens, para o site os poder explicar."""

    meia_vida_dias: float = Field(gt=0)
    janela_dias: int = Field(gt=0)
    amostra_referencia: int = Field(gt=0)
    amostra_maxima: int = Field(gt=0)
    peso_partidaria: float = Field(ge=0)


class SondagemPublicada(ModeloContrato):
    """Uma sondagem entre os dois candidatos da corrida."""

    instituto: str = Field(min_length=1)
    fim: date
    """Último dia do trabalho de campo."""

    amostra: int | None = Field(gt=0)
    populacao: PopulacaoSondagem
    partidaria: bool
    """Encomendada por um partido ou campanha (de qualquer lado)."""

    percentagem_d: float = Field(ge=0, le=100)
    percentagem_r: float = Field(ge=0, le=100)
    margem: float
    peso: float = Probabilidade
    """Peso relativo na média atual (os pesos das sondagens de uma corrida somam 1); 0
    quando a sondagem não entra (fora da janela ou substituída por outra população da
    mesma sondagem)."""


class PontoMedia(ModeloContrato):
    """Média de sondagens de uma corrida num dia."""

    data: date
    margem: float
    institutos: int = Field(ge=1)
    sondagens: int = Field(ge=1)


class SondagensCorrida(ModeloContrato):
    id: str = Field(pattern=r"^[A-Z]{2}-(\d{2}|S|S-especial)$")
    camara: CamaraCongresso
    estado: CodigoEstado
    candidato_d: str | None
    candidato_r: str | None
    media: PontoMedia | None
    """Média no dia do corte (``None`` sem sondagens na janela)."""

    serie: tuple[PontoMedia, ...]
    """Média dia a dia, só nos dias com sondagens na janela."""

    sondagens: tuple[SondagemPublicada, ...]
    """Da mais recente para a mais antiga."""


class ValorAgregador(ModeloContrato):
    nome: str = Field(min_length=1)
    margem: float


class PontoVotoGenerico(ModeloContrato):
    """Valores dos agregadores do voto genérico lidos num dia, e a sua média simples."""

    data: date
    margem: float
    agregadores: tuple[ValorAgregador, ...] = Field(min_length=1)


class SondagensCongresso(ModeloContrato):
    metadados: Metadados
    ano: int
    corte: date
    metodo: MetodoMedia
    voto_generico: tuple[PontoVotoGenerico, ...]
    """Por ordem cronológica (o mais recente no fim)."""

    corridas: tuple[SondagensCorrida, ...]
