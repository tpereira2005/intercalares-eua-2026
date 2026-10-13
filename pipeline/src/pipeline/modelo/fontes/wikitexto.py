"""Utilitários mínimos para ler tabelas em wikitexto.

Não interpretamos todo o MediaWiki: só o que as tabelas eleitorais usam (células,
predefinições de sombreado, ligações e listas). Qualquer linha que não se consiga
interpretar é reportada por quem chama, nunca ignorada em silêncio.
"""

import re
from collections.abc import Iterator

_COMENTARIO = re.compile(r"<!--.*?-->", re.DOTALL)
_REF = re.compile(r"<ref[^>/]*/>|<ref[^>]*>.*?</ref>", re.DOTALL | re.IGNORECASE)
_LIGACAO = re.compile(r"\[\[(?:[^\]|]*\|)?([^\]]*)\]\]")
_SORTNAME = re.compile(r"\{\{\s*sortname\s*\|([^|}]*)\|([^|}]*)[^}]*\}\}", re.IGNORECASE)
_HTML = re.compile(r"<[^>]+>")


def sem_comentarios(texto: str) -> str:
    """Remove comentários HTML e referências, que só atrapalham a leitura das células."""
    return _REF.sub("", _COMENTARIO.sub("", texto))


def texto_simples(celula: str) -> str:
    """Converte uma célula em texto legível: nomes, ligações e texto, sem marcação."""
    texto = _SORTNAME.sub(lambda m: f"{m.group(1).strip()} {m.group(2).strip()}", celula)
    texto = _LIGACAO.sub(r"\1", texto)
    texto = re.sub(r"\{\{\s*(?:small|nowrap)\s*\|([^{}]*)\}\}", r"\1", texto, flags=re.I)
    anterior = None
    while anterior != texto:
        anterior = texto
        texto = re.sub(r"\{\{[^{}]*\}\}", "", texto)
    texto = _HTML.sub(" ", texto).replace("'''", "").replace("''", "")
    texto = texto.replace("{{", " ").replace("}}", " ")
    return re.sub(r"\s+", " ", texto).strip()


def tabelas(texto: str) -> Iterator[str]:
    """Devolve o corpo de cada tabela ``{| ... |}`` de nível superior, por ordem."""
    profundidade = 0
    inicio = 0
    for m in re.finditer(r"^\s*(\{\||\|\})", texto, flags=re.MULTILINE):
        if m.group(1) == "{|":
            if profundidade == 0:
                inicio = m.end()
            profundidade += 1
        elif profundidade > 0:
            profundidade -= 1
            if profundidade == 0:
                yield texto[inicio : m.start()]


def linhas(tabela: str) -> list[str]:
    """Divide o corpo de uma tabela nas suas linhas (separadas por ``|-``)."""
    return re.split(r"^\s*\|-[^\n]*$", tabela, flags=re.MULTILINE)


def celulas(linha: str) -> list[str]:
    """Divide uma linha nas células, respeitando predefinições e ligações com ``|``.

    Cada célula começa numa linha nova por ``|`` ou ``!``, ou na mesma linha por ``||``
    ou ``!!``. Atributos (``style=... |``) ficam na célula; quem lê usa expressões
    regulares sobre o conteúdo, por isso não os separamos.
    """
    resultado: list[str] = []
    atual: list[str] | None = None
    profundidade = 0
    for linha_texto in linha.split("\n"):
        inicio_celula = profundidade == 0 and linha_texto[:1] in {"|", "!"}
        if inicio_celula and not linha_texto.startswith(("|+", "|}")):
            if atual is not None:
                resultado.append("\n".join(atual))
            atual = [linha_texto[1:]]
        elif atual is not None:
            atual.append(linha_texto)
        profundidade = max(profundidade + _equilibrio(linha_texto), 0)
    if atual is not None:
        resultado.append("\n".join(atual))
    partidas: list[str] = []
    for c in resultado:
        partidas.extend(_dividir_inline(c))
    return partidas


def _equilibrio(texto: str) -> int:
    return texto.count("{{") + texto.count("[[") - texto.count("}}") - texto.count("]]")


