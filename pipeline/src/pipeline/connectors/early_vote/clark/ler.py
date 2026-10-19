"""Leitura da página agregada de afluência presencial de Clark County.

A página tem uma tabela com o total acumulado ("Accumulated Total") e uma tabela por semana
("Daily Turnout - Week 1", "Week 2") com um local de voto por linha e um dia por coluna. As
colunas dos dias futuros vêm vazias. Só se lê o que está visível, sem nada pessoal.
"""

import re
from dataclasses import dataclass
from datetime import date
from html.parser import HTMLParser

from pipeline.comum.erros import ErroFormatoFonte

ANO = 2026
MAXIMO_SEMANAS = 2
_NUMERO = re.compile(r"\d{1,3}(,\d{3})*|\d+")
_DIA = re.compile(r"(\d{1,2})/(\d{1,2})")


class ErroFormatoClark(ErroFormatoFonte):
    """A página de Clark County não tem a estrutura esperada ou os números não batem certo."""


@dataclass(frozen=True, slots=True)
class AfluenciaClark:
    acumulado: int
    """Votos presenciais acumulados, segundo a linha "Accumulated Total"."""

    por_dia: dict[date, int]
    """Votos presenciais de cada dia já com valor (os dias futuros ficam de fora)."""

    @property
    def ultimo_dia(self) -> date:
        return max(self.por_dia)


class _Tabelas(HTMLParser):
    """Recolhe o texto das células de cada linha de cada tabela (as aninhadas incluídas)."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.tabelas: list[list[list[str]]] = []
        self._pilha: list[list[list[str]]] = []
        self._linha: list[list[str] | None] = []
        self._celula: list[list[str] | None] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "table":
            self._pilha.append([])
            self._linha.append(None)
            self._celula.append(None)
        elif not self._pilha:
            return
        elif tag == "tr":
            self._linha[-1] = []
        elif tag in ("td", "th") and self._linha[-1] is not None:
            self._celula[-1] = []

    def handle_endtag(self, tag: str) -> None:
        if not self._pilha:
            return
        if tag == "table":
            self.tabelas.append(self._pilha.pop())
            self._linha.pop()
            self._celula.pop()
            return
        linha, celula = self._linha[-1], self._celula[-1]
        if tag in ("td", "th") and linha is not None and celula is not None:
            linha.append(" ".join("".join(celula).split()))
            self._celula[-1] = None
        elif tag == "tr" and linha is not None:
            if linha:
                self._pilha[-1].append(linha)
            self._linha[-1] = None

    def handle_data(self, data: str) -> None:
        if self._celula and self._celula[-1] is not None:
            self._celula[-1].append(data)


def _numero(texto: str, onde: str) -> int:
    if not _NUMERO.fullmatch(texto):
        msg = f"Clark County, {onde}: {texto!r} não é um inteiro não negativo"
        raise ErroFormatoClark(msg)
    return int(texto.replace(",", ""))


def _acumulado(tabelas: list[list[list[str]]]) -> int:
    valores = [
        _numero(linha[1], "Accumulated Total")
        for tabela in tabelas
        for linha in tabela
        if len(linha) == 2 and linha[0] == "Accumulated Total"
    ]
    if len(valores) != 1:
        msg = f"Clark County: esperava uma linha 'Accumulated Total', encontrei {len(valores)}"
        raise ErroFormatoClark(msg)
    return valores[0]


def _datas(cabecalho: list[str]) -> list[date]:
    datas: list[date] = []
    for texto in cabecalho[1:-1]:
        m = _DIA.fullmatch(texto)
        if not m:
            msg = f"Clark County: cabeçalho de dia inesperado ({texto!r})"
            raise ErroFormatoClark(msg)
        try:
            datas.append(date(ANO, int(m[1]), int(m[2])))
        except ValueError as erro:
            msg = f"Clark County: data inválida no cabeçalho ({texto!r})"
            raise ErroFormatoClark(msg) from erro
    if not datas or cabecalho[-1] != "Totals":
        msg = "Clark County: a tabela semanal não termina na coluna 'Totals'"
        raise ErroFormatoClark(msg)
    return datas


def _semana(tabela: list[list[str]]) -> dict[date, int]:
    """Votos por dia de uma tabela semanal: a linha "Daily Totals" quando existe, senão a
    soma dos locais. Um dia sem nenhum valor nos locais ainda não aconteceu e fica de fora."""
    cabecalho = tabela[0]
    datas = _datas(cabecalho)
    locais: list[list[str]] = []
    totais: list[str] | None = None
    for linha in tabela[1:]:
        if len(linha) != len(cabecalho):
            msg = f"Clark County: linha com {len(linha)} células em vez de {len(cabecalho)}"
            raise ErroFormatoClark(msg)
        if linha[0] == "Daily Totals":
            totais = linha
        else:
            locais.append(linha)
    if not locais:
        msg = "Clark County: a tabela semanal não tem locais de voto"
        raise ErroFormatoClark(msg)
    por_dia: dict[date, int] = {}
    for i, dia in enumerate(datas, start=1):
        celulas = [linha[i] for linha in locais if linha[i]]
        if not celulas:
            continue
        soma = sum(_numero(c, f"{dia:%d/%m}") for c in celulas)
        if totais is not None:
            declarado = _numero(totais[i], f"Daily Totals de {dia:%d/%m}")
            if declarado != soma:
                msg = f"Clark County: os locais de {dia:%d/%m} somam {soma}, não {declarado}"
                raise ErroFormatoClark(msg)
        por_dia[dia] = soma
    return por_dia


def ler_afluencia(html: str) -> AfluenciaClark:
    """Total acumulado e votos presenciais por dia, validados entre si.

    Falha com :class:`ErroFormatoClark` se a estrutura mudou (sem acumulado, sem tabela
    semanal, mais de duas semanas, números inválidos) ou se o acumulado não for a soma dos dias.
    """
    leitor = _Tabelas()
    leitor.feed(html)
    leitor.close()
    semanais = [
        t for t in leitor.tabelas if t and t[0] and t[0][0] == "Early Voting Site" and len(t[0]) > 2
    ]
    if not 1 <= len(semanais) <= MAXIMO_SEMANAS:
        msg = f"Clark County: esperava 1 ou 2 tabelas semanais, encontrei {len(semanais)}"
        raise ErroFormatoClark(msg)
    acumulado = _acumulado(leitor.tabelas)
    por_dia: dict[date, int] = {}
    for tabela in semanais:
        for dia, votos in _semana(tabela).items():
            if dia in por_dia:
                msg = f"Clark County: dia {dia:%d/%m} repetido"
                raise ErroFormatoClark(msg)
            por_dia[dia] = votos
    if not por_dia:
        msg = "Clark County: nenhum dia com votos"
        raise ErroFormatoClark(msg)
    if sum(por_dia.values()) != acumulado:
        msg = f"Clark County: os dias somam {sum(por_dia.values())} e o acumulado diz {acumulado}"
        raise ErroFormatoClark(msg)
    return AfluenciaClark(acumulado, por_dia)
