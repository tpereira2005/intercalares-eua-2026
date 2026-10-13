"""Códigos da Pensilvânia normalizados para as categorias comuns."""

from pipeline.comum.categorias import Partido

CONDADOS = (
    "ADAMS", "ALLEGHENY", "ARMSTRONG", "BEAVER", "BEDFORD", "BERKS", "BLAIR", "BRADFORD",
    "BUCKS", "BUTLER", "CAMBRIA", "CAMERON", "CARBON", "CENTRE", "CHESTER", "CLARION",
    "CLEARFIELD", "CLINTON", "COLUMBIA", "CRAWFORD", "CUMBERLAND", "DAUPHIN", "DELAWARE",
    "ELK", "ERIE", "FAYETTE", "FOREST", "FRANKLIN", "FULTON", "GREENE", "HUNTINGDON",
    "INDIANA", "JEFFERSON", "JUNIATA", "LACKAWANNA", "LANCASTER", "LAWRENCE", "LEBANON",
    "LEHIGH", "LUZERNE", "LYCOMING", "MCKEAN", "MERCER", "MIFFLIN", "MONROE", "MONTGOMERY",
    "MONTOUR", "NORTHAMPTON", "NORTHUMBERLAND", "PERRY", "PHILADELPHIA", "PIKE", "POTTER",
    "SCHUYLKILL", "SNYDER", "SOMERSET", "SULLIVAN", "SUSQUEHANNA", "TIOGA", "UNION",
    "VENANGO", "WARREN", "WASHINGTON", "WAYNE", "WESTMORELAND", "WYOMING", "YORK",
)  # fmt: skip
"""Os 67 condados por ordem alfabética, que é também a ordem dos códigos FIPS."""

FIPS_CONDADO = {nome: f"42{2 * i + 1:03d}" for i, nome in enumerate(CONDADOS)}
NOME_CONDADO = {
    fips: nome.title().replace("Mckean", "McKean") for nome, fips in FIPS_CONDADO.items()
}

PARTIDOS: dict[str, Partido] = {
    "D": Partido.DEM,
    "DEM": Partido.DEM,
    "R": Partido.REP,
    "REP": Partido.REP,
}
"""Desde 2024 a fonte junta os não filiados e os pequenos partidos em "OTH"; para comparar
anos, tudo o que não é democrata nem republicano fica em ``outro``."""

ESTADOS_ANULADOS = frozenset({"CANCELLED"})
