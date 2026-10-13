"""Fontes do Iowa: relatórios diários "Absentee Ballot Statistics" do Secretary of State.

Para cada eleição geral, o Secretary of State publica PDF cumulativos com um relatório por
dia: pedidos, boletins emitidos e recebidos por unidade, partido de registo e forma de
receção (no balcão, em locais satélite, por correio, caixa de depósito, etc.). Há um PDF
por distrito do Congresso e outro por condado. Os de 2022 e 2024 continuam publicados, o
que dá a comparação no mesmo dia do ciclo. Não há idade.
"""

from typing import Literal

NOME_FONTE = "Iowa Secretary of State, Absentee Ballot Statistics"
LICENCA = "Registo público (Iowa Code cap. 22)"

Nivel = Literal["distrito", "condado"]
_FICHEIRO: dict[Nivel, str] = {"distrito": "Congressional", "condado": "County"}


def url(ano: int, nivel: Nivel) -> str:
    """PDF cumulativo da eleição geral de ``ano`` por distrito ou por condado."""
    return f"https://sos.iowa.gov/elections/pdf/{ano}/general/Absentee{_FICHEIRO[nivel]}{ano}.pdf"
