"""Preparação das corridas para o modelo: incumbência, margens, redistribuição e regiões.

Converte as ``Corrida`` lidas da Wikipedia em ``LinhaModelo``, a unidade com que a
estimação e a simulação trabalham. As margens são sempre D-R em pontos percentuais do
total de votos; o PVI entra em pontos de margem (o dobro do PVI publicado, que é em quota
bipartidária).
"""

import re
import unicodedata
from dataclasses import dataclass, replace

from pipeline.modelo.fontes.corridas import Candidato, Corrida
from pipeline.modelo.fontes.wikitexto import (
    celulas,
    linhas,
    sem_comentarios,
    texto_simples,
)

REGIOES: dict[str, str] = {
    **dict.fromkeys(["CT", "ME", "MA", "NH", "RI", "VT", "NJ", "NY", "PA"], "nordeste"),
    **dict.fromkeys(
        ["IL", "IN", "MI", "OH", "WI", "IA", "KS", "MN", "MO", "NE", "ND", "SD"], "centro_oeste"
    ),
    **dict.fromkeys(
        ["DE", "FL", "GA", "MD", "NC", "SC", "VA", "WV", "AL", "KY", "MS", "TN", "AR", "LA",
         "OK", "TX", "DC"],
        "sul",
    ),
    **dict.fromkeys(
        ["AZ", "CO", "ID", "MT", "NV", "NM", "UT", "WY", "AK", "CA", "HI", "OR", "WA"], "oeste"
    ),
}  # fmt: skip
"""Regiões do Census Bureau, usadas para o erro regional correlacionado."""

TODOS = frozenset(REGIOES)
REDESENHOS: dict[int, frozenset[str]] = {
    2012: TODOS,
    2014: frozenset(),
    2016: frozenset({"FL", "VA", "NC"}),
    2018: frozenset({"PA"}),
    2020: frozenset({"NC"}),
    2022: TODOS,
    2024: frozenset({"AL", "GA", "LA", "NC", "NY"}),
}
"""Estados com mapa da Câmara novo em cada ano (2026 lê-se da página da Wikipedia)."""


@dataclass(frozen=True, slots=True)
class LinhaModelo:
    ano: int
    camara: str
    id: str
    estado: str
    regiao: str
    pvi: float
    """Inclinação partidária em pontos de margem (2 x Cook PVI), positiva para D."""

    incumbente: int
    """+1 incumbente democrata recandidato, -1 republicano, 0 lugar aberto."""

    margem: float | None
    """Margem real D-R (só depois da eleição)."""

    certo: str | None
    """Vencedor garantido quando não há disputa entre os dois lados (``D``, ``R``, ``I``)."""

    lado_d: str
    """Nome do candidato do lado democrata (ou independente que ocupa esse lado)."""

    lado_r: str
    lado_d_independente: bool
    """O lado democrata é um independente (ex.: Dan Osborn no Nebrasca)."""

    lado_r_independente: bool = False
    """O lado republicano é um independente (ex.: Kevin Kiley na Califórnia em 2026)."""

    vencedor: str | None = None
    """Lado vencedor real (``D``, ``R`` ou ``O``), também quando a margem não é usável."""

    residuo_anterior: float | None = None
    """Desvio do mesmo incumbente face ao modelo no ciclo anterior (mesmo mapa)."""


def _primeira_volta(candidatos: list[Candidato]) -> list[Candidato]:
    vistos: set[str] = set()
    for i, c in enumerate(candidatos):
        if c.nome in vistos:
            return candidatos[:i]
        vistos.add(c.nome)
    return candidatos


def _vencedor(
    candidatos: list[Candidato], lado_d: Candidato | None, lado_r: Candidato | None
) -> str | None:
    finais: dict[str, Candidato] = {c.nome: c for c in candidatos}
    com_resultado = [c for c in finais.values() if c.percentagem is not None]
    if not com_resultado:
        return None
    ordenados = sorted(com_resultado, key=lambda c: -(c.percentagem or 0.0))
    if len(ordenados) > 1 and ordenados[0].percentagem == ordenados[1].percentagem:
        return None
    primeiro = ordenados[0]
    if lado_d is not None and primeiro.nome == lado_d.nome:
        return "D"
    if lado_r is not None and primeiro.nome == lado_r.nome:
        return "R"
    return {"D": "D", "R": "R"}.get(primeiro.partido, "O")


