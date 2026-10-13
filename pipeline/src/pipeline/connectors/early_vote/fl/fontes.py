"""Fontes da Florida: estatísticas diárias de voto por correspondência e antecipado.

A Division of Elections publica totais por condado e partido, cumulativos até ao dia
anterior, compilados a partir dos relatórios diários dos 67 condados. Não há ficheiro
individual público nem séries de anos anteriores: a série diária de 2026 é construída por
nós, guardando cada retrato (ver ``historico``).
"""

import re
from urllib.parse import urljoin

NOME_FONTE = "Florida Division of Elections, Vote-by-Mail and Early Voting Statistics"
LICENCA = "Registo público (Fla. Stat. 101.62, 101.657)"
PAGINA = "https://countyballotfiles.floridados.gov/VoteByMailEarlyVotingReports/PublicStats"

_FICHEIRO = re.compile(
    r"https://electionfiles\.floridados\.gov/countyballotreportfiles/Stats_\d+_\w+\.txt"
)


def urls_estatisticas(html: str) -> list[str]:
    """Ficheiros de estatísticas ligados na página (correio pedido, correio votado e,
    quando começa, voto antecipado presencial)."""
    return sorted({urljoin(PAGINA, u) for u in _FICHEIRO.findall(html)})
