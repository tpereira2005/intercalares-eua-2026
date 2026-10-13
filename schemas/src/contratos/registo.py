"""Registo dos modelos exportados para JSON Schema e TypeScript.

Para publicar um contrato novo, acrescenta-o a ``MODELOS``.
"""

from pydantic import BaseModel

from contratos.base import Fonte, Metadados
from contratos.previsao import PrevisaoCongresso
from contratos.voto_antecipado import VotoAntecipadoEstado
from contratos.voto_antecipado_agregado import VotoAntecipadoAgregado, VotoAntecipadoNacional

MODELOS: tuple[type[BaseModel], ...] = (
    Fonte,
    Metadados,
    VotoAntecipadoEstado,
    VotoAntecipadoAgregado,
    VotoAntecipadoNacional,
    PrevisaoCongresso,
)
