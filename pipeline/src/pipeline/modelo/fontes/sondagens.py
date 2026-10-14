"""Sondagens individuais: tabelas das páginas de cada corrida e ficheiro histórico da 538.

Cada sondagem fica numa ``Sondagem`` com a margem D-R em pontos (percentagem do total,
não do voto bipartidário), a data final do trabalho de campo, a amostra e a população.
"""

import csv
import re
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

from pipeline.modelo.fontes.wikitexto import (
    celulas,
    conteudo,
    grelha,
    linhas,
    sem_comentarios,
    tabelas,
    texto_simples,
)

MESES = {
    m: i + 1
    for i, m in enumerate(
        ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"]
    )
}


@dataclass(frozen=True, slots=True)
class Sondagem:
    corrida: str
    """Identificador da corrida (``NC-S``) ou ``US`` para o voto genérico."""

    ano: int
    instituto: str
    fim: date
    amostra: int | None
    populacao: str
    """``lv`` (eleitores prováveis), ``rv`` (registados), ``a`` (adultos) ou ``?``."""

    partidaria: bool
    """Sondagem encomendada por um partido ou campanha."""

    dem: float
    rep: float
    candidato_d: str = ""
    """Nome do candidato do lado democrata na pergunta (para não misturar cenários)."""

    candidato_r: str = ""

    @property
    def margem(self) -> float:
        return self.dem - self.rep


# --- Ficheiro histórico da 538 (pollster-ratings/raw_polls.csv, CC BY 4.0) -------------


def ler_538(caminho: Path, tipos: tuple[str, ...] = ("Sen-G", "House-G-US")) -> list[Sondagem]:
    """Lê as sondagens finais da 538 entre um Democrata e um Republicano."""
    resultado: list[Sondagem] = []
    with caminho.open(encoding="utf-8", newline="") as f:
        for linha in csv.DictReader(f):
            if linha["type_simple"] not in tipos:
                continue
            partidos = (linha["cand1_party"], linha["cand2_party"])
            if set(partidos) != {"DEM", "REP"}:
                continue
            p1, p2 = float(linha["cand1_pct"]), float(linha["cand2_pct"])
            dem, rep = (p1, p2) if partidos[0] == "DEM" else (p2, p1)
            n1, n2 = linha["cand1_name"], linha["cand2_name"]
            nome_d, nome_r = (n1, n2) if partidos[0] == "DEM" else (n2, n1)
            corrida = _corrida_538(linha)
            if corrida is None:
                continue
            amostra = linha["samplesize"]
            resultado.append(
                Sondagem(
                    corrida=corrida,
                    ano=int(linha["cycle"]),
                    instituto=linha["pollster"],
                    fim=date.fromisoformat(linha["polldate"]),
                    amostra=int(float(amostra)) if amostra not in {"", "NA"} else None,
                    populacao="?",
                    partidaria=linha["partisan"] not in {"", "NA"},
                    dem=dem,
                    rep=rep,
                    candidato_d=nome_d,
                    candidato_r=nome_r,
                )
            )
    return resultado


def resultados_538(caminho: Path) -> dict[tuple[int, str], float]:
    """Margem real D-R de cada corrida no ficheiro da 538 (para validar as nossas leituras)."""
    reais: dict[tuple[int, str], float] = {}
    with caminho.open(encoding="utf-8", newline="") as f:
        for linha in csv.DictReader(f):
            if linha["type_simple"] not in {"Sen-G", "House-G-US"}:
                continue
            partidos = (linha["cand1_party"], linha["cand2_party"])
            if set(partidos) != {"DEM", "REP"}:
                continue
            a1, a2 = float(linha["cand1_actual"]), float(linha["cand2_actual"])
            margem = a1 - a2 if partidos[0] == "DEM" else a2 - a1
            corrida = _corrida_538(linha)
            if corrida is None:
                continue
            reais[(int(linha["cycle"]), corrida)] = margem
    return reais


def _corrida_538(linha: dict[str, str]) -> str | None:
    """Identificador da corrida; segundas voltas (``Sen-R``, ``Sen-SR``) ficam de fora."""
    if linha["type_simple"] == "House-G-US":
        return "US"
    tipo = linha["race"].split("_")[1]
    if tipo == "Sen-G":
        return f"{linha['location']}-S"
    if tipo == "Sen-GS":
        return f"{linha['location']}-S-especial"
    return None


# --- Tabelas da Wikipedia -----------------------------------------------------------------

_DATA = re.compile(
    r"(?:(?P<m1>[A-Za-z]{3,9})\.?\s+)?(?P<d1>\d{1,2})(?:,\s*(?P<a1>\d{4}))?\s*"
    r"[\u2013\u2014-]\s*(?:(?P<m2>[A-Za-z]{3,9})\.?\s+)?(?P<d2>\d{1,2}),\s*(?P<a2>\d{4})"
    r"|(?P<m>[A-Za-z]{3,9})\.?\s+(?P<d>\d{1,2}),\s*(?P<a>\d{4})"
)


def data_final(texto: str) -> date | None:
    """Última data de um intervalo como "October 7-11, 2026" ou "Sep 28 - Oct 2, 2026"."""
    t = texto_simples(texto).replace("&nbsp;", " ")
    m = _DATA.search(t)
    if m is None:
        return None
    if m.group("d2"):
        mes = m.group("m2") or m.group("m1")
        dia, ano = m.group("d2"), m.group("a2")
    else:
        mes, dia, ano = m.group("m"), m.group("d"), m.group("a")
    if mes is None or mes[:3].lower() not in MESES:
        return None
    return date(int(ano), MESES[mes[:3].lower()], int(dia))


