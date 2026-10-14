"""Leitura das folhas diárias "Election Activity" do Colorado.

Cada folha (XLSX) traz, entre outras, estas tabelas, com uma coluna por partido de
registo e uma coluna "Grand Total":

* ``Returned_Mail_Ballots_GenderAge`` e ``In_Person_Ballots_GenderAge``: um bloco por
  género ("Female", "Male", "Not Disclosed", "X") com o subtotal e as faixas "<18",
  "18-24", "25-34", ..., "75 AND OVER";
* ``All_Returned_Ballots_By_County`` e ``In_Person_Ballots_By_County`` (em 2022,
  ``In_Person_by_Party_County``): uma linha por condado.

Não há idade por condado: a idade e os condados ficam em tabelas separadas. O correio por
condado é o total menos o presencial (a folha de 2022 não tem a tabela de correio).

Antes de aceitar uma folha, conferimos que os partidos somam o "Grand Total" em cada
linha, que as faixas somam o subtotal de cada género, que os géneros e os condados somam
a linha "Grand Total", e que correio mais presencial por idade dá o mesmo total que os
condados. Uma folha que falhe é recusada inteira.

O Excel é lido diretamente (``zipfile`` e XML), sem dependências: só se leem números e
texto das células.
"""

import re
import zipfile
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from xml.etree import ElementTree as ET

import polars as pl

from pipeline.comum.condados import chave, fips_por_nome
from pipeline.comum.erros import ErroFormatoFonte

ESQUEMA_IDADE = {
    "dados_ate": pl.Date,
    "faixa": pl.String,
    "partido": pl.String,
    "tipo": pl.String,
    "n": pl.Int64,
}
"""Totais acumulados até ``dados_ate`` por faixa etária, partido de registo e ``tipo``
(``correio`` ou ``presencial``), somando os géneros."""

ESQUEMA_CONDADOS = {
    "dados_ate": pl.Date,
    "fips_condado": pl.String,
    "partido": pl.String,
    "tipo": pl.String,
    "n": pl.Int64,
}

PARTIDOS = {"DEM": "dem", "REP": "rep", "UAF": "nao_afiliado"}
"""Partido de registo. Os pequenos partidos (ACN, APV, CTR, GRN, LBR, ...) vão para
``outro``."""

FAIXAS = {
    "<18": "18-24",
    "18-24": "18-24",
    "25-34": "25-34",
    "35-44": "35-44",
    "45-54": "45-54",
    "55-64": "55-64",
    "65-74": "65-74",
    "75 AND OVER": "75+",
}
"""Faixas da fonte. "<18" são pré-recenseados que fazem 18 anos até ao dia da eleição:
juntam-se aos 18-24, como na faixa canónica."""

_NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
_REL = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"
_TOTAL = "GRAND TOTAL"
_FIM = "END OF WORKSHEET"


def _coluna(referencia: str) -> int:
    letras = re.match(r"[A-Z]+", referencia)
    if letras is None:
        msg = f"Referência de célula inválida: {referencia!r}"
        raise ErroFormatoFonte(msg)
    n = 0
    for c in letras.group(0):
        n = n * 26 + ord(c) - 64
    return n - 1


def _xml(dados: bytes) -> ET.Element:
    return ET.fromstring(dados)  # noqa: S314 (o expat do Python 3.12 recusa expansões de entidades)


