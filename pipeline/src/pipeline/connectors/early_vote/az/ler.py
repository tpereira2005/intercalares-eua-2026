"""Leitura da tabela de boletins antecipados do Arizona e do arquivo de retratos."""

import re
from datetime import date
from html.parser import HTMLParser
from pathlib import Path

import polars as pl

from pipeline.comum.erros import ErroFormatoFonte
from pipeline.connectors.early_vote.az import codigos, fontes

ESQUEMA_RETRATO = {
    "dados_ate": pl.Date,
    "fips_condado": pl.String,
    "devolvidos": pl.Int64,
    "emitidos": pl.Int64,
}
"""Uma linha por dia e condado: boletins devolvidos e emitidos até esse dia."""

CABECALHOS = ("County", "Returned", "Issued", "Registered", "Updated")
_NUMERO = re.compile(r"\d{1,3}(,\d{3})*|\d+")
_DATA = re.compile(r"\d{4}-\d{2}-\d{2}")


class _Tabela(HTMLParser):
    """Recolhe o texto das células (``th`` e ``td``) de cada linha das tabelas da página."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.tabelas = 0
        self.cabecalho: list[str] = []
        self.linhas: list[list[str]] = []
        self._celula: list[str] | None = None
        self._linha: list[str] | None = None
        self._na_tabela = False
        self._no_cabecalho = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "table":
            self.tabelas += 1
            self._na_tabela = True
        elif not self._na_tabela:
            return
        elif tag == "thead":
            self._no_cabecalho = True
        elif tag == "tr":
            self._linha = []
        elif tag in ("th", "td") and self._linha is not None:
            self._celula = []

    def handle_endtag(self, tag: str) -> None:
        if tag == "table":
            self._na_tabela = False
        elif tag == "thead":
            self._no_cabecalho = False
        elif tag in ("th", "td") and self._celula is not None and self._linha is not None:
            self._linha.append(" ".join("".join(self._celula).split()))
            self._celula = None
        elif tag == "tr" and self._linha is not None:
            if self._no_cabecalho:
                self.cabecalho = self._linha
            elif self._linha:
                self.linhas.append(self._linha)
            self._linha = None

    def handle_data(self, data: str) -> None:
        if self._celula is not None:
            self._celula.append(data)


def _chave(nome: str) -> str:
    return re.sub(r"[^A-Z]", "", nome.upper())


def _numero(texto: str, condado: str, coluna: str) -> int:
    limpo = texto.strip()
    if not _NUMERO.fullmatch(limpo):
        msg = f"Arizona, {condado}: {coluna} não é um inteiro não negativo ({texto!r})"
        raise ErroFormatoFonte(msg)
    return int(limpo.replace(",", ""))


def _data(texto: str, nome: str) -> date:
    try:
        if not _DATA.fullmatch(texto):
            raise ValueError(texto)
        return date.fromisoformat(texto)
    except ValueError as erro:
        msg = f"Arizona, {nome}: data de atualização inválida {texto!r}"
        raise ErroFormatoFonte(msg) from erro


def _linha(celulas: list[str]) -> tuple[str, int, int, str]:
    """Nome, devolvidos, emitidos e texto da data de uma linha, já validados."""
    if len(celulas) != len(CABECALHOS):
        msg = f"Arizona: linha com {len(celulas)} células, esperadas {len(CABECALHOS)}"
        raise ErroFormatoFonte(msg)
    nome, devolvidos_, emitidos_, inscritos_, atualizado = celulas
    devolvidos = _numero(devolvidos_, nome, "devolvidos")
    emitidos = _numero(emitidos_, nome, "emitidos")
    _numero(inscritos_, nome, "inscritos")
    if devolvidos > emitidos:
        msg = f"Arizona, {nome}: devolvidos ({devolvidos}) superam emitidos ({emitidos})"
        raise ErroFormatoFonte(msg)
    return nome, devolvidos, emitidos, atualizado


def _tabela(html: str) -> _Tabela:
    if fontes.TEXTO_LICENCA not in html:
        msg = "Arizona: os termos de reutilização já não aparecem na página; confirmar a licença"
        raise ErroFormatoFonte(msg)
    analisador = _Tabela()
    analisador.feed(html)
    if analisador.tabelas != 1:
        msg = f"Arizona: esperava-se 1 tabela, a página tem {analisador.tabelas}"
        raise ErroFormatoFonte(msg)
    if tuple(analisador.cabecalho) != CABECALHOS:
        msg = f"Arizona: cabeçalhos {analisador.cabecalho!r}, esperados {list(CABECALHOS)!r}"
        raise ErroFormatoFonte(msg)
    return analisador


def ler_pagina(html: str) -> pl.DataFrame:
    """Retrato atual no formato de ``ESQUEMA_RETRATO``.

    Valida o esquema da fonte: termos de utilização, cabeçalhos esperados, os 15 condados
    (sem repetidos nem desconhecidos), números inteiros não negativos, datas AAAA-MM-DD e
    devolvidos não superiores a emitidos. Se a tabela trouxer uma linha de total estadual,
    confere que os condados somam o total. Qualquer falha levanta ``ErroFormatoFonte``.
    """
    linhas: dict[str, dict[str, object]] = {}
    total: tuple[int, int] | None = None
    for celulas in _tabela(html).linhas:
        nome, devolvidos, emitidos, atualizado = _linha(celulas)
        chave = _chave(nome)
        if chave in codigos.TOTAIS_ESTADO:
            total = (devolvidos, emitidos)
            continue
        fips = codigos.FIPS_CONDADO.get(chave)
        if fips is None:
            msg = f"Arizona: condado desconhecido {nome!r}"
            raise ErroFormatoFonte(msg)
        if fips in linhas:
            msg = f"Arizona: condado repetido {nome!r}"
            raise ErroFormatoFonte(msg)
        linhas[fips] = {
            "dados_ate": _data(atualizado, nome),
            "fips_condado": fips,
            "devolvidos": devolvidos,
            "emitidos": emitidos,
        }

    em_falta = sorted(set(codigos.FIPS_CONDADO.values()) - set(linhas))
    if em_falta:
        nomes = [codigos.NOMES_CONDADO[f] for f in em_falta]
        msg = f"Arizona: faltam {len(em_falta)} condados: {', '.join(nomes)}"
        raise ErroFormatoFonte(msg)
    retrato = pl.DataFrame(list(linhas.values()), schema=ESQUEMA_RETRATO).sort("fips_condado")
    soma = (int(retrato["devolvidos"].sum()), int(retrato["emitidos"].sum()))
    if total is not None and soma != total:
        msg = f"Arizona: os condados somam {soma} (devolvidos, emitidos), o total diz {total}"
        raise ErroFormatoFonte(msg)
    return retrato


def juntar_arquivo(arquivo: pl.DataFrame | None, retrato: pl.DataFrame) -> pl.DataFrame:
    """Acrescenta o retrato ao arquivo; o retrato mais recente de cada condado e dia ganha."""
    chaves = ["dados_ate", "fips_condado"]
    if arquivo is None or arquivo.is_empty():
        return retrato.sort(chaves)
    return (
        pl.concat([arquivo.cast(ESQUEMA_RETRATO), retrato])  # type: ignore[arg-type]
        .unique(chaves, keep="last", maintain_order=True)
        .sort(chaves)
    )


def ler_arquivo(caminho: Path) -> pl.DataFrame | None:
    if not caminho.exists() or caminho.stat().st_size == 0:
        return None
    return pl.read_csv(caminho, schema=ESQUEMA_RETRATO)
