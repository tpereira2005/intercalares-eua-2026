"""Condados e categorias da Florida."""

from pipeline.comum.categorias import Partido

FIPS_CONDADO: dict[str, str] = {
    "ALACHUA": "12001", "BAKER": "12003", "BAY": "12005", "BRADFORD": "12007",
    "BREVARD": "12009", "BROWARD": "12011", "CALHOUN": "12013", "CHARLOTTE": "12015",
    "CITRUS": "12017", "CLAY": "12019", "COLLIER": "12021", "COLUMBIA": "12023",
    "DESOTO": "12027", "DIXIE": "12029", "DUVAL": "12031", "ESCAMBIA": "12033",
    "FLAGLER": "12035", "FRANKLIN": "12037", "GADSDEN": "12039", "GILCHRIST": "12041",
    "GLADES": "12043", "GULF": "12045", "HAMILTON": "12047", "HARDEE": "12049",
    "HENDRY": "12051", "HERNANDO": "12053", "HIGHLANDS": "12055", "HILLSBOROUGH": "12057",
    "HOLMES": "12059", "INDIANRIVER": "12061", "JACKSON": "12063", "JEFFERSON": "12065",
    "LAFAYETTE": "12067", "LAKE": "12069", "LEE": "12071", "LEON": "12073", "LEVY": "12075",
    "LIBERTY": "12077", "MADISON": "12079", "MANATEE": "12081", "MARION": "12083",
    "MARTIN": "12085", "MIAMIDADE": "12086", "MONROE": "12087", "NASSAU": "12089",
    "OKALOOSA": "12091", "OKEECHOBEE": "12093", "ORANGE": "12095", "OSCEOLA": "12097",
    "PALMBEACH": "12099", "PASCO": "12101", "PINELLAS": "12103", "POLK": "12105",
    "PUTNAM": "12107", "STJOHNS": "12109", "STLUCIE": "12111", "SANTAROSA": "12113",
    "SARASOTA": "12115", "SEMINOLE": "12117", "SUMTER": "12119", "SUWANNEE": "12121",
    "TAYLOR": "12123", "UNION": "12125", "VOLUSIA": "12127", "WAKULLA": "12129",
    "WALTON": "12131", "WASHINGTON": "12133",
}  # fmt: skip
"""Chave: nome em maiúsculas sem espaços nem pontuação ("St. Johns" -> "STJOHNS")."""

COLUNAS_PARTIDO: dict[str, Partido] = {
    "TotalRep": Partido.REP,
    "TotalDem": Partido.DEM,
    "TotalNpa": Partido.NAO_AFILIADO,
    "TotalOth": Partido.OUTRO,
}

TIPOS: dict[str, str] = {
    "VOTE-BY-MAIL PROVIDED (NOT YET RETURNED)": "pendentes",
    "VOTED VOTE-BY-MAIL": "correio",
    "VOTED EARLY": "presencial",
}