def _lados(
    cands: list[Candidato], independentes_d: frozenset[str], independentes_r: frozenset[str]
) -> tuple[Candidato | None, bool, Candidato | None, bool]:
    """Candidato principal de cada lado e se é um independente (regra igual nos dois lados)."""
    dems = [c for c in cands if c.partido == "D"]
    reps = [c for c in cands if c.partido == "R"]
    outros = sorted((c for c in cands if c.partido == "O"), key=lambda c: -(c.percentagem or 0.0))
    principal_d = max(dems, key=lambda c: c.percentagem or 0.0) if dems else None
    principal_r = max(reps, key=lambda c: c.percentagem or 0.0) if reps else None
    # Um independente ocupa o lado democrata quando não há Democrata (ou é um dos conhecidos).
    lado_d_indep = False
    indep_d = next((c for c in outros if c.nome in independentes_d), None)
    if indep_d is None and principal_d is None and principal_r is not None and outros:
        indep_d = outros[0]
    if indep_d is not None and (principal_d is None or indep_d.nome in independentes_d):
        principal_d, lado_d_indep = indep_d, True
    # Regra espelhada para o lado republicano.
    lado_r_indep = False
    restantes = [c for c in outros if c is not indep_d]
    indep_r = next((c for c in restantes if c.nome in independentes_r), None)
    if indep_r is None and principal_r is None and principal_d is not None and restantes:
        indep_r = restantes[0]
    if indep_r is not None and (principal_r is None or indep_r.nome in independentes_r):
        principal_r, lado_r_indep = indep_r, True
    return principal_d, lado_d_indep, principal_r, lado_r_indep


def _disputa_entre_lados(candidatos: list[Candidato]) -> bool:
    """A margem D-R só mede a disputa entre partidos quando os resultados são coerentes.

    Excluímos (de forma simétrica) resultados que somam mais de 100% (várias voltas na
    mesma lista, como no voto preferencial do Alasca) e corridas em que dois candidatos
    do mesmo partido têm ambos 20% ou mais (disputas internas, como Murkowski contra
    Tshibaka em 2022 ou duelos entre dois Democratas na Califórnia).
    """
    percentagens = [c.percentagem for c in candidatos if c.percentagem is not None]
    if sum(percentagens) > 101.0:
        return False
    for partido in ("D", "R"):
        fortes = [c for c in candidatos if c.partido == partido and (c.percentagem or 0.0) >= 20.0]
        if len(fortes) >= 2:
            return False
    return True


def normalizar_nome(nome: str) -> str:
    sem_acentos = unicodedata.normalize("NFKD", nome).encode("ascii", "ignore").decode()
    limpo = re.sub(r"\b(jr|sr|ii|iii|iv)\b\.?", "", sem_acentos.lower())
    return re.sub(r"[^a-z ]", " ", limpo).split()[-1] if limpo.strip() else ""


def _mesmo(nome_a: str, nome_b: str) -> bool:
    return bool(nome_a) and normalizar_nome(nome_a) == normalizar_nome(nome_b)


def _soma(candidatos: list[Candidato], partido: str) -> float | None:
    valores = [c.percentagem for c in candidatos if c.partido == partido]
    if not valores or any(v is None for v in valores):
        return None
    return sum(v for v in valores if v is not None)


def linha_modelo(
    corrida: Corrida,
    independentes_d: frozenset[str] = frozenset(),
    independentes_r: frozenset[str] = frozenset(),
) -> LinhaModelo | None:
    """Converte uma corrida; devolve ``None`` se faltar o PVI (não há base para prever).

    A regra dos independentes é simétrica: um independente conhecido de cada lado (ou o
    principal independente quando falta o candidato de um dos partidos e o outro concorre)
    ocupa esse lado. Sem candidato de um dos lados, a corrida fica decidida.
    """
    if corrida.pvi is None:
        return None
    # No voto preferencial (Maine, Alasca) a lista traz a primeira e a última volta: a
    # margem usa a primeira (comparável às outras corridas) e o vencedor a última.
    cands = _primeira_volta(corrida.candidatos)
    principal_d, lado_d_indep, principal_r, lado_r_indep = _lados(
        cands, independentes_d, independentes_r
    )
    certo: str | None = None
    margem: float | None = None
    if principal_d is None and principal_r is None:
        certo = "I"
    elif principal_d is None:
        certo = "I" if lado_r_indep else "R"
    elif principal_r is None:
        certo = "I" if lado_d_indep else "D"
    else:
        d = principal_d.percentagem if lado_d_indep else _soma(cands, "D")
        r = principal_r.percentagem if lado_r_indep else _soma(cands, "R")
        if d is not None and r is not None and _disputa_entre_lados(cands):
            margem = d - r
    incumbente = 0
    for nome, partido in corrida.incumbentes:
        if not any(_mesmo(nome, c.nome) for c in cands):
            continue
        if partido in {"D", "R"}:
            incumbente = 1 if partido == "D" else -1
            break
        # Independente incumbente: conta para o lado que ocupa.
        if lado_d_indep and principal_d is not None and _mesmo(nome, principal_d.nome):
            incumbente = 1
            break
        if lado_r_indep and principal_r is not None and _mesmo(nome, principal_r.nome):
            incumbente = -1
            break
    return LinhaModelo(
        ano=corrida.ano,
        camara=corrida.camara,
        id=corrida.id,
        estado=corrida.estado,
        regiao=REGIOES[corrida.estado],
        pvi=2.0 * corrida.pvi,
        incumbente=incumbente,
        margem=margem,
        certo=certo,
        lado_d=principal_d.nome if principal_d else "",
        lado_r=principal_r.nome if principal_r else "",
        lado_d_independente=lado_d_indep,
        lado_r_independente=lado_r_indep,
        vencedor=certo or _vencedor(corrida.candidatos, principal_d, principal_r),
    )


