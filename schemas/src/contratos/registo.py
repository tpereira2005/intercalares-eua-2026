"""Registo dos modelos exportados para JSON Schema e TypeScript.

Para publicar um contrato novo, acrescenta-o a ``MODELOS``.
"""

from pydantic import BaseModel

from contratos.base import Fonte, Metadados
from contratos.chamadas import ChamadasRedacoes
from contratos.idade import DiagnosticoIdade
from contratos.noite import HistoricoNoite, ProjecaoNoite
from contratos.previsao import (
    AlteracoesPrevisao,
    AvaliacaoPrevisao,
    CenariosPrevisao,
    HistoricoPrevisao,
    PrevisaoCongresso,
)
from contratos.resultados import ResultadosEstado, ResultadosNacional, ResultadosParciais
from contratos.sondagens import SondagensCongresso
from contratos.voto_antecipado import VotoAntecipadoEstado
from contratos.voto_antecipado_agregado import VotoAntecipadoAgregado, VotoAntecipadoNacional

MODELOS: tuple[type[BaseModel], ...] = (
    Fonte,
    Metadados,
    VotoAntecipadoEstado,
    VotoAntecipadoAgregado,
    VotoAntecipadoNacional,
    DiagnosticoIdade,
    PrevisaoCongresso,
    HistoricoPrevisao,
    AvaliacaoPrevisao,
    AlteracoesPrevisao,
    CenariosPrevisao,
    ResultadosEstado,
    ResultadosNacional,
    ResultadosParciais,
    ChamadasRedacoes,
    ProjecaoNoite,
    HistoricoNoite,
    SondagensCongresso,
)
