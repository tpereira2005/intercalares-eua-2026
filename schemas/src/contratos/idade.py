"""Sinal etário do voto antecipado (secção 6.4 do plano): um diagnóstico mostrado.

O ficheiro diz quanto o eleitorado projetado, por faixa etária e partido de registo,
puxa a margem face aos eleitores registados, comparado com a eleição de referência. Tem
peso zero na previsão; os backtests vêm no próprio ficheiro.
"""

from datetime import date
from typing import Literal

from pydantic import Field

from contratos.base import Metadados, ModeloContrato
from contratos.estados import CodigoEstado
from contratos.voto_antecipado import Faixa

Quota = Field(ge=0.0, le=1.0)
Margem = Field(ge=-100.0, le=100.0)
PartidoIdade = Literal["dem", "rep", "nao_afiliado"]


class GrupoIdade(ModeloContrato):
    """Uma faixa etária num partido de registo (``outro`` junta-se aos não filiados)."""

    faixa: Faixa
    partido: PartidoIdade
    quota_antecipado: float = Quota
    """Quota no voto antecipado chegado até ao dia dos dados."""

    quota_projetada: float = Quota
    """Quota projetada no eleitorado final."""

    quota_registados: float = Quota
    quota_final_referencia: float = Quota
    """Quota no eleitorado final da eleição de referência."""

    margem: float = Margem
    """Margem D-R estimada do grupo (pontos), versão central."""

    margem_minima: float = Margem
    margem_maxima: float = Margem
    """Extremos entre as versões da regressão ecológica (anos e penalizações)."""


class BacktestIdade(ModeloContrato):
    """Uma eleição passada projetada com as do mesmo tipo, no mesmo dia."""

    ano: int
    referencias: tuple[int, ...] = Field(min_length=1)
    dias_antes: int
    inclinacao_real: float
    """Pontos de margem que o eleitorado final puxou face aos registados."""

    inclinacao_projetada: float


class DiagnosticoIdade(ModeloContrato):
    metadados: Metadados
    ano: int
    estado: CodigoEstado
    data_dados: date
    """Último dia de voto antecipado incluído."""

    dias_antes: int
    """Dias entre ``data_dados`` e a eleição."""

    votos_antecipados: int = Field(ge=0)
    ano_referencia: int
    """Eleição com que se compara (a intercalar anterior)."""

    grupos: tuple[GrupoIdade, ...] = Field(min_length=1)
    inclinacao_projetada: float
    inclinacao_referencia: float
    efeito: float
    """Inclinação projetada menos a da referência, em pontos de margem D-R: positivo
    quando o eleitorado deste ano puxa mais para os democratas do que o da referência."""

    efeito_p10: float
    efeito_p90: float
    erro_backtest: float = Field(ge=0.0)
    """Raiz do erro quadrático médio da inclinação projetada nos backtests, no mesmo dia."""

    peso_previsao: Literal[0] = 0
    """O sinal é mostrado, não entra na previsão."""

    backtests: tuple[BacktestIdade, ...]
    notas: tuple[str, ...] = ()