_AMOSTRA = re.compile(r"([\d,]+)\s*\(?\s*(LV|RV|A|V)?\s*\)?", re.I)
_NUMERO = re.compile(r"(\d+(?:\.\d+)?)\s*%")


def _numero(celula: str) -> float | None:
    m = _NUMERO.search(texto_simples(conteudo(celula)))
    return float(m.group(1)) if m else None


def _cabecalhos(tabela: str) -> list[str]:
    primeira = next((ln for ln in linhas(tabela) if "Poll source" in ln), "")
    return [texto_simples(c) for c in celulas(primeira) if c.strip()]


def _partido_coluna(cabecalho: str) -> str | None:
    m = re.search(r"\((D|R|I|DFL|L|G)\)\s*$", cabecalho)
    if not m:
        return None
    return {"DFL": "D"}.get(m.group(1), m.group(1))


def tabelas_eleicao_geral(texto: str) -> list[tuple[list[str], str]]:
    """Tabelas de sondagens das secções de topo "General election" ou "Polling".

    As sondagens das primárias ficam em subsecções das secções de cada primária e por isso
    não entram. Algumas páginas têm a eleição geral num "== Polling ==" à parte.
    """
    texto = sem_comentarios(texto)
    resultado: list[tuple[list[str], str]] = []
    titulos = list(re.finditer(r"^==([^=].*?)==\s*$", texto, flags=re.M))
    for i, titulo in enumerate(titulos):
        if not re.search(r"general election|polling", titulo.group(1), flags=re.I):
            continue
        fim = titulos[i + 1].start() if i + 1 < len(titulos) else len(texto)
        seccao = texto[titulo.end() : fim]
        resultado.extend((_cabecalhos(t), t) for t in tabelas(seccao) if "Poll source" in t)
    return resultado


def ler_tabela(
    tabela: str, cabecalhos: list[str], corrida: str, ano: int, *, dem: str, rep: str
) -> list[Sondagem]:
    """Lê as linhas de uma tabela de sondagens para o par de candidatos (apelidos) dado."""
    col_dem = next((i for i, h in enumerate(cabecalhos) if dem.lower() in h.lower()), None)
    col_rep = next((i for i, h in enumerate(cabecalhos) if rep.lower() in h.lower()), None)
    if col_dem is None or col_rep is None:
        return []
    resultado: list[Sondagem] = []
    vistas: set[tuple[str, date, str]] = set()
    for cs in grelha(tabela):
        if any("Poll source" in c for c in cs) or len(cs) <= max(col_dem, col_rep):
            continue
        fim = data_final(cs[1])
        if fim is None:
            continue
        instituto_bruto = texto_simples(conteudo(cs[0]))
        d, r = _numero(cs[col_dem]), _numero(cs[col_rep])
        if d is None or r is None:
            continue
        amostra_txt = texto_simples(conteudo(cs[2])).replace("&nbsp;", " ")
        m = _AMOSTRA.search(amostra_txt)
        digitos = m.group(1).replace(",", "") if m else ""
        amostra = int(digitos) if digitos else None
        populacao = (m.group(2) or "?").lower() if m else "?"
        instituto = re.sub(r"\s*\((?:D|R|I)\)\s*$", "", instituto_bruto).strip()
        chave = (instituto, fim, populacao)
        if chave in vistas:
            # Mesma sondagem com outra pergunta (ex.: com indecisos inclinados): só a primeira.
            continue
        vistas.add(chave)
        resultado.append(
            Sondagem(
                corrida=corrida,
                ano=ano,
                instituto=instituto,
                fim=fim,
                amostra=amostra,
                populacao="lv" if populacao == "v" else populacao,
                partidaria=bool(re.search(r"\((?:D|R)\)", instituto_bruto)),
                dem=d,
                rep=r,
                candidato_d=_nome_coluna(cabecalhos[col_dem]),
                candidato_r=_nome_coluna(cabecalhos[col_rep]),
            )
        )
    return resultado


def _nome_coluna(cabecalho: str) -> str:
    nome = texto_simples(cabecalho).split("|")[-1]
    return re.sub(r"\s*\([^)]*\)\s*$", "", nome).strip()


def ler_pagina_corrida(texto: str, corrida: str, ano: int, dem: str, rep: str) -> list[Sondagem]:
    """Sondagens D vs R da corrida: a primeira tabela da eleição geral com os dois candidatos."""
    for cabecalhos, tabela in tabelas_eleicao_geral(texto):
        sondagens = ler_tabela(tabela, cabecalhos, corrida, ano, dem=dem, rep=rep)
        if sondagens:
            return sondagens
    return []


def seccao_distrito(texto: str, distrito: int) -> str | None:
    """Secção ``==District N==`` da página de um estado, com os títulos subidos um nível.

    Na página "<ano> United States House of Representatives elections in <estado>", cada
    distrito é uma secção de topo e a eleição geral fica em ``===General election===``.
    Subir os títulos um nível deixa a secção no formato das páginas de cada corrida, para
    usar o mesmo leitor (``ler_pagina_corrida``), que ignora as primárias.
    """
    texto = sem_comentarios(texto)
    inicio = re.search(rf"^==\s*District {distrito}\s*==\s*$", texto, flags=re.M)
    if inicio is None:
        return None
    seguinte = re.search(r"^==[^=].*?==\s*$", texto[inicio.end() :], flags=re.M)
    fim = inicio.end() + seguinte.start() if seguinte else len(texto)
    seccao = texto[inicio.end() : fim]
    return re.sub(r"^=(=+[^=].*?=+)=\s*$", r"\1", seccao, flags=re.M)


def hoje() -> date:
    return datetime.now().astimezone().date()
