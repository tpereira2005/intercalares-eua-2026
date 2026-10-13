"""Fontes da Pensilvânia: pedidos de voto por correspondência no portal de dados abertos.

O Department of State publica em data.pa.gov um registo por pedido de boletim, sem nome
nem identificador do eleitor, com condado, partido, mês (ou data) de nascimento, distrito
e as datas do pedido e da devolução. A versão de 2026 é atualizada diariamente; as dos
anos anteriores estão fechadas ("NO FURTHER UPDATES").
"""

from urllib.parse import urlencode

NOME_FONTE = "Pennsylvania Department of State (data.pa.gov)"
LICENCA = "Public Domain U.S. Government"

CONJUNTOS: dict[int, str] = {
    2020: "mcba-yywm",
    2022: "uhfm-zhus",
    2024: "3q5t-ddp8",
    2026: "nbwd-pfn4",
}
"""Identificador Socrata do conjunto de pedidos de cada eleição geral."""

COLUNAS = (
    "countyname",
    "party",
    "dateofbirth",
    "appissuedate",
    "ballotreturneddate",
    "congressional",
)
COLUNA_ESTADO = "ballot_status"
"""Só existe desde 2024; nos anos anteriores um boletim devolvido tem data de devolução."""

ANOS_COM_ESTADO = frozenset({2024, 2026})
LIMITE = 20_000_000


def url_pedidos(ano: int) -> str:
    """CSV só com as colunas usadas (sem coordenadas), pedido ao servidor."""
    colunas = list(COLUNAS) + ([COLUNA_ESTADO] if ano in ANOS_COM_ESTADO else [])
    consulta = urlencode({"$select": ",".join(colunas), "$limit": LIMITE, "$order": ":id"})
    return f"https://data.pa.gov/resource/{CONJUNTOS[ano]}.csv?{consulta}"
