"""Contratos dos resultados da noite eleitoral, a partir dos feeds oficiais dos estados.

Cada estado publica um ``ResultadosEstado`` com as corridas acompanhadas (Senado e
distritos da Câmara), os votos por candidato e o grau de apuramento. Os números são os
da fonte oficial, tal como estão no momento da recolha: não há projeções nem chamadas de
vencedor neste contrato.
"""

from datetime import date
from typing import Literal, Self

from pydantic import AwareDatetime, Field, model_validator

from contratos.base import Metadados, ModeloContrato
from contratos.estados import CodigoEstado

Contagem = Field(ge=0)

Cargo = Literal["senado", "camara", "governador"]

PartidoCandidato = Literal["dem", "rep", "outro"]
"""Os partidos são só rótulos: nenhuma regra trata um de forma diferente de outro."""

ModalidadeResultado = Literal[
    "dia_eleicao", "antecipado_presencial", "correio", "provisorio", "outro"
]
"""Como o voto foi emitido, quando a fonte separa os votos por tipo."""

UnidadeApuramento = Literal["seccao", "condado", "municipio"]
"""O que a fonte conta como unidade com resultados (secções de voto, condados ou, na
Nova Inglaterra, municípios)."""


class VotosModalidade(ModeloContrato):
    modalidade: ModalidadeResultado
    votos: int = Contagem


class Candidatura(ModeloContrato):
    id: str = Field(min_length=1)
    """Identificador estável dentro da corrida (o da fonte, ou o nome normalizado)."""

    nome: str = Field(min_length=1)
    partido: PartidoCandidato
    partido_fonte: str | None = None
    """Rótulo do partido tal como a fonte o escreve (ex.: "LIB", "Green")."""

    votos: int = Contagem
    por_modalidade: tuple[VotosModalidade, ...] = ()
    """Votos no estado por tipo de voto, quando a fonte os separa (vazio se não)."""


class VotosCandidato(ModeloContrato):
    candidato: str
    """``Candidatura.id``."""

    votos: int = Contagem


class ResultadoGeografico(ModeloContrato):
    """Resultado de uma corrida num condado (ou município) do estado."""

    nivel: Literal["condado", "municipio"]
    codigo: str = Field(min_length=1)
    """FIPS de 5 dígitos para condados; código da fonte para municípios."""

    nome: str
    votos: tuple[VotosCandidato, ...]
    total: int = Contagem
    unidades_reportadas: int | None = Field(default=None, ge=0)
    unidades_totais: int | None = Field(default=None, ge=0)


class Corrida(ModeloContrato):
    id: str = Field(pattern=r"^[A-Z]{2}-(S|G|\d{2})(-especial)?$")
    """Os mesmos identificadores da previsão (``PrevisaoCongresso``): ``NC-S``, ``PA-08``,
    ``AK-00``, ``OH-S-especial``; e ``XX-G`` para governador."""

    estado: CodigoEstado
    cargo: Cargo
    distrito: int | None = Field(default=None, ge=0)
    """Distrito da Câmara (0 nos estados com um só distrito); ``None`` nos outros cargos."""

    especial: bool = False
    nome_fonte: str
    """Nome da corrida tal como a fonte o escreve."""

    candidatos: tuple[Candidatura, ...] = Field(min_length=1)
    total: int = Contagem
    """Total de votos válidos na corrida, incluindo candidatos não nomeados (write-in)."""

    unidades_reportadas: int | None = Field(default=None, ge=0)
    unidades_totais: int | None = Field(default=None, ge=0)
    tipo_unidade: UnidadeApuramento | None = None
    geografia: tuple[ResultadoGeografico, ...] = ()
    notas: tuple[str, ...] = ()

    @model_validator(mode="after")
    def _coerente(self) -> Self:
        if (self.cargo == "camara") != (self.distrito is not None):
            msg = f"{self.id}: só as corridas à Câmara têm distrito"
            raise ValueError(msg)
        if sum(c.votos for c in self.candidatos) > self.total:
            msg = f"{self.id}: a soma dos candidatos excede o total"
            raise ValueError(msg)
        if len({c.id for c in self.candidatos}) != len(self.candidatos):
            msg = f"{self.id}: candidatos repetidos"
            raise ValueError(msg)
        r, t = self.unidades_reportadas, self.unidades_totais
        if r is not None and t is not None and r > t:
            msg = f"{self.id}: mais unidades reportadas do que existentes"
            raise ValueError(msg)
        ids = {c.id for c in self.candidatos}
        for g in self.geografia:
            if not {v.candidato for v in g.votos} <= ids:
                msg = f"{self.id}: candidato desconhecido em {g.codigo}"
                raise ValueError(msg)
        return self