def _dividir_inline(celula: str) -> list[str]:
    partes: list[str] = []
    profundidade = 0
    atual = 0
    i = 0
    while i < len(celula) - 1:
        par = celula[i : i + 2]
        if par in {"{{", "[["}:
            profundidade += 1
            i += 2
            continue
        if par in {"}}", "]]"}:
            profundidade = max(profundidade - 1, 0)
            i += 2
            continue
        if profundidade == 0 and par in {"||", "!!"}:
            partes.append(celula[atual:i])
            atual = i + 2
            i += 2
            continue
        i += 1
    partes.append(celula[atual:])
    return partes


_PVI = re.compile(
    r"shading PVI\s*\|\s*(?:(EVEN)|([DR])\s*\|\s*(?:value\s*=\s*)?([\d.]+))"
    r"|\{\{\s*sort\s*\|[^|}]*\|\s*(?:(EVEN)|([DR])\s*\+\s*([\d.]+))\s*\}\}"
    r"|(?:^|\|)\s*(?:(EVEN)|([DR])\s*\+\s*([\d.]+))\s*$",
    re.IGNORECASE | re.MULTILINE,
)


def pvi(celula: str) -> float | None:
    """Lê um Cook PVI e devolve-o em pontos, positivo para D e negativo para R."""
    m = _PVI.search(celula)
    if m is None:
        return None
    g = m.groups()
    for par, valor, even in ((g[1], g[2], g[0]), (g[4], g[5], g[3]), (g[7], g[8], g[6])):
        if even:
            return 0.0
        if par:
            numero = float(valor or "0")
            return numero if par.upper() == "D" else -numero
    return None


_PARTIDO_SOMBRA = re.compile(
    r"Party shading/(?:Text/)?(Democratic|Republican|Independent|Libertarian)",
    re.IGNORECASE,
)
_COR = {"#b0ceff": "D", "#ffb6b6": "R"}


def partido_sombreado(celula: str) -> str | None:
    """Partido indicado pelo sombreado de uma célula (``D``, ``R``, ``I`` ou ``None``)."""
    m = _PARTIDO_SOMBRA.search(celula)
    if m:
        return {"democratic": "D", "republican": "R"}.get(m.group(1).lower(), "I")
    cor = re.search(r"background(?:-color)?\s*:\s*(#[0-9a-fA-F]{6})", celula)
    if cor:
        return _COR.get(cor.group(1).lower())
    return None


def conteudo(celula: str) -> str:
    """Conteúdo de uma célula sem o prefixo de atributos (``style=... | conteúdo``)."""
    partes = _dividir_simples(celula)
    return (
        partes[-1]
        if (len(partes) > 1 and "=" in partes[-2])
        or (len(partes) > 1 and ("shading" in partes[0].lower()))
        else celula
    )


def _dividir_simples(celula: str) -> list[str]:
    partes: list[str] = []
    profundidade = 0
    atual = 0
    i = 0
    while i < len(celula):
        par = celula[i : i + 2]
        if par in {"{{", "[["}:
            profundidade += 1
            i += 2
            continue
        if par in {"}}", "]]"}:
            profundidade = max(profundidade - 1, 0)
            i += 2
            continue
        if profundidade == 0 and celula[i] == "|":
            partes.append(celula[atual:i])
            atual = i + 1
        i += 1
    partes.append(celula[atual:])
    return partes


_ROWSPAN = re.compile(r'rowspan\s*=\s*"?(\d+)"?', re.IGNORECASE)


def grelha(tabela: str) -> list[list[str]]:
    """Linhas de dados de uma tabela com os ``rowspan`` expandidos (cada linha completa)."""
    pendentes: dict[int, tuple[int, str]] = {}
    resultado: list[list[str]] = []
    for linha in linhas(tabela):
        cs = celulas(linha)
        if not cs or all(not c.strip() for c in cs):
            continue
        completa: list[str] = []
        fila = list(cs)
        coluna = 0
        while fila or coluna in pendentes:
            if coluna in pendentes:
                restantes, valor = pendentes[coluna]
                completa.append(valor)
                if restantes <= 1:
                    del pendentes[coluna]
                else:
                    pendentes[coluna] = (restantes - 1, valor)
            else:
                valor = fila.pop(0)
                completa.append(valor)
                prefixo = valor.split("|", 1)[0] if "|" in valor else ""
                m = _ROWSPAN.search(prefixo)
                if m and int(m.group(1)) > 1:
                    pendentes[coluna] = (int(m.group(1)) - 1, valor)
            coluna += 1
        resultado.append(completa)
    return resultado
