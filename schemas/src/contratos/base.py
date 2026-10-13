"""Modelos base comuns a todos os contratos de dados."""

from collections.abc import Callable
from typing import Any

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, HttpUrl

VERSAO_ESQUEMA = "0.1.0"
"""Versão semântica dos contratos. Sobe sempre que um contrato muda de forma incompatível."""


class ModeloContrato(BaseModel):
    """Base de todos os contratos: imutável e sem campos desconhecidos.

    Rejeitar campos extra garante que uma alteração no formato de uma fonte
    falha na validação em vez de passar despercebida.
    """

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        str_strip_whitespace=True,
        use_attribute_docstrings=True,
        json_schema_serialization_defaults_required=True,
    )


def opcionais_no_esquema(*campos: str) -> Callable[[dict[str, Any]], None]:
    """``json_schema_extra`` que tira ``campos`` da lista de obrigatórios do esquema JSON.

    Para campos acrescentados depois de haver ficheiros publicados: o modelo pydantic usa o
    valor por omissão e os ficheiros antigos continuam válidos no site. Os outros campos
    do modelo mantêm a convenção (obrigatórios no esquema de serialização).
    """

    def ajustar(esquema: dict[str, Any]) -> None:
        obrigatorios = esquema.get("required")
        if isinstance(obrigatorios, list):
            esquema["required"] = [c for c in obrigatorios if c not in campos]

    return ajustar


class Fonte(ModeloContrato):
    """Origem de um conjunto de dados, citada em cada número publicado."""

    nome: str = Field(min_length=1)
    """Nome legível da fonte, por exemplo "North Carolina State Board of Elections"."""

    url: HttpUrl
    """Endereço exato de onde os dados foram obtidos."""

    licenca: str | None = None
    """Licença ou termos de utilização, quando conhecidos."""

    obtida_em: AwareDatetime
    """Momento da recolha, sempre com fuso horário."""


class Metadados(ModeloContrato):
    """Cabeçalho comum a todos os ficheiros de dados publicados."""

    versao_esquema: str = Field(default=VERSAO_ESQUEMA, pattern=r"^\d+\.\d+\.\d+$")
    """Versão dos contratos com que o ficheiro foi produzido."""

    gerado_em: AwareDatetime
    """Momento em que o pipeline gerou o ficheiro."""

    fontes: tuple[Fonte, ...] = Field(min_length=1)
    """Todas as fontes usadas para produzir o ficheiro."""
