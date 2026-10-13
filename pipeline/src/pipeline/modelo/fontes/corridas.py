"""Corridas à Câmara e ao Senado a partir das páginas anuais da Wikipedia.

Cada página anual ("2018 United States House of Representatives elections", etc.) tem
uma tabela por estado com o distrito, o Cook PVI, o incumbente, o desfecho e os
candidatos (com percentagens depois da eleição). Lemos essa tabela da mesma forma para
todos os anos, o que torna os backtests comparáveis com a previsão de 2026.
"""

import re
from dataclasses import dataclass, field

from pipeline.comum.erros import ErroFormatoFonte
from pipeline.modelo.fontes.wikitexto import (
    celulas,
    conteudo,
    linhas,
    partido_sombreado,
    pvi,
    sem_comentarios,
    texto_simples,
)

NOMES_ESTADOS: dict[str, str] = {
    "Alabama": "AL", "Alaska": "AK", "Arizona": "AZ", "Arkansas": "AR", "California": "CA",
    "Colorado": "CO", "Connecticut": "CT", "Delaware": "DE", "Florida": "FL", "Georgia": "GA",
    "Hawaii": "HI", "Idaho": "ID", "Illinois": "IL", "Indiana": "IN", "Iowa": "IA",
    "Kansas": "KS", "Kentucky": "KY", "Louisiana": "LA", "Maine": "ME", "Maryland": "MD",
    "Massachusetts": "MA", "Michigan": "MI", "Minnesota": "MN", "Mississippi": "MS",
    "Missouri": "MO", "Montana": "MT", "Nebraska": "NE", "Nevada": "NV",
    "New Hampshire": "NH", "New Jersey": "NJ", "New Mexico": "NM", "New York": "NY",
    "North Carolina": "NC", "North Dakota": "ND", "Ohio": "OH", "Oklahoma": "OK",
    "Oregon": "OR", "Pennsylvania": "PA", "Rhode Island": "RI", "South Carolina": "SC",
    "South Dakota": "SD", "Tennessee": "TN", "Texas": "TX", "Utah": "UT", "Vermont": "VT",
    "Virginia": "VA", "Washington": "WA", "West Virginia": "WV", "Wisconsin": "WI",
    "Wyoming": "WY",
}  # fmt: skip
CODIGOS = set(NOMES_ESTADOS.values())


@dataclass(frozen=True, slots=True)
class Candidato:
    nome: str
    partido: str
    """``D``, ``R`` ou ``O`` (outro partido ou independente)."""

    percentagem: float | None
    """Percentagem final dos votos; ``None`` antes da eleição."""


@dataclass(slots=True)
class Corrida:
    ano: int
    camara: str
    """``camara`` ou ``senado``."""

    estado: str
    distrito: str
    """Número do distrito (``"00"`` para distritos únicos) ou ``"S"``/``"S-especial"``."""

    pvi: float | None
    """Cook PVI em pontos (positivo D, negativo R) como publicado nesse ciclo."""

    incumbentes: list[tuple[str, str]] = field(default_factory=list)
    """Pares (nome, partido) dos titulares do lugar antes da eleição."""

    candidatos: list[Candidato] = field(default_factory=list)
    estado_texto: str = ""
    """Texto do desfecho ou da situação ("Incumbent re-elected.", "New seat", ...)."""

    @property
    def id(self) -> str:
        return f"{self.estado}-{self.distrito}"


_USHR = re.compile(r"\{\{\s*ushr\s*\|\s*([^|}]+?)\s*\|\s*([^|}]+?)\s*(?:\|[^}]*)?\}\}", re.I)
_SENADO = re.compile(
    r"\[\[\s*\d{4} United States Senate (special )?election in ([^|\]#]+?)\s*(?:\|[^\]]*)?\]\]",
    re.I,
)
_ANCORA = re.compile(r"^\s*\[\[#([^|\]]+)(?:\|[^\]]*)?\]\]")
_PARTIDO = re.compile(r"\(([^()]*)\)\s*(?:[\d.,]+\s*%|Unopposed|$)", re.I)
_PERCENTAGEM = re.compile(r"([\d]+(?:\.\d+)?)\s*%")


