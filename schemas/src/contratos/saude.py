"""Saúde da recolha de resultados na noite eleitoral.

A recolha (``pipeline.jobs.resultados``) escreve ``saude.json`` a cada ciclo e publica-o na
Release ``resultados-2026`` a cada poucos minutos, ou logo que um alerta muda. O vigia lê-o
para abrir avisos; o Worker e o site leem-no para mostrar, por estado, que a fonte está
atrasada.
"""

from datetime import date
from typing import Annotated

from pydantic import AwareDatetime, Field, StringConstraints

from contratos.base import Metadados, ModeloContrato

ChaveRecolha = Annotated[str, StringConstraints(pattern=r"^[A-Z]{2}(-manual)?$")]
"""O estado (``TX``) ou a entrada manual sobreposta a esse estado (``TX-manual``)."""


class SaudeEstado(ModeloContrato):
    ultimo_sucesso: AwareDatetime | None
    """Último ciclo em que a fonte respondeu com um ficheiro válido (novo ou igual)."""

    ultima_alteracao: AwareDatetime | None
    """Último ciclo em que a fonte trouxe dados novos."""

    falhas_seguidas: int = Field(ge=0)
    ultimo_erro: str | None
    """Mensagem técnica da última falha, para quem acompanha a recolha."""

    apurado: bool
    """Todas as corridas do estado com todas as unidades apuradas."""

    alerta: str | None
    """Motivo curto quando o estado precisa de atenção (falhas seguidas, ou fonte parada com
    a contagem por acabar); ``None`` quando está tudo bem."""


class SaudeRecolha(ModeloContrato):
    metadados: Metadados
    data_eleicao: date
    estados: dict[ChaveRecolha, SaudeEstado]
