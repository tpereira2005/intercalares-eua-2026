"""Contratos de dados partilhados entre o pipeline, a API e o site.

Os modelos pydantic deste pacote são a única fonte de verdade. A partir deles
geram-se o JSON Schema (``schemas/json``) e os tipos TypeScript
(``packages/contratos``). Ver ``docs/contratos.md``.
"""

from contratos.base import Fonte, Metadados, ModeloContrato
from contratos.estados import CodigoEstado

__all__ = ["CodigoEstado", "Fonte", "Metadados", "ModeloContrato"]
