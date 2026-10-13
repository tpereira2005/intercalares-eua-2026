"""Leitura dos PDF "Absentee Ballot Statistics" do Iowa.

Cada página traz parte de um relatório diário, com a data no rodapé ("Data Pulled: 7:00
AM (UTC)" em 2024, "Data from night before report date" em 2022): os números são os do
fim do dia anterior. O texto tem três níveis, reconhecidos pelo rótulo:

* unidade: "United States Representative District 1", um condado, ou "Grand Total";
* partido de registo: "Democrat", "Republican", "No Party", "Libertarian", "Other";
* forma de receção, com pedidos, emitidos e recebidos ("Ballot not yet returned by
  voter" só tem pedidos e emitidos).

Uma unidade pode continuar na página seguinte; quando o mesmo dia aparece duas vezes, o
último relatório desse dia ganha. Confere-se, em cada dia, que as formas de receção somam
os recebidos de cada partido, que os partidos somam a unidade e, por distrito, que os
distritos somam o total estadual. Um ficheiro que falhe é recusado.
"""

import re
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path

import polars as pl
from pypdf import PdfReader

from pipeline.comum.condados import chave, fips_por_nome
from pipeline.comum.erros import ErroFormatoFonte
from pipeline.connectors.early_vote.ia.fontes import Nivel

ESQUEMA_RETRATOS = {
    "dados_ate": pl.Date,
    "unidade": pl.String,
    "partido": pl.String,
    "tipo": pl.String,
    "n": pl.Int64,
}
"""Totais acumulados até ``dados_ate``: ``unidade`` é o número do distrito ou o FIPS do
condado; ``tipo`` é ``pedidos``, ``correio``, ``presencial`` ou ``pendentes``."""

PARTIDOS = {
    "DEMOCRAT": "dem",
    "REPUBLICAN": "rep",
    "NO PARTY": "nao_afiliado",
    "LIBERTARIAN": "outro",
    "OTHER": "outro",
}
"""Partido de registo. Os pequenos partidos juntam-se em ``outro``."""

PRESENCIAL = {"COUNTER / IN-OFFICE", "IN-PERSON", "SATELLITE"}
"""Voto no balcão do auditor do condado ou num local satélite: o voto antecipado presencial."""

CORREIO = {"MAIL", "MAILING", "DROP BOX", "E-MAIL", "FAX", "HEALTH CARE FACILITY"}
"""Boletim enviado ao eleitor e devolvido (correio, caixa, lar ou hospital, militares)."""

PENDENTE = "BALLOT NOT YET RETURNED BY VOTER"

_LINHA = re.compile(r"^(?P<rotulo>.*?\S)\s+(?P<a>\d+)(?:\s+(?P<b>\d+))?(?:\s+(?P<c>\d+))?$")
_DATA = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})\s*$")
_DISTRITO = re.compile(r"^UNITED STATES REPRESENTATIVE DISTRICT (\d{1,2})$")
_TOTAL = "GRAND TOTAL"


@dataclass
class _Estado:
    """Unidade e partido correntes, que continuam de uma página para a seguinte."""

    unidade: str | None = None
    partido: str | None = None
    linhas: list[tuple[str, str, str, int]] = field(default_factory=list)
    """(unidade, partido, tipo, n) da página atual; o partido ``total`` guarda os
    recebidos da unidade e dos partidos, para as verificações."""


def _numeros(m: re.Match[str]) -> list[int]:
    return [int(x) for x in (m["a"], m["b"], m["c"]) if x is not None]


def _recebidos(numeros: list[int]) -> int:
    """Recebidos, a terceira coluna. As colunas vazias à direita ficam em branco: no início
    do ciclo há linhas só com pedidos ("Other 1"), e formas como "Mailing 2 2" (boletins
    a caminho do eleitor, em 2022) não têm recebidos. As somas de ``_verificar`` apanham
    qualquer desalinhamento."""
    return numeros[2] if len(numeros) == 3 else 0


def _unidade(rotulo: str, nivel: Nivel) -> str | None:
    if rotulo == _TOTAL:
        return "total"
    if nivel == "distrito":
        m = _DISTRITO.match(rotulo)
        return str(int(m.group(1))) if m else None
    return fips_por_nome("IA").get(chave(rotulo))


