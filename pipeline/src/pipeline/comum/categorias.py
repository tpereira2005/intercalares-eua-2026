"""Categorias normalizadas, comuns a todos os estados.

Cada conector traduz os códigos da sua fonte para estas categorias. A análise nunca vê
códigos estaduais, e nenhuma regra trata um partido de forma diferente de outro: os
partidos são apenas valores de uma coluna (ver o teste de troca de rótulos).
"""

from enum import StrEnum


class Partido(StrEnum):
    DEM = "dem"
    REP = "rep"
    NAO_AFILIADO = "nao_afiliado"
    OUTRO = "outro"


class Raca(StrEnum):
    BRANCA = "branca"
    NEGRA = "negra"
    ASIATICA = "asiatica"
    NATIVA = "nativa"
    HAVAIANA_PACIFICO = "havaiana_pacifico"
    MULTIRRACIAL = "multirracial"
    OUTRA = "outra"
    NAO_INDICADA = "nao_indicada"


class Etnia(StrEnum):
    HISPANICA = "hispanica"
    NAO_HISPANICA = "nao_hispanica"
    NAO_INDICADA = "nao_indicada"


class Genero(StrEnum):
    FEMININO = "feminino"
    MASCULINO = "masculino"
    NAO_INDICADO = "nao_indicado"


class Modalidade(StrEnum):
    CORREIO = "correio"
    PRESENCIAL = "presencial"
    """Voto antecipado presencial (na Carolina do Norte, "one-stop")."""

    NAO_VOTOU = "nao_votou"
    """Recenseado que ainda não votou antecipadamente (só existe nos cubos)."""


class EstadoBoletim(StrEnum):
    ACEITE = "aceite"
    PENDENTE = "pendente"
    """Devolvido mas ainda em verificação ou correção ("cure")."""

    REJEITADO = "rejeitado"
    ANULADO = "anulado"
    """Substituído, cancelado ou não usado: não conta como voto."""

    POR_DEVOLVER = "por_devolver"
    DESCONHECIDO = "desconhecido"


ESTADOS_DEVOLVIDOS = (
    EstadoBoletim.ACEITE,
    EstadoBoletim.PENDENTE,
    EstadoBoletim.REJEITADO,
    EstadoBoletim.DESCONHECIDO,
)
"""Estados que contam como "já votou" na comparação entre ciclos.

Incluímos os rejeitados porque nos ficheiros históricos o estado é o final, enquanto em
2026 muitos boletins ainda estão por verificar. Contar "boletins devolvidos" é a única
definição igual nos dois casos.
"""


class GrupoHistorico(StrEnum):
    """Comportamento de cada eleitor na eleição de referência (a anterior do mesmo tipo)."""

    ANTECIPADO_NA_REFERENCIA = "antecipado_na_referencia"
    """Votou antecipadamente (correio ou presencial): comportamento habitual."""

    DIA_ELEICAO_NA_REFERENCIA = "dia_eleicao_na_referencia"
    """Votou no dia da eleição: se agora votou cedo, é antecipação, não voto novo."""

    ABSTEVE_SE_NA_REFERENCIA = "absteve_se_na_referencia"
    """Estava recenseado e não votou: voto novo ou de baixa propensão."""

    RECENSEADO_APOS_REFERENCIA = "recenseado_apos_referencia"
    """Recenseou-se depois da eleição de referência: eleitor novo no estado ou no registo."""

    SEM_HISTORICO = "sem_historico"
    """Não há histórico individual para a eleição de referência."""


class MetodoHistorico(StrEnum):
    ANTECIPADO = "antecipado"
    DIA_ELEICAO = "dia_eleicao"
