"""Tradução dos códigos da NCSBE para as categorias normalizadas."""

from pipeline.comum.categorias import EstadoBoletim, Etnia, Genero, Modalidade, Partido, Raca
from pipeline.comum.condados import chave, fips_por_nome

CONDADOS: tuple[str, ...] = (
    "ALAMANCE", "ALEXANDER", "ALLEGHANY", "ANSON", "ASHE", "AVERY", "BEAUFORT", "BERTIE",
    "BLADEN", "BRUNSWICK", "BUNCOMBE", "BURKE", "CABARRUS", "CALDWELL", "CAMDEN", "CARTERET",
    "CASWELL", "CATAWBA", "CHATHAM", "CHEROKEE", "CHOWAN", "CLAY", "CLEVELAND", "COLUMBUS",
    "CRAVEN", "CUMBERLAND", "CURRITUCK", "DARE", "DAVIDSON", "DAVIE", "DUPLIN", "DURHAM",
    "EDGECOMBE", "FORSYTH", "FRANKLIN", "GASTON", "GATES", "GRAHAM", "GRANVILLE", "GREENE",
    "GUILFORD", "HALIFAX", "HARNETT", "HAYWOOD", "HENDERSON", "HERTFORD", "HOKE", "HYDE",
    "IREDELL", "JACKSON", "JOHNSTON", "JONES", "LEE", "LENOIR", "LINCOLN", "MACON", "MADISON",
    "MARTIN", "MCDOWELL", "MECKLENBURG", "MITCHELL", "MONTGOMERY", "MOORE", "NASH",
    "NEW HANOVER", "NORTHAMPTON", "ONSLOW", "ORANGE", "PAMLICO", "PASQUOTANK", "PENDER",
    "PERQUIMANS", "PERSON", "PITT", "POLK", "RANDOLPH", "RICHMOND", "ROBESON", "ROCKINGHAM",
    "ROWAN", "RUTHERFORD", "SAMPSON", "SCOTLAND", "STANLY", "STOKES", "SURRY", "SWAIN",
    "TRANSYLVANIA", "TYRRELL", "UNION", "VANCE", "WAKE", "WARREN", "WASHINGTON", "WATAUGA",
    "WAYNE", "WILKES", "WILSON", "YADKIN", "YANCEY",
)  # fmt: skip
"""Os 100 condados pela ordem dos identificadores da NCSBE (1 a 100), que é a ordem
alfabética de como a NCSBE os escreve. Não é a ordem dos códigos FIPS: o Census ordena
"McDowell" antes de "Macon", por isso a posição não serve para calcular o FIPS."""

FIPS_CONDADO: dict[str, str] = {nome: fips_por_nome("NC")[chave(nome)] for nome in CONDADOS}
"""Nome do condado (como a NCSBE o escreve) para o código FIPS de cinco dígitos, pela lista
de condados do Census Bureau."""

PARTIDO: dict[str, Partido] = {
    "DEM": Partido.DEM,
    "REP": Partido.REP,
    "UNA": Partido.NAO_AFILIADO,
}
"""Qualquer outro código válido (LIB, GRE, CST, NLB, JFA...) passa a ``Partido.OUTRO``."""

RACA: dict[str, Raca] = {
    # códigos do ficheiro de eleitores e dos retratos
    "W": Raca.BRANCA,
    "B": Raca.NEGRA,
    "A": Raca.ASIATICA,
    "I": Raca.NATIVA,
    "P": Raca.HAVAIANA_PACIFICO,
    "M": Raca.MULTIRRACIAL,
    "O": Raca.OUTRA,
    "U": Raca.NAO_INDICADA,
    # descrições do ficheiro de boletins
    "WHITE": Raca.BRANCA,
    "BLACK OR AFRICAN AMERICAN": Raca.NEGRA,
    "ASIAN": Raca.ASIATICA,
    "INDIAN AMERICAN OR ALASKA NATIVE": Raca.NATIVA,
    "AMERICAN INDIAN OR ALASKA NATIVE": Raca.NATIVA,
    "NATIVE HAWAIIAN OR PACIFIC ISLANDER": Raca.HAVAIANA_PACIFICO,
    "TWO OR MORE RACES": Raca.MULTIRRACIAL,
    "OTHER": Raca.OUTRA,
    "UNDESIGNATED": Raca.NAO_INDICADA,
}

