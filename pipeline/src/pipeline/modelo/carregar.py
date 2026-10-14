"""Construção e leitura dos dados do modelo (referência versionada + 2026 em direto)."""

import logging
import re
from collections.abc import Iterable
from pathlib import Path

import httpx

from pipeline.modelo import referencia
from pipeline.modelo.dados import (
    REDESENHOS,
    LinhaModelo,
    linha_modelo,
    redesenhados_2026,
    voto_generico_agregadores,
    voto_nacional,
)
from pipeline.modelo.fontes import wikipedia
from pipeline.modelo.fontes.corridas import NOMES_ESTADOS, Corrida, ler_pagina
from pipeline.modelo.fontes.sondagens import (
    Sondagem,
    ler_538,
    ler_pagina_corrida,
    resultados_538,
    seccao_distrito,
)
from pipeline.modelo.previsao import Dados

registo = logging.getLogger(__name__)

ANOS_REFERENCIA = (2012, 2014, 2016, 2018, 2020, 2022, 2024)
ANO_ATUAL = 2026
CACHE = Path("data/brutos/modelo/wiki")
URL_538 = (
    "https://raw.githubusercontent.com/fivethirtyeight/data/master/pollster-ratings/raw_polls.csv"
)
COMPOSICAO_SENADO: dict[int, tuple[int, int, str]] = {
    2014: (55, 45, "D"),
    2016: (46, 54, "D"),
    2018: (49, 51, "R"),
    2020: (47, 53, "R"),
    2022: (50, 50, "D"),
    2024: (51, 49, "?"),
    2026: (47, 53, "R"),
}
"""Senado antes de cada eleição: bancada democrata (com independentes que votam com ela),
bancada republicana e partido do vice-presidente em funções no novo Congresso. Em 2024 o
desempate dependia da eleição presidencial do mesmo dia, por isso fica indeterminado."""

INDEPENDENTES_D = frozenset(
    {
        "Bernie Sanders",
        "Angus King",
        "Dan Osborn",
        "Evan McMullin",
        "Greg Orman",
        "Todd Achilles",
        "Bill Hill",
    }
)
"""Independentes que ocuparam o lado democrata (sem candidato democrata relevante)."""

INDEPENDENTES_R = frozenset({"Kevin Kiley"})
"""Independentes que ocupam o lado republicano (alinham com a bancada republicana)."""

_SUFIXOS = {"jr", "jr.", "sr", "sr.", "ii", "iii", "iv"}


def apelido(nome: str) -> str:
    partes = [p for p in nome.replace(",", " ").split() if p.lower() not in _SUFIXOS]
    return partes[-1] if partes else nome


def titulo_casa(ano: int) -> str:
    return f"{ano} United States House of Representatives elections"


def titulo_senado(ano: int) -> str:
    return f"{ano} United States Senate elections"


def titulo_corrida(corrida: Corrida) -> str:
    inverso = {v: k for k, v in NOMES_ESTADOS.items()}
    especial = "special " if corrida.distrito == "S-especial" else ""
    return f"{corrida.ano} United States Senate {especial}election in {inverso[corrida.estado]}"


def corridas_do_ano(ano: int, cliente: httpx.Client, atualizar: bool) -> list[Corrida]:
    casa = wikipedia.obter(titulo_casa(ano), CACHE, atualizar=atualizar, cliente=cliente)
    senado = wikipedia.obter(titulo_senado(ano), CACHE, atualizar=atualizar, cliente=cliente)
    return ler_pagina(casa, ano, "camara") + ler_pagina(senado, ano, "senado")


def sondagens_wikipedia(
    corridas: list[Corrida], cliente: httpx.Client, atualizar: bool
) -> list[Sondagem]:
    """Sondagens D vs R de cada corrida ao Senado, lidas da página de cada corrida."""
    resultado: list[Sondagem] = []
    for corrida in corridas:
        if corrida.camara != "senado":
            continue
        linha = linha_modelo(corrida, INDEPENDENTES_D, INDEPENDENTES_R)
        if linha is None or linha.certo is not None or not linha.lado_d or not linha.lado_r:
            continue
        try:
            texto = wikipedia.obter(
                titulo_corrida(corrida), CACHE / "senado", atualizar=atualizar, cliente=cliente
            )
        except wikipedia.PaginaInexistente:
            registo.warning("Sem página para %s %s", corrida.ano, corrida.id)
            continue
        lidas = ler_pagina_corrida(
            texto, corrida.id, corrida.ano, apelido(linha.lado_d), apelido(linha.lado_r)
        )
        registo.info("%s %s: %d sondagens", corrida.ano, corrida.id, len(lidas))
        resultado.extend(lidas)
    return resultado


def titulo_camara_estado(ano: int, estado: str, *, distrito_unico: bool = False) -> str:
    """Página com as secções de cada distrito de um estado (no singular, e sem secções, nos
    estados com um só distrito)."""
    inverso = {v: k for k, v in NOMES_ESTADOS.items()}
    eleicoes = "election" if distrito_unico else "elections"
    return f"{ano} United States House of Representatives {eleicoes} in {inverso[estado]}"