def com_residuo_anterior(
    linhas_ano: list[LinhaModelo],
    anteriores: dict[str, tuple[str, float]],
    redesenhados: frozenset[str],
) -> list[LinhaModelo]:
    """Acrescenta o resíduo do ciclo anterior quando o vencedor de então se recandidata.

    ``anteriores`` mapeia o id da corrida para (nome do vencedor, resíduo do modelo).
    Estados com mapa novo não herdam resíduo: o distrito já não é o mesmo.
    """
    resultado: list[LinhaModelo] = []
    for linha in linhas_ano:
        anterior = anteriores.get(linha.id)
        herda = (
            anterior is not None
            and linha.estado not in redesenhados
            and linha.incumbente != 0
            and (_mesmo(anterior[0], linha.lado_d) or _mesmo(anterior[0], linha.lado_r))
        )
        resultado.append(
            replace(linha, residuo_anterior=anterior[1] if herda and anterior else None)
        )
    return resultado


# --- Leituras auxiliares das páginas anuais ---------------------------------------------


def voto_nacional(texto: str) -> float:
    """Margem D-R do voto popular nacional na Câmara, a partir da caixa de informação."""
    campos = dict(
        re.findall(r"^\s*\|\s*(party\d|percentage\d)\s*=\s*(.+)$", texto, flags=re.MULTILINE)
    )
    percentagens: dict[str, float] = {}
    for i in ("1", "2", "3"):
        partido = campos.get(f"party{i}", "")
        perc = re.search(r"([\d.]+)\s*%", texto_simples(campos.get(f"percentage{i}", "")))
        if perc and "Democratic" in partido:
            percentagens["D"] = float(perc.group(1))
        elif perc and "Republican" in partido:
            percentagens["R"] = float(perc.group(1))
    return percentagens["D"] - percentagens["R"]


def redesenhados_2026(texto: str) -> frozenset[str]:
    """Estados com mapa novo em 2026, lidos do quadro "Summary of mid-decade changes"."""
    from pipeline.modelo.fontes.corridas import NOMES_ESTADOS  # noqa: PLC0415

    texto = sem_comentarios(texto)
    inicio = texto.find("Summary of mid-decade changes")
    if inicio < 0:
        return frozenset()
    fim = texto.find("\n|}", inicio)
    estados: set[str] = set()
    for linha in linhas(texto[inicio:fim]):
        cs = celulas(linha)
        if len(cs) < 2:
            continue
        nome = texto_simples(cs[0])
        if nome in NOMES_ESTADOS and "new districts enacted" in cs[1].lower():
            estados.add(NOMES_ESTADOS[nome])
    return frozenset(estados)


def voto_generico_agregadores(texto: str) -> tuple[float, list[tuple[str, float]]]:
    """Média dos agregadores do voto genérico (quadro da página anual da Câmara).

    Devolve a média simples das margens publicadas e a lista (agregador, margem D-R).
    """
    texto = sem_comentarios(texto)
    inicio = texto.find('section begin="GenericBallotAgg"')
    fim = texto.find('section end="GenericBallotAgg"')
    if inicio < 0 or fim < 0:
        raise ValueError("Quadro de agregadores do voto genérico não encontrado")
    valores: list[tuple[str, float]] = []
    for linha in linhas(texto[inicio:fim]):
        cs = celulas(linha)
        if len(cs) < 5 or "Average" in linha:
            continue
        nome = texto_simples(cs[0])
        margem = texto_simples(cs[-1])
        m = re.search(r"(Democrats|Republicans)\s*\+\s*([\d.]+)", margem)
        if m:
            valor = float(m.group(2))
            valores.append((nome, valor if m.group(1) == "Democrats" else -valor))
        elif "Tie" in margem or "EVEN" in margem.upper():
            valores.append((nome, 0.0))
    if not valores:
        raise ValueError("Sem valores no quadro de agregadores")
    return sum(v for _, v in valores) / len(valores), valores