def folhas(caminho: Path) -> dict[str, list[list[str]]]:
    """Todas as folhas do livro, como linhas de texto (células vazias a ``""``)."""
    try:
        livro = zipfile.ZipFile(caminho)
    except zipfile.BadZipFile as erro:
        msg = f"{caminho.name} não é um XLSX (a fonte devolveu outra coisa)"
        raise ErroFormatoFonte(msg) from erro
    with livro:
        nomes = set(livro.namelist())
        partilhadas: list[str] = []
        if "xl/sharedStrings.xml" in nomes:
            raiz = _xml(livro.read("xl/sharedStrings.xml"))
            partilhadas = ["".join(t.text or "" for t in si.iter(f"{_NS}t")) for si in raiz]
        relacoes = {
            r.get("Id"): r.get("Target", "") for r in _xml(livro.read("xl/_rels/workbook.xml.rels"))
        }
        resultado: dict[str, list[list[str]]] = {}
        for folha in _xml(livro.read("xl/workbook.xml")).iter(f"{_NS}sheet"):
            alvo = relacoes.get(folha.get(_REL), "").lstrip("/")
            alvo = alvo if alvo.startswith("xl/") else f"xl/{alvo}"
            if alvo not in nomes:
                continue
            linhas = []
            for linha in _xml(livro.read(alvo)).iter(f"{_NS}row"):
                celulas: dict[int, str] = {}
                for c in linha.iter(f"{_NS}c"):
                    v = c.find(f"{_NS}v")
                    tipo = c.get("t")
                    if tipo == "inlineStr":
                        texto = "".join(t.text or "" for t in c.iter(f"{_NS}t"))
                    elif v is None or v.text is None:
                        texto = ""
                    elif tipo == "s":
                        texto = partilhadas[int(v.text)]
                    else:
                        texto = v.text
                    celulas[_coluna(c.get("r", "A"))] = texto.strip()
                largura = max(celulas, default=-1) + 1
                linhas.append([celulas.get(i, "") for i in range(largura)])
            resultado[folha.get("name", "")] = linhas
    return resultado


@dataclass(frozen=True, slots=True)
class _Tabela:
    rotulos: list[str]
    """Rótulo de cada linha de dados (condado, género ou faixa), pela ordem da folha."""

    valores: list[dict[str, int]]
    """Votos por partido da fonte em cada linha."""

    totais: list[int]
    """Coluna "Grand Total" de cada linha."""

    total: dict[str, int] | None
    """Linha "Grand Total", por partido, com a chave ``_TOTAL`` para o total geral."""


def _inteiro(texto: str, onde: str) -> int:
    if texto == "":
        return 0
    try:
        numero = float(texto)
    except ValueError as erro:
        msg = f"{onde}: valor não numérico {texto!r}"
        raise ErroFormatoFonte(msg) from erro
    if numero < 0 or numero != int(numero):
        msg = f"{onde}: contagem inválida {texto!r}"
        raise ErroFormatoFonte(msg)
    return int(numero)


def _tabela(linhas: list[list[str]], cabecalho: str, onde: str) -> _Tabela:
    """Lê a tabela que começa na linha cujo primeiro texto começa por ``cabecalho``."""
    inicio = next(
        (i for i, ln in enumerate(linhas) if ln and ln[0].upper().startswith(cabecalho)), None
    )
    if inicio is None:
        msg = f"{onde}: sem cabeçalho {cabecalho!r}"
        raise ErroFormatoFonte(msg)
    cabecalhos = [c.upper() for c in linhas[inicio]]
    if _TOTAL not in cabecalhos:
        msg = f"{onde}: sem coluna {_TOTAL!r}"
        raise ErroFormatoFonte(msg)
    col_total = cabecalhos.index(_TOTAL)
    partidos = {i: c for i, c in enumerate(cabecalhos[1:col_total], start=1) if c}
    if not {"DEM", "REP", "UAF"} <= set(partidos.values()):
        msg = f"{onde}: colunas de partido inesperadas {sorted(partidos.values())}"
        raise ErroFormatoFonte(msg)
    rotulos: list[str] = []
    valores: list[dict[str, int]] = []
    totais: list[int] = []
    total: dict[str, int] | None = None
    for numero, ln in enumerate(linhas[inicio + 1 :], start=inicio + 2):
        rotulo = ln[0] if ln else ""
        if rotulo.upper() == _FIM or (not rotulo and not any(ln)):
            if rotulos:
                break
            continue
        if not rotulo:
            continue
        celula = f"{onde}, linha {numero}"
        por_partido = {
            p: _inteiro(ln[i] if i < len(ln) else "", celula) for i, p in partidos.items()
        }
        geral = _inteiro(ln[col_total] if col_total < len(ln) else "", celula)
        if sum(por_partido.values()) != geral:
            msg = f"{celula} ({rotulo}): os partidos somam {sum(por_partido.values())}, não {geral}"
            raise ErroFormatoFonte(msg)
        if rotulo.upper() == _TOTAL:
            total = {**por_partido, _TOTAL: geral}
            break
        rotulos.append(rotulo)
        valores.append(por_partido)
        totais.append(geral)
    return _Tabela(rotulos, valores, totais, total)


