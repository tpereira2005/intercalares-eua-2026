"""Contratos do rastreador de voto antecipado (por estado, com o módulo demográfico).

Um ficheiro ``VotoAntecipadoEstado`` por estado e por atualização. Contém só contagens
agregadas: nunca dados de eleitores individuais. As taxas e quotas derivam das contagens
e vêm já calculadas para que o site e a API não reimplementem a metodologia.
"""

from datetime import date
from typing import Literal

from pydantic import ConfigDict, Field

from contratos.base import Metadados, ModeloContrato
from contratos.estados import CodigoEstado

Faixa = Literal[
    "18-24", "25-29", "30-39", "40-49", "50-64", "65-74", "75+", "desconhecida", "total"
]
"""Faixa etária canónica (idade no fim do ano da eleição)."""

FaixaLarga = Literal["18-29", "30-49", "50-64", "65+", "desconhecida", "total"]
"""Agregação da faixa canónica usada nos mapas."""

Partido = Literal["dem", "rep", "nao_afiliado", "outro", "total"]
"""Partido de registo do eleitor (não é o voto)."""

ModalidadeVoto = Literal["correio", "presencial", "total"]

GrupoHistorico = Literal[
    "antecipado_na_referencia",
    "dia_eleicao_na_referencia",
    "absteve_se_na_referencia",
    "recenseado_apos_referencia",
    "sem_historico",
]
"""O que o eleitor fez na eleição de referência (a anterior do mesmo tipo)."""

Dimensao = Literal["partido", "raca", "etnia", "genero", "modalidade"]

Contagem = Field(ge=0)


class CicloVotoAntecipado(ModeloContrato):
    """Uma eleição comparável (2026 ou um ano de referência)."""

    ano: int
    tipo: Literal["intercalar", "presidencial"]
    data_eleicao: date
    inicio_presencial_dias_antes: int | None
    """Primeiro dia do voto antecipado presencial, em dias antes da eleição."""

    fim_presencial_dias_antes: int | None
    ano_referencia_historico: int | None
    """Eleição usada para classificar o histórico de voto de cada eleitor."""

    registados: int = Contagem
    votos_antecipados: int = Contagem
    """Total de votos antecipados: final nos anos anteriores, acumulado até agora em 2026."""

    notas: tuple[str, ...]
    """Diferenças de regras ou de contexto que afetam a comparação."""


class PontoSerie(ModeloContrato):
    """Votos acumulados até um dia do ciclo."""

    ano: int
    dias_antes: int
    faixa: Faixa
    partido: Partido
    modalidade: ModalidadeVoto
    votos: int = Contagem
    registados: int = Contagem


class LinhaComparacao(ModeloContrato):
    """2026 face a um ano de referência, no mesmo dia do ciclo, para uma faixa etária."""

    # Campos acrescentados depois da primeira versão: opcionais no esquema JSON, para que os
    # ficheiros já publicados continuem válidos (os modelos pydantic usam o valor por omissão).
    model_config = ConfigDict(json_schema_serialization_defaults_required=False)

    ano_base: int
    faixa: Faixa
    votos: int = Contagem
    registados: int = Contagem
    votos_base: int = Contagem
    registados_base: int = Contagem
    quota: float
    """Quota da faixa no voto antecipado (composição)."""

    quota_base: float
    quota_recenseamento: float
    """Quota da faixa nos eleitores recenseados."""

    quota_recenseamento_base: float
    taxa: float | None
    """Percentagem dos recenseados da faixa que já votou (participação)."""

    taxa_base: float | None
    esperado: float
    """Votos esperados: recenseados de hoje x taxa do ano de referência no mesmo dia."""

    desvio: float | None
    """Votos observados / esperados - 1. Positivo: acima do ritmo do ano de referência."""

    desvio_min: float | None = None
    desvio_max: float | None = None
    """Menor e maior desvio com a taxa de referência lida até 3 dias antes ou depois do
    mesmo dia do ciclo: a sensibilidade ao alinhamento do calendário. O intervalo das
    barras é o envelope destes valores nas referências intercalares (2018 e 2022), que é
    a medida honesta da incerteza (ver a metodologia)."""

    efeito_recenseamento: float
    """Parte da variação da quota explicada por haver mais ou menos recenseados da faixa."""

    efeito_participacao: float
    """Parte da variação da quota explicada por a faixa votar mais ou menos até este dia."""


