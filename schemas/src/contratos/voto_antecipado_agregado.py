"""Contratos do voto antecipado nos estados sem ficheiro de eleitores gratuito, e nacional.

``VotoAntecipadoAgregado`` serve os estados onde só há boletins (sem os recenseados de cada
grupo) ou totais por condado. Por isso compara **votos com votos** no mesmo dia do ciclo,
não taxas de participação. As dimensões que a fonte não tem (por exemplo, a idade no
Maine) não aparecem: ``dimensoes`` diz quais existem.

``VotoAntecipadoNacional`` resume todos os estados acompanhados para a página inicial.
"""

from datetime import date
from typing import Literal

from pydantic import Field

from contratos.base import Metadados, ModeloContrato
from contratos.estados import CodigoEstado
from contratos.voto_antecipado import Faixa, FaixaLarga, ModalidadeVoto, Partido

Contagem = Field(ge=0)

DimensaoAgregada = Literal["faixa", "partido", "modalidade", "condado", "distrito"]

Granularidade = Literal["boletim", "condado"]
"""``boletim``: um registo por boletim (contagens exatas por dia do ciclo).
``condado``: só totais por condado publicados pela fonte, sem histórico diário próprio."""


class CicloAgregado(ModeloContrato):
    ano: int
    tipo: Literal["intercalar", "presidencial"]
    data_eleicao: date
    votos: int = Contagem
    """Final nos anos anteriores; acumulado até ``dias_antes`` em 2026."""

    votos_mesmo_dia: int | None = Field(default=None, ge=0)
    """Votos até ao mesmo dia do ciclo que o ano atual (só nos anos de comparação)."""

    pedidos: int | None = Field(default=None, ge=0)
    """Boletins por correspondência pedidos até ao mesmo dia, quando a fonte os tem."""

    notas: tuple[str, ...]


class PontoSerieAgregado(ModeloContrato):
    """Votos acumulados até um dia do ciclo."""

    ano: int
    dias_antes: int
    faixa: Faixa
    partido: Partido
    modalidade: ModalidadeVoto
    votos: int = Contagem


class LinhaComparacaoAgregada(ModeloContrato):
    """Uma categoria em 2026 face ao ano de referência, no mesmo dia do ciclo."""

    ano_base: int
    dimensao: Literal["faixa", "partido", "modalidade"]
    categoria: str
    votos: int = Contagem
    votos_base: int = Contagem
    quota: float | None
    """Quota da categoria nos votos antecipados de 2026 (composição)."""

    quota_base: float | None
    ritmo: float | None
    """votos / votos_base - 1: positivo quando a categoria vai à frente do ano de referência."""


class LinhaGeografiaAgregada(ModeloContrato):
    ano: int
    nivel: Literal["condado", "distrito"]
    codigo: str
    """FIPS de cinco dígitos (condado) ou número do distrito em vigor em 2026."""

    nome: str
    partido: Partido
    votos: int = Contagem
    faixa: FaixaLarga = "total"
    """Faixa larga, nos estados com idade (Pensilvânia). As linhas por faixa têm
    ``partido = "total"``; as linhas por partido têm ``faixa = "total"``."""


class LinhaPedidos(ModeloContrato):
    """Boletins por correspondência pedidos, devolvidos e por devolver até ao dia."""

    ano: int
    faixa: Faixa
    partido: Partido
    pedidos: int = Contagem
    devolvidos: int = Contagem
    pendentes: int = Contagem


class VotoAntecipadoAgregado(ModeloContrato):
    metadados: Metadados
    estado: CodigoEstado
    ano: int
    dados_ate: date
    dias_antes: int
    granularidade: Granularidade
    dimensoes: tuple[DimensaoAgregada, ...]
    """Dimensões que a fonte permite analisar neste estado."""

    modalidades: tuple[Literal["correio", "presencial"], ...]
    """Modalidades que a fonte cobre (na Pensilvânia, por exemplo, só há correio)."""

    ciclos: tuple[CicloAgregado, ...]
    serie: tuple[PontoSerieAgregado, ...]
    comparacao: tuple[LinhaComparacaoAgregada, ...]
    geografia: tuple[LinhaGeografiaAgregada, ...]
    pedidos: tuple[LinhaPedidos, ...]
    avisos: tuple[str, ...]


class LinhaEstadoNacional(ModeloContrato):
    """Resumo de um estado para a página inicial."""

    estado: CodigoEstado
    ficheiro: str
    """Nome do ficheiro completo do estado, publicado ao lado deste."""

    granularidade: Granularidade
    dados_ate: date
    dias_antes: int
    modalidades: tuple[Literal["correio", "presencial"], ...]
    votos: int = Contagem
    ano_base: int | None
    votos_base: int | None = Field(ge=0)
    """Votos do ano de referência até ao mesmo dia do ciclo."""

    ritmo: float | None
    quota_dem: float | None
    """Quota de eleitores registados como democratas nos votos (registo, não voto)."""

    quota_rep: float | None
    quota_dem_base: float | None
    quota_rep_base: float | None
    quota_65_mais: float | None
    """Quota de eleitores com 65 ou mais anos (só nos estados com idade)."""

    quota_65_mais_base: float | None


class EstadoSemDados(ModeloContrato):
    """Estado prioritário que o site não acompanha, e porquê."""

    estado: CodigoEstado
    motivo: Literal["bloqueado", "sem_fonte_gratuita"]
    """``bloqueado``: a fonte oficial existe, mas recusa pedidos automáticos (não contornamos
    o bloqueio). ``sem_fonte_gratuita``: não há dados oficiais gratuitos."""

    nota: str
    """Explicação curta em PT-PT, para mostrar no site."""


class VotoAntecipadoNacional(ModeloContrato):
    metadados: Metadados
    ano: int
    estados: tuple[LinhaEstadoNacional, ...]
    votos: int = Contagem
    """Soma dos estados acompanhados (não é um total nacional)."""

    avisos: tuple[str, ...]
    estados_sem_dados: tuple[EstadoSemDados, ...] = ()
    """Estados prioritários sem ficheiro, para o site não os mostrar como "ainda sem dados"."""
