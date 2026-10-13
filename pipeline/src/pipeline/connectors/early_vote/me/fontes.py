"""Fontes do Maine: ficheiro público de votantes por correspondência (absentee).

O Secretary of State publica, em texto delimitado por "|", um registo por boletim pedido,
com município, partido, distrito e as datas de pedido e de receção. Não traz a idade. Em
2026 o ficheiro é atualizado algumas vezes por semana e muda de nome em cada versão, por
isso o endereço lê-se da página de dados. Os ficheiros finais dos anos anteriores ficam
numa página de arquivo.
"""

import re
from urllib.parse import urljoin

NOME_FONTE = "Maine Secretary of State, Absentee Voter File"
LICENCA = "Registo público (21-A M.R.S. § 753-B)"

PAGINA_ATUAL = "https://www.maine.gov/sos/elections-voting/voter-data"
BASE = "https://www.maine.gov/sos/sites/maine.gov.sos/files/"
FINAIS: dict[int, str] = {
    2018: BASE + "data-text/absentee-voter-file11618.txt",
    2022: BASE + "inline-files/Absentee%20Voter%20File11822_0.txt",
    2024: BASE + "inline-files/2024-11-05%20Final%20AB%20Voter%20File.txt",
}

_LIGACAO_2026 = re.compile(r'href="([^"]*11-3-26[^"]*AB[^"]*Voter[^"]*File[^"]*\.txt)"', re.I)


def url_atual(html: str) -> str | None:
    """Endereço do ficheiro da eleição geral de 2026 na página de dados, se existir."""
    encontrados: list[str] = _LIGACAO_2026.findall(html)
    if not encontrados:
        return None
    return urljoin(PAGINA_ATUAL, encontrados[-1])
