"""Faixas etárias usadas em toda a análise.

Há três esquemas:

* ``CANONICA``: as faixas do plano (secção 6.3), usadas no site. Exigem a idade individual.
* ``LARGA``: agregação da canónica para mapas e títulos (jovens vs mais velhos). Cada faixa
  larga é uma soma exata de faixas canónicas, por isso pode ser derivada dos cubos.
* ``NCSBE``: as faixas que a Junta Eleitoral da Carolina do Norte usa nos seus ficheiros
  agregados (``voter_stats``, ``history_stats``). Servem só para validar os nossos totais
  contra os números oficiais.
"""

from dataclasses import dataclass

import polars as pl

IDADE_MINIMA = 17
"""Quem faz 18 anos até ao dia da eleição pode estar recenseado com 17."""

IDADE_MAXIMA_PLAUSIVEL = 115
FAIXA_DESCONHECIDA = "desconhecida"


@dataclass(frozen=True, slots=True)
class Faixa:
    rotulo: str
    minimo: int
    maximo: int | None
    """Inclusivo; ``None`` significa sem limite superior."""

    def contem(self, idade: int) -> bool:
        return idade >= self.minimo and (self.maximo is None or idade <= self.maximo)


@dataclass(frozen=True, slots=True)
class EsquemaFaixas:
    nome: str
    faixas: tuple[Faixa, ...]

    @property
    def rotulos(self) -> list[str]:
        return [f.rotulo for f in self.faixas]

    def classificar(self, idade: int | None) -> str:
        if idade is None or not IDADE_MINIMA <= idade <= IDADE_MAXIMA_PLAUSIVEL:
            return FAIXA_DESCONHECIDA
        for faixa in self.faixas:
            if faixa.contem(idade):
                return faixa.rotulo
        return FAIXA_DESCONHECIDA

    def expressao(self, coluna: str = "idade", nome: str = "faixa") -> pl.Expr:
        """Expressão polars que classifica uma coluna inteira de idades (pode ter nulos)."""
        idade = pl.col(coluna)
        resultado: pl.Expr = pl.lit(FAIXA_DESCONHECIDA)
        for faixa in reversed(self.faixas):
            condicao = idade >= faixa.minimo
            if faixa.maximo is not None:
                condicao = condicao & (idade <= faixa.maximo)
            resultado = pl.when(condicao).then(pl.lit(faixa.rotulo)).otherwise(resultado)
        valida = idade.is_not_null() & idade.is_between(IDADE_MINIMA, IDADE_MAXIMA_PLAUSIVEL)
        return pl.when(valida).then(resultado).otherwise(pl.lit(FAIXA_DESCONHECIDA)).alias(nome)


CANONICA = EsquemaFaixas(
    "canonica",
    (
        Faixa("18-24", IDADE_MINIMA, 24),
        Faixa("25-29", 25, 29),
        Faixa("30-39", 30, 39),
        Faixa("40-49", 40, 49),
        Faixa("50-64", 50, 64),
        Faixa("65-74", 65, 74),
        Faixa("75+", 75, None),
    ),
)

LARGA = EsquemaFaixas(
    "larga",
    (
        Faixa("18-29", IDADE_MINIMA, 29),
        Faixa("30-49", 30, 49),
        Faixa("50-64", 50, 64),
        Faixa("65+", 65, None),
    ),
)

NCSBE = EsquemaFaixas(
    "ncsbe",
    (
        Faixa("18-25", IDADE_MINIMA, 25),
        Faixa("26-40", 26, 40),
        Faixa("41-65", 41, 65),
        Faixa("66+", 66, None),
    ),
)

CANONICA_PARA_LARGA: dict[str, str] = {
    "18-24": "18-29",
    "25-29": "18-29",
    "30-39": "30-49",
    "40-49": "30-49",
    "50-64": "50-64",
    "65-74": "65+",
    "75+": "65+",
    FAIXA_DESCONHECIDA: FAIXA_DESCONHECIDA,
}
"""Cada faixa larga é a soma exata de faixas canónicas."""
