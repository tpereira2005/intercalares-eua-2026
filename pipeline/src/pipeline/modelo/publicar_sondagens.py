"""Monta o ficheiro das sondagens para o site (contrato ``SondagensCongresso``).

Usa as mesmas sondagens e o mesmo método de média da previsão (``media.pesos`` e
``previsao.sondagens_por_corrida``), para que a página mostre exatamente o que entra no
modelo. A série do voto genérico acumula-se de execução em execução: a Wikipédia de 2026
só publica os valores atuais dos agregadores, não as sondagens individuais.
"""

from collections.abc import Iterable, Sequence
from datetime import date, datetime, timedelta

from contratos.base import Fonte, Metadados
from contratos.sondagens import (
    MetodoMedia,
    PontoMedia,
    PontoVotoGenerico,
    SondagemPublicada,
    SondagensCongresso,
    SondagensCorrida,
    ValorAgregador,
)
from pipeline.modelo import media as metodo
from pipeline.modelo.dados import LinhaModelo
from pipeline.modelo.fontes.sondagens import Sondagem
from pipeline.modelo.previsao import Dados, sondagens_por_corrida

POPULACOES = frozenset({"lv", "rv", "a", "?"})
DIAS_SERIE = 150
"""A série diária da média começa, no máximo, este número de dias antes do corte."""


def _publicada(s: Sondagem, peso: float) -> SondagemPublicada:
    return SondagemPublicada(
        instituto=s.instituto,
        fim=s.fim,
        amostra=s.amostra if s.amostra and s.amostra > 0 else None,
        populacao=s.populacao if s.populacao in POPULACOES else "?",
        partidaria=s.partidaria,
        percentagem_d=s.dem,
        percentagem_r=s.rep,
        margem=s.margem,
        peso=peso,
    )


def _ponto(lista: list[Sondagem], dia: date) -> PontoMedia | None:
    m = metodo.media(lista, dia)
    if m is None:
        return None
    return PontoMedia(data=dia, margem=m.margem, institutos=m.institutos, sondagens=m.sondagens)


def corrida(linha: LinhaModelo, lista: list[Sondagem], corte: date) -> SondagensCorrida:
    """Sondagens, média atual e série diária de uma corrida."""
    pesadas = metodo.pesos(lista, corte)
    total = sum(p for _, p in pesadas)
    peso_de = {id(s): p / total for s, p in pesadas} if total > 0 else {}
    serie: list[PontoMedia] = []
    if lista:
        dia = max(min(s.fim for s in lista) + timedelta(days=1), corte - timedelta(DIAS_SERIE))
        while dia <= corte:
            ponto = _ponto(lista, dia)
            if ponto is not None:
                serie.append(ponto)
            dia += timedelta(days=1)
    ordenadas = sorted(lista, key=lambda s: (s.fim, s.instituto), reverse=True)
    return SondagensCorrida(
        id=linha.id,
        camara="camara" if linha.camara == "camara" else "senado",
        estado=linha.estado,
        candidato_d=linha.lado_d or None,
        candidato_r=linha.lado_r or None,
        media=_ponto(lista, corte),
        serie=tuple(serie),
        sondagens=tuple(_publicada(s, peso_de.get(id(s), 0.0)) for s in ordenadas),
    )


def voto_generico(
    anterior: Iterable[PontoVotoGenerico], hoje: date, agregadores: Sequence[tuple[str, float]]
) -> tuple[PontoVotoGenerico, ...]:
    """Acrescenta os valores de hoje à série (um dia repetido substitui o anterior)."""
    pontos = {p.data: p for p in anterior if p.data <= hoje}
    if agregadores:
        valores = tuple(ValorAgregador(nome=n, margem=m) for n, m in agregadores)
        pontos[hoje] = PontoVotoGenerico(
            data=hoje,
            margem=sum(m for _, m in agregadores) / len(agregadores),
            agregadores=valores,
        )
    return tuple(pontos[d] for d in sorted(pontos))


def montar(
    dados: Dados,
    ano: int,
    corte: date,
    linhas: Sequence[LinhaModelo],
    agregadores: Sequence[tuple[str, float]],
    *,
    anterior: SondagensCongresso | None,
    fontes: Iterable[Fonte],
    gerado_em: datetime,
) -> SondagensCongresso:
    """Ficheiro das sondagens; ``linhas`` são as corridas disputadas com o lado de cada um."""
    por_corrida = sondagens_por_corrida(dados, ano, list(linhas))
    corridas = tuple(
        corrida(ln, por_corrida[ln.id], corte)
        for ln in sorted(linhas, key=lambda ln: ln.id)
        if por_corrida.get(ln.id)
    )
    return SondagensCongresso(
        metadados=Metadados(gerado_em=gerado_em, fontes=tuple(fontes)),
        ano=ano,
        corte=corte,
        metodo=MetodoMedia(
            meia_vida_dias=metodo.MEIA_VIDA_DIAS,
            janela_dias=metodo.JANELA_DIAS,
            amostra_referencia=metodo.AMOSTRA_REFERENCIA,
            amostra_maxima=metodo.AMOSTRA_MAXIMA,
            peso_partidaria=metodo.PESO_PARTIDARIA,
        ),
        voto_generico=voto_generico(anterior.voto_generico if anterior else (), corte, agregadores),
        corridas=corridas,
    )
