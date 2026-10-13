"""Contrato da previsão própria para a Câmara e o Senado.

Um ficheiro ``PrevisaoCongresso`` por atualização. Todas as margens estão em pontos
percentuais do voto total, sempre Democrata menos Republicano (D-R): positivo favorece o
lado democrata, negativo o republicano. As probabilidades estão entre 0 e 1. A
metodologia está em ``docs/metodologia/previsao.md``.
"""

from datetime import date
from typing import Literal

from pydantic import Field

from contratos.base import Metadados, ModeloContrato
from contratos.estados import CodigoEstado

Probabilidade = Field(ge=0.0, le=1.0)

CamaraCongresso = Literal["camara", "senado"]

FonteAmbiente = Literal["agregadores", "media_sondagens_voto_generico", "sondagens_senado"]
"""De onde vem o ambiente nacional: média dos agregadores publicados, a nossa média das
sondagens do voto genérico ou, sem voto genérico, a leitura implícita nas sondagens do
Senado (usada no backtest de 2024)."""

Lado = Literal["D", "R", "I"]


class AgregadorVotoGenerico(ModeloContrato):
    """Valor de um agregador público do voto genérico usado no ambiente nacional."""

    nome: str = Field(min_length=1)
    margem: float


class AmbienteNacional(ModeloContrato):
    """Margem nacional no voto para a Câmara (D-R) que serve de centro às simulações."""

    margem: float
    desvio_padrao: float = Field(gt=0)
    """Erro histórico (raiz do erro quadrático médio) das médias do voto genérico."""

    fonte: FonteAmbiente
    agregadores: tuple[AgregadorVotoGenerico, ...]


class PontoDistribuicao(ModeloContrato):
    """Probabilidade de o lado democrata ficar com exatamente ``lugares`` lugares."""

    lugares: int = Field(ge=0)
    probabilidade: float = Probabilidade


class ResumoCamara(ModeloContrato):
    """Controlo e distribuição de lugares de uma câmara.

    ``lugares_d_*`` contam o lado democrata, incluindo independentes que ocupam esse lado
    e, no Senado, os lugares que não vão a votos. O lado republicano é o complemento.
    """

    camara: CamaraCongresso
    lugares_total: int = Field(gt=0)
    maioria: int = Field(gt=0)
    prob_controlo_d: float = Probabilidade
    prob_controlo_r: float = Probabilidade
    """No Senado, 50-50 decide-se pelo partido do vice-presidente."""

    lugares_d_media: float
    lugares_d_p5: int
    lugares_d_p10: int
    lugares_d_mediana: int
    lugares_d_p90: int
    lugares_d_p95: int
    lugares_independentes_media: float
    """Lugares ganhos por independentes (de qualquer lado), em média."""

    lugares_fora_de_jogo_d: int = Field(ge=0)
    lugares_fora_de_jogo_r: int = Field(ge=0)
    limiar_nacional: float | None
    """Margem nacional a partir da qual o lado democrata passa a favorito ao controlo
    (abaixo dela o favorito é o lado republicano). ``None`` se nunca muda nas simulações."""

    distribuicao: tuple[PontoDistribuicao, ...]


class PrevisaoCorrida(ModeloContrato):
    """Previsão de uma corrida: um distrito da Câmara ou um lugar do Senado."""

    id: str = Field(pattern=r"^[A-Z]{2}-(\d{2}|S|S-especial)$")
    """``NC-01``, ``AK-00`` (distrito único), ``TX-S`` ou ``OH-S-especial``."""

    camara: CamaraCongresso
    estado: CodigoEstado
    candidato_d: str | None
    """Candidato do lado democrata (pode ser um independente, ver ``lado_d_independente``)."""

    candidato_r: str | None
    lado_d_independente: bool
    lado_r_independente: bool
    incumbente_recandidato: Lado | None
    """Partido do incumbente quando se recandidata; ``None`` em lugar aberto."""

    pvi: float
    """Cook PVI em pontos (D+ positivo), tal como publicado: a margem é o dobro."""

    decidida: Lado | None
    """Vencedor já certo (sem candidato de um dos lados)."""

    margem_fundamentos: float
    margem_sondagens: float | None
    institutos: int = Field(ge=0)
    """Número de institutos com sondagens na média (só no Senado)."""

    peso_sondagens: float = Probabilidade
    margem_prevista: float
    margem_p10: float
    margem_p90: float
    prob_d: float = Probabilidade
    """Probabilidade de vitória do lado democrata."""


class ParametrosFundamentos(ModeloContrato):
    """Parâmetros da regressão de fundamentos de uma câmara (anos anteriores apenas)."""

    camara: CamaraCongresso
    anos_treino: tuple[int, ...]
    observacoes: int = Field(gt=0)
    intercepto: float
    inclinacao_pvi: float
    incumbencia: float
    persistencia: float
    desvio_ano: float = Field(ge=0)
    desvio_regiao: float = Field(ge=0)
    desvio_corrida: float = Field(ge=0)


class ParametrosErroSondagens(ModeloContrato):
    """Erro histórico das médias de sondagens do Senado."""

    observacoes: int = Field(gt=0)
    erro_base: float = Field(ge=0)
    erro_por_instituto: float = Field(ge=0)
    desvio_ano: float = Field(ge=0)
    ligacao_nacional: float
    """Parte do erro do voto genérico que se transmite às sondagens do Senado."""


class Backtest(ModeloContrato):
    """O mesmo modelo aplicado a uma eleição passada, só com dados anteriores ao corte."""

    ano: int
    camara: CamaraCongresso
    corte: date
    ambiente_previsto: float
    ambiente_real: float
    fonte_ambiente: FonteAmbiente
    prob_controlo_d: float = Probabilidade
    prob_controlo_r: float = Probabilidade
    controlo_real: Literal["D", "R"]
    lugares_d_mediana: int
    lugares_d_p10: int
    lugares_d_p90: int
    lugares_d_reais: int
    corridas_avaliadas: int = Field(ge=0)
    corridas_erradas: tuple[str, ...]
    brier: float = Field(ge=0)
    vies_competitivas: float
    """Média de (previsto - real) nas corridas com margem prevista abaixo de 15 pontos."""

    erro_absoluto_competitivas: float = Field(ge=0)
    cobertura_80: float = Probabilidade
    """Fração das margens reais dentro do intervalo de 80% (o ideal é 0,8)."""


class PrevisaoCongresso(ModeloContrato):
    """Previsão completa: ambiente, câmaras, corridas, parâmetros e backtests."""

    metadados: Metadados
    ano: int
    data_eleicao: date
    corte: date
    """Só entram dados até este dia (exclusive)."""

    congelada: bool
    """Verdadeiro quando ``corte`` é a data final (dois dias antes da eleição)."""

    simulacoes: int = Field(gt=0)
    semente: int
    ambiente: AmbienteNacional
    camara: ResumoCamara
    senado: ResumoCamara
    corridas: tuple[PrevisaoCorrida, ...]
    fundamentos: tuple[ParametrosFundamentos, ...]
    erro_sondagens: ParametrosErroSondagens
    peso_voto_antecipado: float = Field(ge=0.0, le=1.0)
    """Peso do voto antecipado na previsão (0: só diagnóstico, ver a metodologia)."""

    backtests: tuple[Backtest, ...]
    notas: tuple[str, ...]