class ResultadosEstado(ModeloContrato):
    metadados: Metadados
    estado: CodigoEstado
    data_eleicao: date
    atualizado_fonte: AwareDatetime | None = None
    """Hora da última atualização declarada pela fonte, quando a fonte a indica."""

    corridas: tuple[Corrida, ...]
    avisos: tuple[str, ...] = ()

    @model_validator(mode="after")
    def _corridas_do_estado(self) -> Self:
        if any(c.estado != self.estado for c in self.corridas):
            msg = "Corrida de outro estado"
            raise ValueError(msg)
        if len({c.id for c in self.corridas}) != len(self.corridas):
            msg = "Corridas repetidas"
            raise ValueError(msg)
        return self


class LinhaCorridaNacional(ModeloContrato):
    """Resumo de uma corrida para o painel da noite eleitoral."""

    id: str
    estado: CodigoEstado
    cargo: Cargo
    distrito: int | None
    ficheiro: str
    """Ficheiro do estado com o detalhe (ex.: ``nc.json``)."""

    atualizado_fonte: AwareDatetime | None
    total: int = Contagem
    votos_dem: int = Contagem
    votos_rep: int = Contagem
    votos_outros: int = Contagem
    apuramento: float | None = Field(default=None, ge=0, le=1)
    """Unidades reportadas / unidades totais, quando a fonte as indica."""


class ResultadosNacional(ModeloContrato):
    metadados: Metadados
    data_eleicao: date
    corridas: tuple[LinhaCorridaNacional, ...]
    avisos: tuple[str, ...] = ()


class ContagemModo(ModeloContrato):
    modo: ModalidadeResultado
    votos_d: int = Contagem
    votos_r: int = Contagem
    votos_outros: int = Contagem


class UnidadeContagem(ModeloContrato):
    """Votos de uma corrida numa unidade geográfica, no formato do estimador ao vivo."""

    corrida: str = Field(pattern=r"^[A-Z]{2}-(S|\d{2})(-especial)?$")
    """Identificador da previsão (só Senado e Câmara)."""

    unidade: str = Field(pattern=r"^(\d{5}|total|[A-Z0-9]{1,12})$")
    """FIPS do condado, código do município, ou ``total`` quando a fonte só dá o total.
    Um condado partido por vários distritos aparece uma vez em cada distrito."""

    votos_d: int = Contagem
    """Candidatos com o rótulo democrata."""

    votos_r: int = Contagem
    votos_outros: int = Contagem
    por_modo: tuple[ContagemModo, ...] = ()
    percentagem_contada: float | None = Field(default=None, ge=0, le=1)
    """Só quando a fonte publica a fração do voto esperado (nenhuma das atuais o faz)."""

    seccoes_reportadas: int | None = Field(default=None, ge=0)
    seccoes_totais: int | None = Field(default=None, ge=0)
    atualizado_em: AwareDatetime | None = None


class ResultadosParciais(ModeloContrato):
    """Um instante da contagem em todos os estados acompanhados (entrada do Modelo C)."""

    metadados: Metadados
    ano: int
    instante: AwareDatetime
    reconstruido: bool = False
    """``True`` no ensaio: a ordem de chegada dos condados foi reconstruída a partir do
    resultado final, porque as fontes não guardam os retratos intermédios."""

    unidades: tuple[UnidadeContagem, ...]
