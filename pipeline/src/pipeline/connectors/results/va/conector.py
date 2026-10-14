"""Conector de resultados da Virgínia.

A Virgínia usa a mesma API JSON (Enhanced Voting) que a Geórgia, lida por
``enhanced_voting.py``. O ficheiro do estado traz o Senado, os 11 distritos da Câmara e
as corridas locais (ignoradas), com o apuramento por localidade (133 condados e cidades
independentes) e, por candidato, os votos por tipo: Early Voting, Election Day, Mailed
Absentee, Provisional e Post-Election. Só pedimos o ficheiro do estado; os das localidades
não são necessários para o apuramento.

Os identificadores vêm da lista de eleições do site (``api/jurisdictions/Virginia``) e não
seguem uma regra única: 2024 é ``2024NovemberGeneral`` e 2025 e 2026 são
``2025-November-General`` e ``2026-November-General``. As eleições de 2022 e anteriores a
2023 não estão nesta plataforma. Antes de a página da eleição existir, a API responde 204.
"""

from dataclasses import dataclass
from datetime import date
from pathlib import Path

from contratos.estados import CodigoEstado
from pipeline.connectors.results.comum import ObterTexto, Pedido
from pipeline.connectors.results.enhanced_voting import FICHEIRO, ler_estado
from pipeline.transform.resultados.montar import Leitura

URL = "https://enr.elections.virginia.gov/results/public/api/elections/Virginia/{eleicao}/data"


def identificador(data: date) -> str:
    if data.year == 2024:
        return "2024NovemberGeneral"
    return f"{data.year}-November-General"


@dataclass(frozen=True, slots=True)
class ConectorVA:
    estado: CodigoEstado = CodigoEstado.VA
    nome_fonte: str = "Virginia Department of Elections, Election Results"
    licenca: str | None = "Registo público (Code of Virginia, 2.2-3700)"

    def pedidos(self, data: date, obter: ObterTexto) -> list[Pedido]:
        del obter
        return [Pedido(URL.format(eleicao=identificador(data)), FICHEIRO)]

    def ler(self, pasta: Path, data: date) -> Leitura:
        del data
        return ler_estado(pasta, self.estado)