def sondagens_camara_wikipedia(
    linhas: Iterable[LinhaModelo], cliente: httpx.Client, atualizar: bool
) -> dict[str, list[Sondagem]]:
    """Sondagens D vs R dos distritos dados, lidas da página de cada estado (só para o site).

    Cada página de estado é pedida uma vez por execução, com a pausa e a cache de
    ``wikipedia.obter``. Estas sondagens não entram no modelo.
    """
    por_estado: dict[str, list[LinhaModelo]] = {}
    for linha in linhas:
        if linha.lado_d and linha.lado_r and linha.certo is None:
            por_estado.setdefault(linha.estado, []).append(linha)
    resultado: dict[str, list[Sondagem]] = {}
    for estado, distritos in sorted(por_estado.items()):
        unico = any(d.id.endswith("-00") for d in distritos)
        titulo = titulo_camara_estado(distritos[0].ano, estado, distrito_unico=unico)
        try:
            texto = wikipedia.obter(titulo, CACHE / "camara", atualizar=atualizar, cliente=cliente)
        except wikipedia.PaginaInexistente:
            registo.warning("Sem página para %s", titulo)
            continue
        for linha in distritos:
            numero = int(linha.id[3:])
            seccao = texto if numero == 0 else seccao_distrito(texto, numero)
            if seccao is None:
                continue
            lidas = ler_pagina_corrida(
                seccao, linha.id, linha.ano, apelido(linha.lado_d), apelido(linha.lado_r)
            )
            if lidas:
                registo.info("%s %s: %d sondagens", linha.ano, linha.id, len(lidas))
                resultado[linha.id] = lidas
    return resultado


def construir_referencia(pasta: Path = referencia.PASTA) -> None:
    """Lê as fontes dos anos terminados e grava as tabelas versionadas."""
    with httpx.Client(headers={"User-Agent": wikipedia.USER_AGENT}, timeout=60.0) as cliente:
        nacional: list[dict[str, object]] = []
        sondagens: list[Sondagem] = []
        resultados: dict[tuple[int, str], float] = {}
        for ano in ANOS_REFERENCIA:
            corridas = corridas_do_ano(ano, cliente, atualizar=False)
            referencia.gravar_corridas(corridas, pasta / f"corridas_{ano}.json")
            casa = wikipedia.obter(titulo_casa(ano), CACHE, cliente=cliente)
            nacional.append(
                {"ano": ano, "margem": f"{voto_nacional(casa):.2f}", "fonte": "wikipedia"}
            )
            if ano >= 2024:
                sondagens.extend(sondagens_wikipedia(corridas, cliente, atualizar=False))
                for c in corridas:
                    linha = linha_modelo(c, INDEPENDENTES_D, INDEPENDENTES_R)
                    if c.camara == "senado" and linha is not None and linha.margem is not None:
                        resultados[(ano, c.id)] = linha.margem
        bruto_538 = Path("data/brutos/modelo/538/raw_polls.csv")
        if not bruto_538.exists():
            bruto_538.parent.mkdir(parents=True, exist_ok=True)
            bruto_538.write_bytes(cliente.get(URL_538).content)
    sondagens.extend(ler_538(bruto_538))
    reais_538 = resultados_538(bruto_538)
    for (ano, corrida), margem in reais_538.items():
        if corrida == "US":
            if ano not in ANOS_REFERENCIA:
                nacional.append({"ano": ano, "margem": f"{margem:.2f}", "fonte": "538"})
        else:
            resultados.setdefault((ano, corrida), margem)
    referencia.gravar_sondagens(sondagens, pasta / "sondagens.csv")
    referencia.gravar_tabela(
        sorted(nacional, key=lambda r: int(str(r["ano"]))), pasta / "voto_nacional.csv"
    )
    referencia.gravar_tabela(
        [
            {"ano": a, "corrida": c, "margem": f"{m:.2f}"}
            for (a, c), m in sorted(resultados.items())
        ],
        pasta / "resultados_senado.csv",
    )


def carregar(
    pasta: Path = referencia.PASTA,
    atual: list[Corrida] | None = None,
    sondagens_atuais: list[Sondagem] | None = None,
    redesenho_atual: frozenset[str] = frozenset(),
) -> Dados:
    """Lê a referência versionada e junta-lhe (opcionalmente) os dados de 2026."""
    corridas = {
        int(re.findall(r"\d{4}", p.stem)[0]): referencia.ler_corridas(p)
        for p in sorted(pasta.glob("corridas_*.json"))
    }
    if atual is not None:
        corridas[ANO_ATUAL] = atual
    nacional = {
        int(r["ano"]): float(r["margem"])
        for r in referencia.ler_tabela(pasta / "voto_nacional.csv")
    }
    resultados = {
        (int(r["ano"]), r["corrida"]): float(r["margem"])
        for r in referencia.ler_tabela(pasta / "resultados_senado.csv")
    }
    sondagens = referencia.ler_sondagens(pasta / "sondagens.csv") + (sondagens_atuais or [])
    redesenhos = dict(REDESENHOS)
    redesenhos[ANO_ATUAL] = redesenho_atual
    return Dados(
        corridas=corridas,
        nacional=nacional,
        sondagens=sondagens,
        resultados_senado=resultados,
        composicao=COMPOSICAO_SENADO,
        redesenhos=redesenhos,
        independentes_d=INDEPENDENTES_D,
        independentes_r=INDEPENDENTES_R,
    )


def dados_2026(
    cliente: httpx.Client, atualizar: bool = True
) -> tuple[list[Corrida], list[Sondagem], frozenset[str], tuple[float, list[tuple[str, float]]]]:
    """Corridas, sondagens, estados redesenhados e voto genérico publicados para 2026."""
    corridas = corridas_do_ano(ANO_ATUAL, cliente, atualizar)
    casa = wikipedia.obter(titulo_casa(ANO_ATUAL), CACHE, cliente=cliente)
    sondagens = sondagens_wikipedia(corridas, cliente, atualizar)
    return corridas, sondagens, redesenhados_2026(casa), voto_generico_agregadores(casa)
