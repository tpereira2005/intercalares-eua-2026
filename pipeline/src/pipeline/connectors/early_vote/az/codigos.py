"""Condados do Arizona."""

FIPS_CONDADO: dict[str, str] = {
    "APACHE": "04001", "COCHISE": "04003", "COCONINO": "04005", "GILA": "04007",
    "GRAHAM": "04009", "GREENLEE": "04011", "LAPAZ": "04012", "MARICOPA": "04013",
    "MOHAVE": "04015", "NAVAJO": "04017", "PIMA": "04019", "PINAL": "04021",
    "SANTACRUZ": "04023", "YAVAPAI": "04025", "YUMA": "04027",
}  # fmt: skip
"""Chave: nome em maiúsculas sem espaços nem pontuação ("La Paz" -> "LAPAZ")."""

NOMES_CONDADO: dict[str, str] = {
    "04012": "La Paz",
    "04023": "Santa Cruz",
    **{fips: nome.title() for nome, fips in FIPS_CONDADO.items() if fips not in ("04012", "04023")},
}
"""Nome de apresentação de cada condado, por FIPS."""

TOTAIS_ESTADO: frozenset[str] = frozenset(
    {"ARIZONA", "TOTAL", "STATETOTAL", "STATETOTALS", "STATEWIDE", "STATE"}
)
"""Nomes (na mesma forma das chaves de ``FIPS_CONDADO``) que a fonte poderia dar a uma linha
de total estadual. Hoje a tabela não tem nenhuma; se aparecer, confere-se a soma."""
