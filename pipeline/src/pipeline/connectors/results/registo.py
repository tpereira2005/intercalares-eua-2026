"""Estados com resultados ao vivo e o conector de cada um.

Só entram fontes oficiais gratuitas, sem bloqueios a pedidos automáticos. Os sites de
resultados da Pensilvânia, Arizona, Texas, Ohio, Michigan e Nevada recusam pedidos
automáticos (ver ``docs/metodologia/resultados.md``); nesses estados entram só os condados
com fonte oficial aberta, sempre marcados como cobertura parcial.
"""

from contratos.estados import CodigoEstado
from pipeline.comum.condados import nomes
from pipeline.connectors.results.ak.conector import ConectorAK
from pipeline.connectors.results.clarity.conector import CAROLINA_DO_SUL, IOWA
from pipeline.connectors.results.comum import ConectorResultados
from pipeline.connectors.results.condados.conector import ConectorCondados
from pipeline.connectors.results.condados.harris import FonteHarris
from pipeline.connectors.results.fl.conector import ConectorFL
from pipeline.connectors.results.ga.conector import ConectorGA
from pipeline.connectors.results.nc.conector import ConectorNC

CONECTORES: dict[CodigoEstado, ConectorResultados] = {
    CodigoEstado.NC: ConectorNC(),
    CodigoEstado.FL: ConectorFL(),
    CodigoEstado.GA: ConectorGA(),
    CodigoEstado.SC: CAROLINA_DO_SUL,
    CodigoEstado.IA: IOWA,
    CodigoEstado.AK: ConectorAK(),
    CodigoEstado.TX: ConectorCondados(CodigoEstado.TX, (FonteHarris(),)),
}

DISTRITOS: dict[CodigoEstado, int] = {
    CodigoEstado.NC: 14,
    CodigoEstado.FL: 28,
    CodigoEstado.GA: 14,
    CodigoEstado.SC: 7,
    CodigoEstado.IA: 4,
    CodigoEstado.AK: 1,
    CodigoEstado.TX: 38,
}
"""Distritos da Câmara em 2026. Uma corrida sem oposição pode não aparecer no feed (na
Florida, os candidatos sem adversário não vão a votos)."""


def nomes_geo(estado: CodigoEstado) -> dict[str, str]:
    return nomes(estado.value)
