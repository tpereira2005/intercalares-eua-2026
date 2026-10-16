"""Fonte dos estados que bloqueiam a recolha automática: UF Election Lab.

O Election Lab da Universidade da Florida (Prof. Michael McDonald) reúne o voto antecipado
de cada estado em ``US.csv``, o ficheiro que as páginas por estado do próprio site leem
(``2026-early-voting.js``). Não é uma fonte oficial: é um compilado académico dos dados que
cada estado publica. O ``robots.txt`` do site só exclui ``/wp-admin/``.

A reutilização foi pedida por e-mail ao UF Election Lab a 16 de outubro de 2026; o dono do
projeto mandou avançar assumindo resposta positiva.
"""

NOME_FONTE = (
    "UF Election Lab, 2026 General Election Early Vote (Michael McDonald, Universidade da Florida)"
)
LICENCA = "Reutilização com atribuição (pedida ao UF Election Lab a 16/10/2026)"
PAGINA = "https://election.lab.ufl.edu/2026-general-election-early-vote/"
CSV = "https://election.lab.ufl.edu/data-downloads/earlyvote/2026/US.csv"
CITACAO = (
    "McDonald, M. P. (2026). 2026 General Election Early Vote. "
    "UF Election Lab, University of Florida. https://election.lab.ufl.edu/"
)
