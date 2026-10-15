"""Classificações de outros prognosticadores, lidas das tabelas da Wikipedia.

O Senado vem da secção "Predictions" de ``2026 United States Senate elections``; a Câmara,
da primeira tabela de ``2026 United States House of Representatives election ratings``.
Cada coluna de classificações identifica-se pela ligação no cabeçalho (Cook, Sabato...),
nunca pela posição: a ordem muda entre páginas e ao longo do tempo. Uma coluna, uma
categoria ou uma corrida que não se reconheça faz falhar a leitura, para que nada mal lido
chegue ao site.
"""

import re
from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import Literal, cast

from contratos.prognosticos import Categoria, Classificacao, CorridaPrognosticos
from pipeline.comum.erros import ErroFormatoFonte
from pipeline.modelo.fontes.corridas import CODIGOS, NOMES_ESTADOS
from pipeline.modelo.fontes.wikitexto import grelha, linhas, sem_comentarios, tabelas

PAGINA_SENADO = "2026 United States Senate elections"
PAGINA_CAMARA = "2026 United States House of Representatives election ratings"

PROGNOSTICADORES: dict[str, tuple[str, str]] = {
    "cook political report": ("cook", "Cook Political Report"),
    "the cook political report": ("cook", "Cook Political Report"),
    "inside elections": ("ie", "Inside Elections"),
    "stuart rothenberg": ("ie", "Inside Elections"),
    "sabato's crystal ball": ("sabato", "Sabato's Crystal Ball"),
    "the economist": ("economist", "The Economist"),
    "split ticket (website)": ("split-ticket", "Split Ticket"),
    "decision desk hq": ("ddhq", "Decision Desk HQ"),
    "fiftyplusone": ("fpo", "FiftyPlusOne"),
    "fox news": ("fox", "Fox News"),
    "silver bulletin": ("silver", "Silver Bulletin"),
    "realclearpolitics": ("rcp", "RealClearPolitics"),
    "real clear politics": ("rcp", "RealClearPolitics"),
}
"""Destino da ligação no cabeçalho da coluna -> (chave, nome)."""

CATEGORIAS: dict[str, Categoria] = {
    "safe": "seguro",
    "solid": "seguro",
    "likely": "provavel",
    "lean": "inclinado",
    "tilt": "ligeiro",
    "tossup": "empate",
    "toss-up": "empate",
}

MESES = {
    m: i + 1
    for i, m in enumerate(
        ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"]
    )
}

_CLASSIFICACAO = re.compile(r"\{\{\s*USRaceRating\s*\|([^{}]*)\}\}", re.I)
_LIGACAO = re.compile(r"\[\[([^\]|#]+)(?:\|[^\]]*)?\]\]")
_DATA = re.compile(r"([A-Z][a-z]{2,8})\.?\s+(\d{1,2}),?\s*(?:<br\s*/?>)?\s*(\d{4})", re.I)
_URL = re.compile(r"\burl\s*=\s*(https?://[^\s|}]+)", re.I)
_USHR = re.compile(r"\{\{\s*ushr\s*\|\s*([^|}]+?)\s*\|\s*([^|}]+?)\s*(?:\|[^}]*)?\}\}", re.I)
_SENADO = re.compile(
    r"\[\[\s*\d{4} United States Senate (special )?election in ([^|\]#]+?)\s*(?:\|[^\]]*)?\]\]",
    re.I,
)


@dataclass(frozen=True, slots=True)
class Coluna:
    chave: str
    nome: str
    data: date | None
    url: str | None


@dataclass(frozen=True, slots=True)
class Tabela:
    colunas: tuple[Coluna, ...]
    corridas: tuple[CorridaPrognosticos, ...]


def _data(celula: str) -> date | None:
    texto = re.sub(r"\{\{\s*small\s*\|", " ", celula, flags=re.I)
    m = _DATA.search(texto)
    if m is None:
        return None
    mes = MESES.get(m.group(1)[:3].lower())
    if mes is None:
        return None
    return date(int(m.group(3)), mes, int(m.group(2)))


def _coluna(celula: str) -> Coluna | None:
    sem_refs = re.sub(r"<ref[^>]*>.*?</ref>", "", celula, flags=re.S | re.I)
    m = _LIGACAO.search(sem_refs)
    if m is None:
        return None
    alvo = m.group(1).strip().lower()
    if alvo not in PROGNOSTICADORES:
        return None
    chave, nome = PROGNOSTICADORES[alvo]
    url = _URL.search(celula)
    return Coluna(chave, nome, _data(sem_refs), url.group(1) if url else None)


def _distrito(valor: str) -> str:
    valor = valor.strip().upper()
    if valor in {"AL", "AT-LARGE", "0"}:
        return "00"
    if not valor.isdigit():
        raise ErroFormatoFonte(f"Distrito desconhecido: {valor!r}")
    return f"{int(valor):02d}"


def _estado(valor: str) -> str:
    valor = valor.strip()
    if valor.upper() in CODIGOS:
        return valor.upper()
    if valor in NOMES_ESTADOS:
        return NOMES_ESTADOS[valor]
    raise ErroFormatoFonte(f"Estado desconhecido: {valor!r}")


