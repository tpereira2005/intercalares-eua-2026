"""Fonte oficial da afluência ao voto antecipado presencial de Clark County, Nevada.

A página do Clark County Election Department mostra, por local de voto e por dia, quantas
pessoas votaram presencialmente (o voto por correio não aparece). Usamos só esta página
agregada: nunca os ficheiros por eleitor (``ev_AAAAMMDD.zip``), que têm nomes e identificadores.
"""

NOME_FONTE = "Clark County Election Department, Early Voting Turnout (voto presencial)"
LICENCA = "Informação pública do Clark County Election Department"
URL = "https://elections.clarkcountynv.gov/ElectionResultsTV/evturnout.aspx"