def _soma(linhas: Iterable[dict[str, int]]) -> dict[str, int]:
    soma: dict[str, int] = {}
    for ln in linhas:
        for k, v in ln.items():
            soma[k] = soma.get(k, 0) + v
    return soma


def _conferir_total(tabela: _Tabela, linhas: list[int], onde: str) -> int:
    """Confere que ``linhas`` somam a linha "Grand Total" e devolve o total geral."""
    if tabela.total is None:
        msg = f"{onde}: sem a linha {_TOTAL!r}"
        raise ErroFormatoFonte(msg)
    soma = _soma(tabela.valores[i] for i in linhas)
    esperado = {k: v for k, v in tabela.total.items() if k != _TOTAL}
    if soma != esperado:
        msg = f"{onde}: as linhas não somam a linha {_TOTAL!r}"
        raise ErroFormatoFonte(msg)
    return tabela.total[_TOTAL]


def _normalizar(valores: dict[str, int]) -> dict[str, int]:
    resultado: dict[str, int] = {}
    for p, n in valores.items():
        nosso = PARTIDOS.get(p, "outro")
        resultado[nosso] = resultado.get(nosso, 0) + n
    return resultado


def _por_idade(tabela: _Tabela, onde: str) -> tuple[dict[str, dict[str, int]], int]:
    """Votos por faixa (nossa) e partido (nosso), somando os géneros, com as somas
    conferidas, e o total geral."""
    generos: list[int] = []
    faixas_do_genero: dict[int, list[int]] = {}
    for i, rotulo in enumerate(tabela.rotulos):
        if rotulo.upper() in FAIXAS:
            if not generos:
                msg = f"{onde}: faixa {rotulo!r} antes do primeiro género"
                raise ErroFormatoFonte(msg)
            faixas_do_genero[generos[-1]].append(i)
        else:
            generos.append(i)
            faixas_do_genero[i] = []
    for g, faixas in faixas_do_genero.items():
        if _soma(tabela.valores[i] for i in faixas) != tabela.valores[g]:
            msg = f"{onde}: as faixas de {tabela.rotulos[g]!r} não somam o subtotal"
            raise ErroFormatoFonte(msg)
    total = _conferir_total(tabela, generos, onde)
    resultado: dict[str, dict[str, int]] = {}
    for faixas in faixas_do_genero.values():
        for i in faixas:
            nossa = FAIXAS[tabela.rotulos[i].upper()]
            soma = _soma([resultado.get(nossa, {}), _normalizar(tabela.valores[i])])
            resultado[nossa] = soma
    return resultado, total


def _por_condado(tabela: _Tabela, onde: str) -> tuple[dict[str, dict[str, int]], int]:
    fips = fips_por_nome("CO")
    resultado: dict[str, dict[str, int]] = {}
    for rotulo, valores in zip(tabela.rotulos, tabela.valores, strict=True):
        codigo = fips.get(chave(rotulo))
        if codigo is None:
            msg = f"{onde}: condado desconhecido {rotulo!r}"
            raise ErroFormatoFonte(msg)
        if codigo in resultado:
            msg = f"{onde}: condado repetido {rotulo!r}"
            raise ErroFormatoFonte(msg)
        resultado[codigo] = _normalizar(valores)
    if set(resultado) != set(fips.values()):
        msg = f"{onde}: {len(resultado)} condados, não {len(set(fips.values()))}"
        raise ErroFormatoFonte(msg)
    return resultado, _conferir_total(tabela, list(range(len(tabela.rotulos))), onde)