def _id_corrida(celula: str) -> str | None:
    m = _USHR.search(celula)
    if m is not None:
        return f"{_estado(m.group(1))}-{_distrito(m.group(2))}"
    s = _SENADO.search(celula)
    if s is None:
        return None
    especial = bool(s.group(1)) or "special" in celula.lower()
    nome = re.sub(r"\s*\(special\)", "", s.group(2), flags=re.I).strip()
    return f"{_estado(nome)}-{'S-especial' if especial else 'S'}"


def _classificacao(celula: str, chave: str, corrida: str) -> Classificacao | None:
    m = _CLASSIFICACAO.search(celula)
    if m is None:
        return None
    partes = [p.strip() for p in m.group(1).split("|")]
    categoria = CATEGORIAS.get(partes[0].lower())
    if categoria is None:
        raise ErroFormatoFonte(f"{corrida}: classificação desconhecida {partes[0]!r} ({chave})")
    if categoria == "empate":
        return Classificacao(prognosticador=chave, categoria=categoria, partido=None)
    partido = partes[1].upper() if len(partes) > 1 else ""
    if partido not in {"D", "R", "I"}:
        raise ErroFormatoFonte(f"{corrida}: partido desconhecido {partido!r} ({chave})")
    lado = cast(Literal["D", "R", "I"], partido)
    return Classificacao(prognosticador=chave, categoria=categoria, partido=lado)


def _cabecalho(tabela: str) -> list[Coluna]:
    """Colunas de classificações, das linhas antes da primeira corrida."""
    colunas: list[Coluna] = []
    for linha in linhas(tabela):
        if "USRaceRating" in linha:
            break
        for parte in re.split(r"^\s*!", linha, flags=re.M):
            coluna = _coluna(parte)
            if coluna is not None:
                colunas.append(coluna)
    if not colunas:
        raise ErroFormatoFonte("Tabela de classificações sem colunas reconhecidas")
    if len({c.chave for c in colunas}) != len(colunas):
        raise ErroFormatoFonte("Prognosticador repetido no cabeçalho")
    return colunas


def ler_tabela(tabela: str) -> Tabela:
    """Lê uma tabela de classificações: colunas pelo cabeçalho, uma corrida por linha."""
    # As células costumam vir alinhadas depois de um comentário (``<!--Cook--> | ...``);
    # sem o comentário ficam espaços antes do ``|``, que o wikitexto ignora.
    tabela = re.sub(r"^[ \t]+(?=[|!])", "", sem_comentarios(tabela), flags=re.M)
    colunas = _cabecalho(tabela)
    corridas: list[CorridaPrognosticos] = []
    vistos: set[str] = set()
    for celulas in grelha(tabela):
        if not any("USRaceRating" in c for c in celulas):
            continue
        corrida = _id_corrida(celulas[0])
        if corrida is None:
            raise ErroFormatoFonte(f"Linha sem corrida reconhecida: {celulas[0][:60]!r}")
        if corrida in vistos:
            raise ErroFormatoFonte(f"Corrida repetida: {corrida}")
        vistos.add(corrida)
        # As classificações são as últimas colunas da linha, pela ordem do cabeçalho; uma
        # célula a menos deslocaria todas, por isso cada uma tem de ter classificação.
        finais = celulas[-len(colunas) :]
        com = sum("USRaceRating" in c for c in celulas)
        if len(celulas) <= len(colunas) or com != len(colunas):
            raise ErroFormatoFonte(f"{corrida}: faltam colunas de classificação")
        if not all("USRaceRating" in c for c in finais):
            raise ErroFormatoFonte(f"{corrida}: classificações fora do lugar")
        lidas = [
            c
            for col, cel in zip(colunas, finais, strict=True)
            if (c := _classificacao(cel, col.chave, corrida)) is not None
        ]
        if lidas:
            corridas.append(CorridaPrognosticos(id=corrida, classificacoes=tuple(lidas)))
    if not corridas:
        raise ErroFormatoFonte("Tabela de classificações sem corridas")
    return Tabela(tuple(colunas), tuple(corridas))


def ler_senado(wikitexto: str) -> Tabela:
    """Primeira tabela com classificações depois do título "Predictions"."""
    texto = sem_comentarios(wikitexto)
    m = re.search(r"^==\s*Predictions\s*==\s*$", texto, flags=re.M)
    if m is None:
        raise ErroFormatoFonte("Página do Senado sem secção Predictions")
    for tabela in tabelas(texto[m.end() :]):
        if "USRaceRating" in tabela:
            return ler_tabela(tabela)
    raise ErroFormatoFonte("Secção Predictions sem tabela de classificações")


def ler_camara(wikitexto: str) -> Tabela:
    """Primeira tabela com classificações da página das classificações da Câmara."""
    texto = sem_comentarios(wikitexto)
    for tabela in tabelas(texto):
        if "USRaceRating" in tabela:
            return ler_tabela(tabela)
    raise ErroFormatoFonte("Página da Câmara sem tabela de classificações")


def agora_utc() -> datetime:
    return datetime.now(UTC)
