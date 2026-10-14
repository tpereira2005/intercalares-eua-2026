"""Contrato da projeção da noite eleitoral (Modelo C).

Um ficheiro ``ProjecaoNoite`` por instante de resultados. Parte da previsão congelada
(``PrevisaoCongresso``) e atualiza-a com os votos já contados. As margens estão em pontos
percentuais do voto total, sempre D-R (positivo favorece o lado democrata). A metodologia
está em ``docs/metodologia/noite-eleitoral.md``.
"""

from datetime import date

from pydantic import AwareDatetime, Field

from contratos.base import Metadados, ModeloContrato
from contratos.previsao import CamaraCongresso, PontoDistribuicao, Probabilidade


class ProjecaoCorridaNoite(ModeloContrato):
    """Projeção de uma corrida num instante da contagem."""

    id: str = Field(pattern=r"^[A-Z]{2}-(\d{2}|S|S-especial)$")
    camara: CamaraCongresso
    votos_contados: int = Field(ge=0)
    votos_esperados: float | None = Field(ge=0)
    """Estimativa do total final de votos (contados mais por contar); ``None`` quando a
    fonte não diz quanto falta e não há eleição de referência para o estimar."""

    fracao_contada: float | None = Field(ge=0.0, le=1.0)
    """Votos contados a dividir pelos votos esperados."""

    unidades_com_votos: int = Field(ge=0)
    margem_contada: float | None
    """Margem D-R dos votos já contados; ``None`` sem votos."""

    margem_prior: float
    """Margem prevista na previsão congelada."""

    margem_projetada: float
    margem_p10: float
    margem_p90: float
    prob_d: float = Probabilidade
    prob_d_prior: float = Probabilidade
    decidida: bool
    """Corrida sem disputa entre os dois lados na previsão (fica com o vencedor certo)."""


class ResumoCamaraNoite(ModeloContrato):
    """Controlo e lugares de uma câmara, incluindo os lugares que não vão a votos."""

    camara: CamaraCongresso
    lugares_total: int = Field(gt=0)
    maioria: int = Field(gt=0)
    prob_controlo_d: float = Probabilidade
    prob_controlo_r: float = Probabilidade
    prob_controlo_d_prior: float = Probabilidade
    lugares_d_media: float
    lugares_d_p10: int
    lugares_d_mediana: int
    lugares_d_p90: int
    corridas_com_votos: int = Field(ge=0)
    distribuicao: tuple[PontoDistribuicao, ...]


class DesvioNacionalNoite(ModeloContrato):
    """Quanto os votos contados se afastam, em média, da previsão congelada."""

    media: float
    """Desvio nacional estimado em pontos de margem D-R (positivo: melhor para D)."""

    desvio_padrao: float = Field(ge=0)
    corridas_informativas: int = Field(ge=0)


class ProjecaoNoite(ModeloContrato):
    """Projeção completa num instante: corridas, câmaras e desvio nacional."""

    metadados: Metadados
    ano: int
    instante: AwareDatetime
    """Instante dos resultados usados (o da recolha, ou o original numa repetição)."""

    corte_prior: date
    """Data de corte da previsão congelada usada como ponto de partida."""

    prior_congelado: bool = True
    """``False`` quando o ponto de partida é uma previsão ainda não congelada (por exemplo,
    um ensaio antes de 1 de novembro)."""

    reconstruido: bool = False
    """``True`` quando os resultados parciais são uma reconstrução (ensaio ou repetição) e
    não a contagem real da noite."""

    simulacoes: int = Field(gt=0)
    semente: int
    desvio_nacional: DesvioNacionalNoite
    camara: ResumoCamaraNoite
    senado: ResumoCamaraNoite
    corridas: tuple[ProjecaoCorridaNoite, ...]
    notas: tuple[str, ...]


# --- Evolução ao longo da noite (gráficos) --------------------------------------------


class PontoNoiteCamara(ModeloContrato):
    """Resumo de uma câmara num instante da noite."""

    prob_controlo_d: float = Probabilidade
    prob_controlo_r: float = Probabilidade
    lugares_d_mediana: int
    lugares_d_p10: int
    lugares_d_p90: int
    corridas_com_votos: int = Field(ge=0)


class PontoNoiteCorrida(ModeloContrato):
    """Uma corrida com votos contados num instante da noite."""

    id: str = Field(pattern=r"^[A-Z]{2}-(\d{2}|S|S-especial)$")
    prob_d: float = Probabilidade
    margem_projetada: float
    margem_p10: float
    margem_p90: float
    """Intervalo de 80% da margem final (o mesmo de ``ProjecaoCorridaNoite``)."""

    fracao_contada: float | None = Field(ge=0.0, le=1.0)


class PontoNoite(ModeloContrato):
    """Uma projeção reduzida ao necessário para desenhar a evolução da noite."""

    instante: AwareDatetime
    """Instante dos resultados usados (o mesmo de ``ProjecaoNoite.instante``)."""

    gerado_em: AwareDatetime
    desvio_nacional: float
    votos_contados: int = Field(ge=0)
    camara: PontoNoiteCamara
    senado: PontoNoiteCamara
    corridas: tuple[PontoNoiteCorrida, ...]
    """Só as corridas que já têm votos contados."""


class HistoricoNoite(ModeloContrato):
    """Pontos por ordem cronológica (o mais recente no fim), um por projeção guardada.

    Para o ficheiro não crescer sem limite ao longo da noite, dois pontos guardados
    seguidos distam pelo menos ``intervalo_minutos``, exceto os dois últimos: o último
    ponto é sempre a projeção mais recente e substitui-se até haver um intervalo completo.
    """

    metadados: Metadados
    ano: int
    corte_prior: date
    prior_congelado: bool
    reconstruido: bool
    intervalo_minutos: int = Field(gt=0)
    pontos: tuple[PontoNoite, ...] = Field(min_length=1)