def _codigo_estado(valor: str) -> str:
    valor = valor.strip()
    if valor.upper() in CODIGOS:
        return valor.upper()
    if valor in NOMES_ESTADOS:
        return NOMES_ESTADOS[valor]
    raise ErroFormatoFonte(f"Estado desconhecido: {valor!r}")


def _distrito(valor: str) -> str:
    valor = valor.strip().upper()
    if valor in {"AL", "AT-LARGE", "0"}:
        return "00"
    if not valor.isdigit():
        raise ErroFormatoFonte(f"Distrito desconhecido: {valor!r}")
    return f"{int(valor):02d}"


def _partido_candidato(texto: str) -> str:
    t = texto.lower()
    if t.startswith("democratic") or "democratic\u2013farmer" in t or "dfl" in t:
        return "D"
    if t.startswith("republican"):
        return "R"
    return "O"


def ler_candidatos(celula: str) -> list[Candidato]:
    """Lê a lista de candidatos (``* nome (Partido) 51.2%``) de uma célula."""
    resultado: list[Candidato] = []
    # Cada candidato começa por "*"; algumas linhas esquecem o "*" mas trazem a faixa.
    partes = re.split(
        r"\n\s*\*|^\s*\*|\n(?=\{\{\s*Party stripe)|plainlist\s*\|\s*\*",
        celula,
        flags=re.MULTILINE | re.IGNORECASE,
    )[1:]
    if not partes and "Party stripe" in celula:
        partes = [celula.split("|", 1)[-1] if "nowrap" in celula[:20] else celula]
    for parte in partes:
        # O fim da tabela ("|}") pode vir colado à última linha da lista.
        bruto = re.split(r"^\s*\|\}(?!\})", parte, maxsplit=1, flags=re.MULTILINE)[0]
        texto = texto_simples(bruto)
        # O partido é o último parêntese seguido de percentagem, "Unopposed" ou fim.
        ocorrencias = list(_PARTIDO.finditer(texto))
        if not ocorrencias:
            continue
        m = ocorrencias[-1]
        perc = _PERCENTAGEM.search(texto[m.end(1) :])
        nome = texto[: m.start()].strip(" ,")
        resultado.append(
            Candidato(
                nome=nome,
                partido=_partido_candidato(m.group(1)),
                percentagem=float(perc.group(1)) if perc else None,
            )
        )
    return resultado


def _e_celula_candidatos(c: str) -> bool:
    return "Party stripe" in c or bool(re.search(r"^\s*\*", c, flags=re.MULTILINE))


def _incumbente(nome_celula: str, partido_celula: str) -> tuple[str, str] | None:
    nome = texto_simples(conteudo(nome_celula))
    if not nome or nome.lower().startswith(("none", "vacant", "new seat")):
        return None
    partido = partido_sombreado(partido_celula) or partido_sombreado(nome_celula)
    if partido is None:
        texto = texto_simples(partido_celula).lower()
        partido = "D" if texto.startswith("democ") else "R" if texto.startswith("repub") else "I"
    nome = re.sub(r"\s*\((?:retiring|retired)[^)]*\)", "", nome, flags=re.I)
    return nome, partido


