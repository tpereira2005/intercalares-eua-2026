"""Média ponderada de sondagens, igual para todas as corridas e para o voto genérico.

Pesos (todos documentados em ``docs/metodologia/previsao.md``):

- recência: metade do peso a cada ``MEIA_VIDA_DIAS``;
- amostra: raiz de ``n/600``, limitada a ``n = 2000`` para que nenhuma sondagem domine;
- população: eleitores prováveis 1, registados 0,8, adultos 0,6, desconhecida 0,9;
- sondagens de campanhas ou partidos (de qualquer lado): metade do peso;
- cada instituto conta uma vez: o peso de cada sondagem divide-se pelo número de sondagens
  do mesmo instituto na janela.

A regra é simétrica: nada depende do partido que a sondagem favorece.
"""

from collections import Counter
from dataclasses import dataclass
from datetime import date, timedelta

from pipeline.modelo.fontes.sondagens import Sondagem

MEIA_VIDA_DIAS = 14.0
JANELA_DIAS = 60
PESO_POPULACAO = {"lv": 1.0, "rv": 0.8, "a": 0.6, "?": 0.9}
PESO_PARTIDARIA = 0.5
AMOSTRA_REFERENCIA = 600
AMOSTRA_MAXIMA = 2000
PREFERENCIA_POPULACAO = {"lv": 0, "?": 1, "rv": 2, "a": 3}


@dataclass(frozen=True, slots=True)
class Media:
    margem: float
    """Margem média D-R em pontos."""

    institutos: int
    """Número de institutos distintos na média."""

    sondagens: int


def media(
    sondagens: list[Sondagem], corte: date, meia_vida: float = MEIA_VIDA_DIAS
) -> Media | None:
    """Média das sondagens terminadas antes de ``corte`` (exclusive) e dentro da janela."""
    inicio = corte - timedelta(days=JANELA_DIAS)
    validas = [s for s in sondagens if inicio <= s.fim < corte]
    # Da mesma sondagem (instituto e data) fica só a população preferida (LV > RV > A).
    melhores: dict[tuple[str, date], Sondagem] = {}
    for s in validas:
        chave = (s.instituto, s.fim)
        atual = melhores.get(chave)
        if atual is None or PREFERENCIA_POPULACAO.get(s.populacao, 1) < PREFERENCIA_POPULACAO.get(
            atual.populacao, 1
        ):
            melhores[chave] = s
    escolhidas = list(melhores.values())
    if not escolhidas:
        return None
    por_instituto = Counter(s.instituto for s in escolhidas)
    soma = 0.0
    pesos = 0.0
    for s in escolhidas:
        idade = (corte - s.fim).days
        amostra = min(s.amostra or AMOSTRA_REFERENCIA, AMOSTRA_MAXIMA)
        peso = (
            0.5 ** (idade / meia_vida)
            * (amostra / AMOSTRA_REFERENCIA) ** 0.5
            * PESO_POPULACAO.get(s.populacao, 0.9)
            * (PESO_PARTIDARIA if s.partidaria else 1.0)
            / por_instituto[s.instituto]
        )
        soma += peso * s.margem
        pesos += peso
    return Media(margem=soma / pesos, institutos=len(por_instituto), sondagens=len(escolhidas))
