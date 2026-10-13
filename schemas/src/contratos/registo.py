"""Registo dos modelos exportados para JSON Schema e TypeScript.

Para publicar um contrato novo, acrescenta-o a ``MODELOS``.
"""

from pydantic import BaseModel

from contratos.base import Fonte, Metadados
from contratos.voto_antecipado import VotoAntecipadoEstado

MODELOS: tuple[type[BaseModel], ...] = (Fonte, Metadados, VotoAntecipadoEstado)
