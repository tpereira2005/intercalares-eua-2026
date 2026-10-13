"""Dados sintéticos para os testes do modelo de previsão.

Nada aqui vem de eleições reais: as corridas, os resultados e as sondagens são gerados com
uma semente fixa a partir de uma regra conhecida (margem = ambiente + PVI + incumbência +
ruído), o que permite verificar que o modelo recupera os parâmetros e é simétrico.
"""

from dataclasses import replace
from datetime import timedelta

import numpy as np
import pytest

from pipeline.modelo.fontes.corridas import Candidato, Corrida
from pipeline.modelo.fontes.sondagens import Sondagem
from pipeline.modelo.previsao import DATAS_ELEICAO, Dados, corte_final

ANOS = (2008, 2010, 2012, 2014, 2016, 2018)
ESTADOS = [
    *("AL", "AZ", "AR", "CA", "CO", "CT", "FL", "GA", "IA", "ID", "IL", "IN", "KS", "KY", "LA"),
    *("MA", "MD", "ME", "MI", "MN", "MO", "MS", "MT", "NC", "NE", "NH", "NJ", "NM", "NV", "NY"),
    *("OH", "OK", "OR", "PA", "SC", "SD", "TN", "TX", "UT", "VA", "WA", "WI", "WV"),
]
CAMARA_POR_ESTADO = 3
SENADO = ESTADOS[:30]


def apelido(i: int) -> str:
    """Apelido só com letras (o modelo compara nomes pelo último nome, sem algarismos)."""
    letras = ""
    i += 26 * 27
    while i:
        i, r = divmod(i, 26)
        letras = chr(97 + r) + letras
    return letras.capitalize()


def _corrida(
    lugar: tuple[int, str, str, str], pvi: float, margem: float, *, inc: str, k: int
) -> Corrida:
    ano, camara, estado, distrito = lugar
    nome_d, nome_r = f"Ana {apelido(2 * k)}", f"Rui {apelido(2 * k + 1)}"
    incumbentes = []
    if inc == "D":
        incumbentes.append((nome_d, "D"))
    elif inc == "R":
        incumbentes.append((nome_r, "R"))
    return Corrida(
        ano=ano,
        camara=camara,
        estado=estado,
        distrito=distrito,
        pvi=pvi,
        incumbentes=incumbentes,
        candidatos=[
            Candidato(nome_d, "D", round(50 + margem / 2, 1)),
            Candidato(nome_r, "R", round(50 - margem / 2, 1)),
        ],
    )


def gerar_dados(semente: int = 7) -> Dados:
    rng = np.random.default_rng(semente)
    nacional = {a: float(rng.normal(0, 5)) for a in ANOS}
    for a in (1998, 2000, 2002, 2004, 2006):
        nacional[a] = float(rng.normal(0, 5))
    corridas: dict[int, list[Corrida]] = {}
    sondagens: list[Sondagem] = []
    resultados: dict[tuple[int, str], float] = {}
    k = 0
    pvis_camara = rng.normal(0, 12, len(ESTADOS) * CAMARA_POR_ESTADO)
    pvis_senado = rng.normal(0, 8, len(SENADO))
    for ano in ANOS:
        lista: list[Corrida] = []
        efeito_ano = rng.normal(0, 1.5)
        for i, estado in enumerate(ESTADOS):
            for d in range(CAMARA_POR_ESTADO):
                pvi = float(pvis_camara[i * CAMARA_POR_ESTADO + d])
                inc = str(rng.choice(["D", "R", ""]))
                sinal = {"D": 1, "R": -1, "": 0}[inc]
                margem = nacional[ano] + efeito_ano + 1.8 * pvi + 6 * sinal + rng.normal(0, 7)
                lugar = (ano, "camara", estado, f"{d + 1:02d}")
                lista.append(_corrida(lugar, pvi, margem, inc=inc, k=k))
                k += 1
        erro_sondagens = rng.normal(0, 2)
        for j, estado in enumerate(SENADO):
            pvi = float(pvis_senado[j])
            inc = "D" if j % 2 == 0 else "R"
            sinal = 1 if inc == "D" else -1
            margem = nacional[ano] + 1.6 * pvi + 5 * sinal + rng.normal(0, 7)
            corrida = _corrida((ano, "senado", estado, "S"), pvi, margem, inc=inc, k=k)
            k += 1
            lista.append(corrida)
            resultados[(ano, corrida.id)] = margem
            for p in range(4):
                centro = margem + erro_sondagens + rng.normal(0, 3)
                sondagens.append(
                    Sondagem(
                        corrida=corrida.id,
                        ano=ano,
                        instituto=f"Instituto {p}",
                        fim=corte_final(ano) - timedelta(days=int(3 + 4 * p)),
                        amostra=800,
                        populacao="lv",
                        partidaria=False,
                        dem=50 + centro / 2,
                        rep=50 - centro / 2,
                        candidato_d=corrida.candidatos[0].nome,
                        candidato_r=corrida.candidatos[1].nome,
                    )
                )
        corridas[ano] = lista
    for ano, n in nacional.items():
        for p in range(5):
            centro = n + rng.normal(0, 2.5)
            sondagens.append(
                Sondagem(
                    corrida="US",
                    ano=ano,
                    instituto=f"Nacional {p}",
                    fim=DATAS_ELEICAO[ano] - timedelta(days=5 + 3 * p),
                    amostra=1500,
                    populacao="lv",
                    partidaria=False,
                    dem=45 + centro / 2,
                    rep=45 - centro / 2,
                )
            )
    return Dados(
        corridas=corridas,
        nacional=nacional,
        sondagens=sondagens,
        resultados_senado={k: v for k, v in resultados.items() if k[0] < 2018},
        composicao=dict.fromkeys(ANOS, (50, 50, "R")),
        redesenhos=dict.fromkeys(ANOS, frozenset()),
    )


def _trocar_partido(partido: str) -> str:
    return {"D": "R", "R": "D"}.get(partido, partido)


def espelhar(dados: Dados) -> Dados:
    """Os mesmos dados com os partidos trocados em todas as entradas."""
    corridas = {
        ano: [
            replace(
                c,
                pvi=None if c.pvi is None else -c.pvi,
                incumbentes=[(n, _trocar_partido(p)) for n, p in c.incumbentes],
                candidatos=[replace(x, partido=_trocar_partido(x.partido)) for x in c.candidatos],
            )
            for c in lista
        ]
        for ano, lista in dados.corridas.items()
    }
    sondagens = [
        replace(s, dem=s.rep, rep=s.dem, candidato_d=s.candidato_r, candidato_r=s.candidato_d)
        for s in dados.sondagens
    ]
    return Dados(
        corridas=corridas,
        nacional={a: -v for a, v in dados.nacional.items()},
        sondagens=sondagens,
        resultados_senado={k: -v for k, v in dados.resultados_senado.items()},
        composicao={a: (r, d, _trocar_partido(x)) for a, (d, r, x) in dados.composicao.items()},
        redesenhos=dados.redesenhos,
        independentes_d=dados.independentes_r,
        independentes_r=dados.independentes_d,
    )


@pytest.fixture(scope="session")
def dados_sinteticos() -> Dados:
    return gerar_dados()


@pytest.fixture(scope="session")
def dados_espelhados(dados_sinteticos: Dados) -> Dados:
    return espelhar(dados_sinteticos)