def ler_pagina(texto: str, ano: int, camara: str) -> list[Corrida]:
    """Lê todas as corridas de uma página anual (Câmara ou Senado)."""
    texto = sem_comentarios(texto)
    corridas: dict[str, Corrida] = {}
    pvis: dict[str, float] = {}
    # Algumas páginas abrem as tabelas com uma predefinição ({{USCongressElectionTableHead}})
    # em vez de "{|", por isso percorremos todas as linhas da página e não só as tabelas.
    ultima: Corrida | None = None
    for linha in linhas(texto):
        cs = celulas(linha)
        if not cs:
            ultima = None
            continue
        corrida, _ = _cabecalho(cs[0], ano, camara)
        if corrida is None:
            if ultima is not None and len(cs) >= 2 and "ushr" not in linha:
                _continuacao(ultima, cs)
            ultima = None if ultima is None or "|}" in linha else ultima
            continue
        if not any(_e_celula_candidatos(c) for c in cs[1:]):
            # Linhas sem candidatos (ex.: tabela de previsões do Senado) só trazem o PVI.
            valor = next((pvi(c) for c in cs[1:3] if pvi(c) is not None), None)
            if valor is not None:
                pvis.setdefault(corrida.id, valor)
            ultima = None
            continue
        _preencher(corrida, cs[1:])
        anterior = corridas.get(corrida.id)
        # As eleições especiais aparecem antes, numa tabela sem PVI; a linha principal ganha.
        if anterior is not None and (anterior.pvi is not None or corrida.pvi is None):
            ultima = None
            continue
        corridas[corrida.id] = corrida
        ultima = corrida if "rowspan" in cs[0] else None
    for corrida in corridas.values():
        if corrida.pvi is None:
            corrida.pvi = pvis.get(corrida.id)
    for corrida in corridas.values():
        if corrida.pvi is None and camara == "senado":
            # O PVI é do estado: a outra corrida do mesmo estado nesse ano serve.
            corrida.pvi = next(
                (
                    o.pvi
                    for o in corridas.values()
                    if o.estado == corrida.estado and o.pvi is not None
                ),
                None,
            )
    return list(corridas.values())


def _cabecalho(celula: str, ano: int, camara: str) -> tuple[Corrida | None, str]:
    if camara == "camara":
        m = _USHR.search(celula)
        if m is None:
            return None, ""
        try:
            estado = _codigo_estado(m.group(1))
            distrito = _distrito(m.group(2))
        except ErroFormatoFonte:
            return None, ""
        return Corrida(ano, camara, estado, distrito, None), ""
    m = _SENADO.search(celula)
    if m is not None:
        nome, especial = m.group(2), bool(m.group(1))
    else:
        # Tabela de previsões: ligações internas como [[#Arizona|Arizona]].
        a = _ANCORA.search(celula)
        if a is None:
            return None, ""
        nome, especial = a.group(1), False
    especial = especial or "special" in nome.lower() or "special" in celula.lower()
    nome = re.sub(r"\s*\(special\)|\s+special", "", nome, flags=re.I).strip()
    try:
        estado = _codigo_estado(nome)
    except ErroFormatoFonte:
        return None, ""
    distrito = "S-especial" if especial else "S"
    return Corrida(ano, camara, estado, distrito, None), ""


def _preencher(corrida: Corrida, cs: list[str]) -> None:
    indice_pvi = next((i for i, c in enumerate(cs) if pvi(c) is not None), None)
    if indice_pvi is not None:
        corrida.pvi = pvi(cs[indice_pvi])
    inicio = 0 if indice_pvi is None else indice_pvi + 1
    restantes = cs[inicio:]
    candidatos = [c for c in restantes if _e_celula_candidatos(c)]
    if candidatos:
        corrida.candidatos = ler_candidatos(candidatos[-1])
    if len(restantes) >= 2 and "new seat" not in restantes[0].lower():
        inc = _incumbente(restantes[0], restantes[1])
        if inc is not None:
            corrida.incumbentes.append(inc)
    corrida.estado_texto = " ".join(
        texto_simples(c) for c in restantes if not _e_celula_candidatos(c)
    )[:400]


def _continuacao(corrida: Corrida, cs: list[str]) -> None:
    """Linha extra de uma célula com ``rowspan``: outro incumbente no mesmo distrito."""
    if any(_e_celula_candidatos(c) for c in cs) and not corrida.candidatos:
        corrida.candidatos = ler_candidatos(next(c for c in cs if _e_celula_candidatos(c)))
    inc = _incumbente(cs[0], cs[1])
    if inc is not None and inc[1] in {"D", "R", "I"}:
        corrida.incumbentes.append(inc)
        corrida.estado_texto += " | " + " ".join(texto_simples(c) for c in cs[2:])[:200]