def _ler_linha(texto: str, nivel: Nivel, estado: _Estado, onde: str) -> None:
    m = _LINHA.match(texto.strip())
    if m is None:
        return
    rotulo = re.sub(r"\s+", " ", m["rotulo"]).upper()
    numeros = _numeros(m)
    unidade = _unidade(rotulo, nivel)
    if unidade is not None:
        estado.unidade, estado.partido = unidade, None
        estado.linhas.append((unidade, "total", "recebidos", _recebidos(numeros)))
        return
    if estado.unidade is None:
        return  # cabeçalho antes da primeira unidade
    if rotulo == PENDENTE:
        # Pedidos e emitidos (às vezes só um número); por vezes também um recebido, que a
        # fonte conta nos recebidos do partido: entra como correio para os totais baterem.
        if estado.partido is None:
            msg = f"{onde}: forma de receção sem partido: {texto!r}"
            raise ErroFormatoFonte(msg)
        estado.linhas.append(
            (estado.unidade, estado.partido, "pendentes", numeros[min(1, len(numeros) - 1)])
        )
        if recebidos := _recebidos(numeros):
            estado.linhas.append((estado.unidade, estado.partido, "correio", recebidos))
        return
    if rotulo in PARTIDOS:
        estado.partido = PARTIDOS[rotulo]
        estado.linhas += [
            (estado.unidade, estado.partido, "pedidos", numeros[0]),
            (estado.unidade, estado.partido, "recebidos", _recebidos(numeros)),
        ]
        return
    if estado.partido is None:
        msg = f"{onde}: forma de receção sem partido: {texto!r}"
        raise ErroFormatoFonte(msg)
    recebidos = _recebidos(numeros)
    if rotulo in PRESENCIAL:
        tipo = "presencial"
    elif rotulo in CORREIO or rotulo.isdigit():
        # Em 2024 aparece uma forma de receção com um código numérico ("37480") e um
        # boletim: conta como correio, para os totais baterem certo com a fonte.
        tipo = "correio"
    else:
        msg = f"{onde}: forma de receção desconhecida {rotulo!r}"
        raise ErroFormatoFonte(msg)
    estado.linhas.append((estado.unidade, estado.partido, tipo, recebidos))


def _data_pagina(texto: str, onde: str) -> date:
    for linha in reversed(texto.strip().splitlines()):
        m = _DATA.search(linha)
        if m:
            mes, dia, ano = (int(x) for x in m.groups())
            return date(ano, mes, dia)
    msg = f"{onde}: página sem data do relatório"
    raise ErroFormatoFonte(msg)


def _paginas(caminho: Path) -> Iterable[str]:
    with caminho.open("rb") as f:
        if f.read(5) != b"%PDF-":
            msg = f"{caminho.name} não é um PDF (a fonte devolveu outra coisa)"
            raise ErroFormatoFonte(msg)
    for pagina in PdfReader(caminho).pages:
        yield pagina.extract_text()


def ler_relatorios(caminho: Path, nivel: Nivel) -> pl.DataFrame:
    """Todos os relatórios diários do PDF, no formato de ``ESQUEMA_RETRATOS``."""
    return ler_paginas(_paginas(caminho), nivel, caminho.name)


def ler_paginas(paginas: Iterable[str], nivel: Nivel, nome: str) -> pl.DataFrame:
    """Como ``ler_relatorios``, a partir do texto de cada página."""
    estado = _Estado()
    por_dia: dict[date, dict[tuple[str, str, str], int]] = {}
    vistos: dict[date, set[str]] = {}
    for i, texto in enumerate(paginas, start=1):
        onde = f"{nome}, página {i}"
        relatorio = _data_pagina(texto, onde)
        estado.linhas = []
        for linha in texto.splitlines():
            _ler_linha(linha, nivel, estado, onde)
        dia = por_dia.setdefault(relatorio, {})
        unidades = vistos.setdefault(relatorio, set())
        for unidade, partido, tipo, n in estado.linhas:
            chave_ = (unidade, partido, tipo)
            if partido == "total" and unidade in unidades:
                # O mesmo dia publicado outra vez: o relatório mais recente substitui.
                for k in [k for k in dia if k[0] == unidade]:
                    del dia[k]
            unidades.add(unidade)
            dia[chave_] = dia.get(chave_, 0) + n
    if not por_dia:
        msg = f"{nome}: sem relatórios"
        raise ErroFormatoFonte(msg)
    linhas = []
    for relatorio, valores in sorted(por_dia.items()):
        _verificar(valores, nivel, f"{nome}, relatório de {relatorio}")
        dados_ate = relatorio - timedelta(days=1)
        linhas += [
            {"dados_ate": dados_ate, "unidade": u, "partido": p, "tipo": t, "n": n}
            for (u, p, t), n in valores.items()
            if p != "total" and u != "total" and t != "recebidos"
        ]
    return pl.DataFrame(linhas, schema=ESQUEMA_RETRATOS).sort(
        "dados_ate", "unidade", "partido", "tipo"
    )


def _verificar(valores: dict[tuple[str, str, str], int], nivel: Nivel, onde: str) -> None:
    unidades = {u for u, _, _ in valores if u != "total"}
    for u in unidades:
        partidos = {p for uu, p, _ in valores if uu == u and p != "total"}
        soma_partidos = 0
        for p in partidos:
            recebidos = valores.get((u, p, "recebidos"), 0)
            formas = valores.get((u, p, "correio"), 0) + valores.get((u, p, "presencial"), 0)
            if formas != recebidos:
                msg = f"{onde}: {u}/{p}, as formas de receção somam {formas}, não {recebidos}"
                raise ErroFormatoFonte(msg)
            soma_partidos += recebidos
        total = valores.get((u, "total", "recebidos"))
        if total is not None and total != soma_partidos:
            msg = f"{onde}: {u}, os partidos somam {soma_partidos}, não {total}"
            raise ErroFormatoFonte(msg)
    estadual = valores.get(("total", "total", "recebidos"))
    if nivel == "distrito" and estadual is not None:
        soma = sum(v for (u, p, t), v in valores.items() if u != "total" and p == "total")
        if soma != estadual:
            msg = f"{onde}: os distritos somam {soma}, o total estadual diz {estadual}"
            raise ErroFormatoFonte(msg)
