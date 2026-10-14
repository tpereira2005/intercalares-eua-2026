"""Conector de resultados da Geórgia.

Desde 2024 a Geórgia publica os resultados numa API JSON (Enhanced Voting, lida por
``enhanced_voting.py``). O ficheiro do estado traz todas as corridas com os votos por
candidato e os condados apurados; os condados têm ficheiros próprios, que não pedimos a
cada ciclo (seriam 159 pedidos). As eleições têm identificadores legíveis (``2022NovGen``,
``2024NovGen``); antes de a página da eleição existir, a API responde 204 sem conteúdo.
"""

from dataclasses import dataclass
from datetime import date
from pathlib import Path

from contratos.estados import CodigoEstado
from pipeline.connectors.results.comum import ObterTexto, Pedido
from pipeline.connectors.results.enhanced_voting import FICHEIRO, ler_estado
from pipeline.transform.resultados.montar import Leitura

URL = "https://results.sos.ga.gov/results/public/api/elections/Georgia/{eleicao}/data"


def identificador(data: date) -> str:
    return f"{data.year}{data:%b}Gen"


@dataclass(frozen=True, slots=True)
class ConectorGA:
    estado: CodigoEstado = CodigoEstado.GA
    nome_fonte: str = "Georgia Secretary of State, Election Results"
    licenca: str | None = "Registo público (O.C.G.A. 50-18-70)"

    def pedidos(self, data: date, obter: ObterTexto) -> list[Pedido]:
        del obter
        return [Pedido(URL.format(eleicao=identificador(data)), FICHEIRO)]

    def ler(self, pasta: Path, data: date) -> Leitura:
        del data
        return ler_estado(pasta, self.estado)