ETNIA: dict[str, Etnia] = {
    "HL": Etnia.HISPANICA,
    "NL": Etnia.NAO_HISPANICA,
    "UN": Etnia.NAO_INDICADA,
    "HISPANIC OR LATINO": Etnia.HISPANICA,
    "NOT HISPANIC OR NOT LATINO": Etnia.NAO_HISPANICA,
    "UNDESIGNATED": Etnia.NAO_INDICADA,
}

GENERO: dict[str, Genero] = {
    "F": Genero.FEMININO,
    "M": Genero.MASCULINO,
    "U": Genero.NAO_INDICADO,
}

MODALIDADE: dict[str, Modalidade] = {
    "ONE-STOP": Modalidade.PRESENCIAL,
    "EARLY VOTING": Modalidade.PRESENCIAL,
    "MAIL": Modalidade.CORREIO,
}

ESTADO_BOLETIM: dict[str, EstadoBoletim] = {
    "": EstadoBoletim.POR_DEVOLVER,
    "ACCEPTED": EstadoBoletim.ACEITE,
    "ACCEPTED - CURED": EstadoBoletim.ACEITE,
    "ACCEPTED - EXCEPTION": EstadoBoletim.ACEITE,
    "PENDING": EstadoBoletim.PENDENTE,
    "PENDING CURE": EstadoBoletim.PENDENTE,
    "AFFIDAVIT REVIEW PENDING": EstadoBoletim.PENDENTE,
    "PHOTO ID CURABLE": EstadoBoletim.PENDENTE,
    "CONFLICT": EstadoBoletim.PENDENTE,
    "WITNESS INFO INCOMPLETE": EstadoBoletim.PENDENTE,
    "ASSISTANT INFO INCOMPLETE": EstadoBoletim.PENDENTE,
    "SIGNATURE DIFFERENT": EstadoBoletim.PENDENTE,
    "NOT PROPERLY NOTARIZED": EstadoBoletim.PENDENTE,
    "ID NOT PROVIDED": EstadoBoletim.PENDENTE,
    "AFFIDAVIT INCOMPLETE": EstadoBoletim.PENDENTE,
    "RETURNED AFTER DEADLINE": EstadoBoletim.REJEITADO,
    "WRONG VOTER": EstadoBoletim.REJEITADO,
    "NO TIME FOR CURE - CONTACTED": EstadoBoletim.REJEITADO,
    "PHOTO ID NONCOMPLIANT": EstadoBoletim.REJEITADO,
    "AFFIDAVIT DECLINED": EstadoBoletim.REJEITADO,
    "SDR-FAILED VERIFICATION": EstadoBoletim.REJEITADO,
    "SPOILED": EstadoBoletim.ANULADO,
    "SPOILED-EV": EstadoBoletim.ANULADO,
    "CANCELLED": EstadoBoletim.ANULADO,
    "NOT VOTED": EstadoBoletim.ANULADO,
    "RETURNED UNDELIVERABLE": EstadoBoletim.ANULADO,
    "DUPLICATE": EstadoBoletim.ANULADO,
    "E-TRANSMISSION FAILURE": EstadoBoletim.ANULADO,
}
"""Estados intermédios que dependem de correção ficam como pendentes; nos ficheiros finais
dos anos anteriores contam igualmente como devolvidos (ver ``ESTADOS_DEVOLVIDOS``)."""

METODO_HISTORICO_ANTECIPADO = frozenset(
    {
        "ABSENTEE ONESTOP",
        "ABSENTEE CURBSIDE",
        "ABSENTEE BY MAIL",
        "ABSENTEE",
        "EARLY VOTING IN-PERSON",
        "EARLY VOTING CURBSIDE",
    }
)
METODO_HISTORICO_DIA = frozenset(
    {"ELECTION DAY IN-PERSON", "ELECTION DAY CURBSIDE", "PROVISIONAL", "TRANSFER", "IN-PERSON"}
)


def _nome_proprio(nome: str) -> str:
    if nome == "MCDOWELL":
        return "McDowell"
    return " ".join(p.capitalize() for p in nome.split())


NOME_CONDADO: dict[str, str] = {FIPS_CONDADO[n]: _nome_proprio(n) for n in CONDADOS}
"""FIPS para o nome do condado, como aparece no site."""
