"""Contrato da análise de sensibilidade da previsão.

Um ficheiro ``SensibilidadePrevisao`` por atualização diária: o resultado de 2026 com cada
escolha do modelo mudada uma de cada vez. Os backtests de cada variante não se publicam.
"""

from datetime import date

from pydantic import Field

from contratos.base import Metadados, ModeloContrato
from contratos.previsao import CodigoCommit, Probabilidade


class ResumoSensibilidade(ModeloContrato):
    """Controlo e lugares do lado democrata numa câmara, para uma variante."""

    prob_controlo_d: float = Probabilidade
    lugares_d_mediana: int = Field(ge=0)
    lugares_d_p10: int = Field(ge=0)
    lugares_d_p90: int = Field(ge=0)


class VarianteSensibilidade(ModeloContrato):
    """Uma escolha do modelo alterada e o que ela faz à previsão de 2026."""

    nome: str = Field(min_length=1)
    descricao: str = Field(min_length=1)
    """O que muda em relação ao modelo publicado, numa frase."""

    ambiente: float
    """Margem nacional D-R (pontos percentuais) usada nesta variante."""

    camara: ResumoSensibilidade
    senado: ResumoSensibilidade


class SensibilidadePrevisao(ModeloContrato):
    """Sensibilidade da previsão, calculada com os mesmos dados e o mesmo corte da
    ``PrevisaoCongresso`` do dia. A primeira variante é o modelo publicado."""

    metadados: Metadados
    ano: int
    corte: date
    codigo_commit: str | None = CodigoCommit
    variantes: tuple[VarianteSensibilidade, ...] = Field(min_length=1)