class LinhaHistorico(ModeloContrato):
    """Contributo de um grupo histórico para a participação de uma faixa até ao dia."""

    ano: int
    ano_referencia: int
    faixa: Faixa
    grupo: GrupoHistorico
    votos: int = Contagem
    registados: int = Contagem
    """Recenseados da faixa (todos os grupos)."""

    contributo: float | None
    """votos / registados: a soma dos grupos dá a taxa de participação da faixa."""


class LinhaReserva(ModeloContrato):
    """Eleitores que votaram na eleição de referência e ainda não votaram até ao dia."""

    ano: int
    faixa: Faixa
    partido: Partido
    habituais: int = Contagem
    ja_votaram: int = Contagem
    restantes: int = Contagem


class LinhaGeografia(ModeloContrato):
    ano: int
    nivel: Literal["condado", "distrito"]
    codigo: str
    """FIPS de cinco dígitos (condado) ou número do distrito no mapa de 2026."""

    nome: str
    faixa: FaixaLarga
    votos: int = Contagem
    registados: int = Contagem


class LinhaHistoricoGeografia(ModeloContrato):
    """Contributo de um grupo histórico para a participação de uma unidade geográfica e
    faixa larga até ao dia (o mesmo dia do ciclo em todos os anos, com o mapa de 2026)."""

    ano: int
    ano_referencia: int
    nivel: Literal["condado", "distrito"]
    codigo: str
    """FIPS de cinco dígitos (condado) ou número do distrito no mapa de 2026."""

    nome: str
    faixa: FaixaLarga
    grupo: GrupoHistorico
    votos: int = Contagem
    registados: int = Contagem
    """Recenseados da unidade e faixa (todos os grupos)."""

    contributo: float | None
    """votos / registados: a soma dos grupos dá a taxa de participação da unidade e faixa."""


class LinhaCruzamento(ModeloContrato):
    ano: int
    dimensao: Dimensao
    faixa: Faixa
    categoria: str
    votos: int = Contagem
    registados: int = Contagem
    """Para a modalidade, o denominador é o total da faixa."""


class VotoAntecipadoEstado(ModeloContrato):
    """Rastreador de voto antecipado de um estado, com a análise por idade."""

    # Campo acrescentado depois da primeira versão: opcional no esquema JSON, para que os
    # ficheiros já publicados continuem válidos (os modelos pydantic usam o valor por omissão).
    model_config = ConfigDict(json_schema_serialization_defaults_required=False)

    metadados: Metadados
    estado: CodigoEstado
    ano: int
    dados_ate: date
    """Último dia com votos no ficheiro da fonte."""

    dias_antes: int
    """Dias entre ``dados_ate`` e a eleição: o ponto do ciclo usado nas comparações."""

    ciclos: tuple[CicloVotoAntecipado, ...]
    serie: tuple[PontoSerie, ...]
    comparacao: tuple[LinhaComparacao, ...]
    historico: tuple[LinhaHistorico, ...]
    reserva: tuple[LinhaReserva, ...]
    geografia: tuple[LinhaGeografia, ...]
    cruzamentos: tuple[LinhaCruzamento, ...]
    avisos: tuple[str, ...]
    """Limitações conhecidas desta atualização, em PT-PT, para mostrar no site."""

    historico_geografia: tuple[LinhaHistoricoGeografia, ...] = ()
    """Histórico de voto (habituais, antecipação, voto novo) por condado e distrito e por
    faixa larga. Vazio nos anos sem histórico individual de referência."""