def _folha(
    livro: dict[str, list[list[str]]], *palavras: str, inicio: str = ""
) -> tuple[str, list[list[str]]]:
    """A folha cujo nome começa por ``inicio`` e tem todas as ``palavras`` (sem distinguir
    maiúsculas nem sublinhados)."""
    encontradas = [
        (nome, linhas)
        for nome, linhas in livro.items()
        if (simples := nome.upper().replace("_", "")).startswith(inicio)
        and all(p in simples for p in palavras)
    ]
    if len(encontradas) != 1:
        msg = f"Esperava uma folha com {palavras}, encontrei {[n for n, _ in encontradas]}"
        raise ErroFormatoFonte(msg)
    return encontradas[0]


@dataclass(frozen=True, slots=True)
class Relatorio:
    dados_ate: date
    idade: pl.DataFrame
    """No formato de ``ESQUEMA_IDADE``."""

    condados: pl.DataFrame
    """No formato de ``ESQUEMA_CONDADOS``."""


def ler_folha(caminho: Path, dados_ate: date) -> Relatorio:
    """Lê e confere uma folha diária. ``dados_ate`` é a data dos dados (a do nome)."""
    livro = folhas(caminho)
    nome = caminho.name
    idade: dict[str, dict[str, dict[str, int]]] = {}
    totais_idade: dict[str, int] = {}
    for tipo, palavra in (("correio", "MAIL"), ("presencial", "PERSON")):
        folha, linhas = _folha(livro, palavra, "GENDERAGE")
        tabela = _tabela(linhas, "GENDER/AGE", f"{nome}, {folha}")
        idade[tipo], totais_idade[tipo] = _por_idade(tabela, f"{nome}, {folha}")

    folha_todos, linhas_todos = _folha(livro, "COUNTY", inicio="ALL")
    todos = _tabela(linhas_todos, "COUNTY", f"{nome}, {folha_todos}")
    folha_pres, linhas_pres = _folha(livro, "PERSON", "COUNTY")
    pres = _tabela(linhas_pres, "COUNTY", f"{nome}, {folha_pres}")
    por_condado_todos, total_todos = _por_condado(todos, f"{nome}, {folha_todos}")
    por_condado_pres, total_pres = _por_condado(pres, f"{nome}, {folha_pres}")
    if totais_idade["presencial"] != total_pres:
        msg = (
            f"{nome}: presencial por idade ({totais_idade['presencial']}) e por condado "
            f"({total_pres}) não batem"
        )
        raise ErroFormatoFonte(msg)
    if totais_idade["correio"] + totais_idade["presencial"] != total_todos:
        msg = (
            f"{nome}: correio e presencial por idade somam "
            f"{totais_idade['correio'] + totais_idade['presencial']}, os condados "
            f"{total_todos}"
        )
        raise ErroFormatoFonte(msg)

    linhas_idade = [
        {"dados_ate": dados_ate, "faixa": f, "partido": p, "tipo": tipo, "n": n}
        for tipo, faixas in idade.items()
        for f, partidos in faixas.items()
        for p, n in partidos.items()
    ]
    linhas_condados = []
    for codigo, partidos in por_condado_todos.items():
        presencial = por_condado_pres[codigo]
        for p, n in partidos.items():
            correio = n - presencial.get(p, 0)
            if correio < 0:
                msg = f"{nome}: {codigo}/{p}, mais votos presenciais do que no total"
                raise ErroFormatoFonte(msg)
            linhas_condados += [
                {"dados_ate": dados_ate, "fips_condado": codigo, "partido": p,
                 "tipo": "correio", "n": correio},
                {"dados_ate": dados_ate, "fips_condado": codigo, "partido": p,
                 "tipo": "presencial", "n": presencial.get(p, 0)},
            ]  # fmt: skip
    return Relatorio(
        dados_ate,
        pl.DataFrame(linhas_idade, schema=ESQUEMA_IDADE).sort("faixa", "partido", "tipo"),
        pl.DataFrame(linhas_condados, schema=ESQUEMA_CONDADOS).sort(
            "fips_condado", "partido", "tipo"
        ),
    )
