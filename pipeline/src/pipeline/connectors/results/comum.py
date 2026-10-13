"""Peças comuns aos conectores de resultados.

Um conector tem duas partes separadas de propósito:

- ``pedidos``: que ficheiros pedir à fonte (pode precisar de um pedido prévio, como a
  versão atual nos sites Clarity);
- ``ler``: transformar os ficheiros já descarregados numa ``Leitura``, sem rede.

Assim o mesmo ``ler`` serve a noite eleitoral, os testes e o ensaio geral com os ficheiros
de 2022 e 2024 guardados.
"""

import re
import unicodedata
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Protocol

from contratos.estados import CodigoEstado
from contratos.resultados import Cargo
from pipeline.transform.resultados.montar import DescricaoCorrida, Leitura

ObterTexto = Callable[[str], str]
"""Pede um URL pequeno à fonte (ou ao espelho do ensaio) e devolve o texto."""


@dataclass(frozen=True, slots=True)
class Pedido:
    url: str
    ficheiro: str
    """Nome do ficheiro local, dentro da pasta do retrato."""

    sentinela: bool = True
    """Ficheiro que muda sempre que há resultados novos. Os outros (detalhe por condado)
    só se pedem quando uma sentinela mudou, para não multiplicar pedidos à fonte."""


class ConectorResultados(Protocol):
    @property
    def estado(self) -> CodigoEstado: ...

    @property
    def nome_fonte(self) -> str: ...

    @property
    def licenca(self) -> str | None: ...

    def pedidos(self, data: date, obter: ObterTexto) -> list[Pedido]: ...

    def ler(self, pasta: Path, data: date) -> Leitura: ...


def _simples(texto: str) -> str:
    sem_acentos = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    return re.sub(r"\s+", " ", sem_acentos.upper().replace(".", "")).strip()


_DEM = {"DEM", "D", "DEMOCRAT", "DEMOCRATIC", "DEMOCRATIC PARTY"}
_REP = {"REP", "R", "REPUBLICAN", "REPUBLICAN PARTY", "GOP"}


def partido(texto: str | None) -> str:
    """Normaliza o rótulo de partido da fonte para ``dem``, ``rep`` ou ``outro``."""
    chave = _simples(texto or "")
    if chave in _DEM:
        return "dem"
    if chave in _REP:
        return "rep"
    return "outro"


_SENADO = re.compile(r"\b(US|UNITED STATES) SENAT(E|OR)\b")
_CAMARA = re.compile(
    r"\b(US HOUSE(?: OF REPRESENTATIVES)?(?: DIST)?|REPRESENTATIVE IN CONGRESS|US REPRESENTATIVE|"
    r"UNITED STATES REPRESENTATIVE|US CONGRESS|CONGRESSIONAL DISTRICT)\b\D*?(\d{1,2})\b"
)
_CAMARA_DISTRITO_ANTES = re.compile(r"\b(\d{1,2})(ST|ND|RD|TH)? CONGRESSIONAL DISTRICT\b")
_CAMARA_SEM_NUMERO = re.compile(
    r"^(US REPRESENTATIVE|US HOUSE(?: OF REPRESENTATIVES)?|REPRESENTATIVE IN CONGRESS|"
    r"UNITED STATES REPRESENTATIVE)$"
)
DISTRITO_UNICO = frozenset(
    {CodigoEstado.AK, CodigoEstado.DE, CodigoEstado.ND, CodigoEstado.SD, CodigoEstado.VT,
     CodigoEstado.WY}
)  # fmt: skip
"""Estados com um só lugar na Câmara: a corrida chama-se só "U.S. Representative" e o
identificador é ``XX-00``, como na previsão."""
_GOVERNADOR = re.compile(r"^GOVERNOR\b")
_ESPECIAL = re.compile(r"\b(SPECIAL|UNEXPIRED)\b")


def identificar_corrida(estado: CodigoEstado, nome: str) -> DescricaoCorrida | None:
    """Reconhece Senado, Câmara e governador pelo nome da corrida na fonte.

    Devolve ``None`` para tudo o resto (cargos estaduais, referendos, primárias).
    """
    chave = _simples(nome)
    especial = bool(_ESPECIAL.search(chave))
    sufixo = "-especial" if especial else ""
    cargo: Cargo
    distrito: int | None = None
    if _SENADO.search(chave):
        cargo, codigo = "senado", "S"
    elif m := (_CAMARA_DISTRITO_ANTES.search(chave) or _CAMARA.search(chave)):
        numero = m.group(1) if m.re is _CAMARA_DISTRITO_ANTES else m.group(2)
        distrito = int(numero)
        cargo, codigo = "camara", f"{distrito:02d}"
    elif estado in DISTRITO_UNICO and _CAMARA_SEM_NUMERO.match(chave):
        distrito = 0
        cargo, codigo = "camara", "00"
    elif _GOVERNADOR.search(chave):
        cargo, codigo = "governador", "G"
    else:
        return None
    return DescricaoCorrida(
        id=f"{estado.value}-{codigo}{sufixo}",
        nome_fonte=nome.strip(),
        cargo=cargo,
        distrito=distrito,
        especial=especial,
    )


def modalidade(nome: str) -> str:
    """Normaliza o tipo de voto da fonte (``Election Day``, ``Advanced Voting``...)."""
    chave = _simples(nome)
    if "PROVISIONAL" in chave or "FAILSAFE" in chave:
        return "provisorio"
    if "MAIL" in chave or chave in {"ABSENTEE", "ABSENTEE BY MAIL", "AVC"}:
        return "correio"
    if "EARLY" in chave or "ADVANCE" in chave or "ONE STOP" in chave or "IN PERSON" in chave:
        return "antecipado_presencial"
    if "ELECTION DAY" in chave or chave in {"POLLS", "OVC"}:
        return "dia_eleicao"
    return "outro"
