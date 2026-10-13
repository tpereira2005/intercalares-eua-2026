"""Orquestração do modelo: estimar com o passado, simular o ano pedido.

A mesma função ``prever`` serve a previsão de 2026 e os backtests (2018, 2022, 2024): só
mudam o ano e os dados disponíveis à data de corte.
"""

import math
from dataclasses import dataclass
from datetime import date, timedelta

import numpy as np

from pipeline.modelo.dados import (
    LinhaModelo,
    com_residuo_anterior,
    linha_modelo,
    normalizar_nome,
)
from pipeline.modelo.estimacao import (
    ErroSondagens,
    Fundamentos,
    erro_quadratico_medio,
    estimar_erro_sondagens,
    estimar_fundamentos,
)
from pipeline.modelo.fontes.corridas import Corrida
from pipeline.modelo.fontes.sondagens import Sondagem
from pipeline.modelo.media import Media, media
from pipeline.modelo.simulacao import (
    Ambiente,
    ComposicaoSenado,
    ResultadoCamara,
    simular_camara,
    simular_senado,
    sortear_choques,
)

DATAS_ELEICAO: dict[int, date] = {
    1998: date(1998, 11, 3), 2000: date(2000, 11, 7), 2002: date(2002, 11, 5),
    2004: date(2004, 11, 2), 2006: date(2006, 11, 7), 2008: date(2008, 11, 4),
    2010: date(2010, 11, 2), 2012: date(2012, 11, 6), 2014: date(2014, 11, 4),
    2016: date(2016, 11, 8), 2018: date(2018, 11, 6), 2020: date(2020, 11, 3),
    2022: date(2022, 11, 8), 2024: date(2024, 11, 5), 2026: date(2026, 11, 3),
}  # fmt: skip
DIAS_CORTE = 2
"""O modelo congela-se dois dias antes da eleição (1 de novembro em 2026)."""

SIMULACOES = 20_000


def corte_final(ano: int) -> date:
    return DATAS_ELEICAO[ano] - timedelta(days=DIAS_CORTE)


@dataclass(frozen=True, slots=True)
class Dados:
    """Tudo o que o modelo pode usar (o filtro por data e por ano faz-se em ``prever``)."""

    corridas: dict[int, list[Corrida]]
    """Corridas por ano (Câmara e Senado), 2012 em diante."""

    nacional: dict[int, float]
    """Voto popular nacional real na Câmara (D-R), por ano."""

    sondagens: list[Sondagem]
    """Sondagens do Senado (``XX-S``) e do voto genérico (``US``)."""

    resultados_senado: dict[tuple[int, str], float]
    """Margem real D-R de corridas ao Senado com sondagens (para estimar o erro)."""

    composicao: dict[int, tuple[int, int, str]]
    """Senado antes da eleição: (bancada D, bancada R, partido do desempate)."""

    redesenhos: dict[int, frozenset[str]]
    independentes_d: frozenset[str] = frozenset()
    independentes_r: frozenset[str] = frozenset()


@dataclass(frozen=True, slots=True)
class Previsao:
    ano: int
    corte: date
    ambiente: Ambiente
    fonte_ambiente: str
    fundamentos_camara: Fundamentos
    fundamentos_senado: Fundamentos
    erro_sondagens: ErroSondagens
    camara: ResultadoCamara
    senado: ResultadoCamara
    composicao: ComposicaoSenado
    anos_treino: tuple[int, ...]
    semente: int


def _linhas(dados: Dados, ano: int, camara: str) -> list[LinhaModelo]:
    resultado = []
    for corrida in dados.corridas.get(ano, []):
        if corrida.camara != camara:
            continue
        linha = linha_modelo(corrida, dados.independentes_d, dados.independentes_r)
        if linha is not None:
            resultado.append(linha)
    return resultado


def _com_historico(
    dados: Dados,
    anos: list[int],
    camara: str,
    fund: Fundamentos | None,
    residuos: dict[tuple[int, str], float],
) -> dict[int, list[LinhaModelo]]:
    """Linhas por ano com o resíduo do ciclo anterior (só na Câmara)."""
    por_ano = {a: _linhas(dados, a, camara) for a in anos}
    if camara != "camara" or fund is None:
        return por_ano
    for ano in anos:
        anteriores: dict[str, tuple[str, float]] = {}
        for linha in por_ano.get(ano - 2, _linhas(dados, ano - 2, camara)):
            residuo = residuos.get((ano - 2, linha.id))
            if residuo is None or linha.margem is None:
                continue
            vencedor = linha.lado_d if linha.margem > 0 else linha.lado_r
            anteriores[linha.id] = (vencedor, residuo)
        por_ano[ano] = com_residuo_anterior(
            por_ano[ano], anteriores, dados.redesenhos.get(ano, frozenset())
        )
    return por_ano


def estimar(
    dados: Dados, ano: int, camara: str
) -> tuple[Fundamentos, dict[int, list[LinhaModelo]]]:
    """Estima os fundamentos com os anos anteriores e devolve as linhas (incl. ``ano``)."""
    treino = sorted(a for a in dados.corridas if a < ano and a in dados.nacional)
    todos = [*treino, ano]
    base, residuos = estimar_fundamentos(
        [ln for a in treino for ln in _linhas(dados, a, camara)], dados.nacional
    )
    por_ano = _com_historico(dados, todos, camara, base, residuos)
    if camara != "camara":
        return base, por_ano
    fund, _ = estimar_fundamentos([ln for a in treino for ln in por_ano[a]], dados.nacional)
    return fund, por_ano


def _medias(
    dados: Dados, ano: int, corte: date, linhas: list[LinhaModelo] | None = None
) -> dict[str, Media]:
    """Média de sondagens por corrida; com ``linhas``, só perguntas com os candidatos reais."""
    candidatos = {ln.id: (ln.lado_d, ln.lado_r) for ln in linhas or []}
    por_corrida: dict[str, list[Sondagem]] = {}
    for s in dados.sondagens:
        if s.ano != ano:
            continue
        if s.corrida in candidatos and not _mesmos_candidatos(s, *candidatos[s.corrida]):
            continue
        por_corrida.setdefault(s.corrida, []).append(s)
    medias = {}
    for corrida, lista in por_corrida.items():
        m = media(lista, corte)
        if m is not None:
            medias[corrida] = m
    return medias


def _mesmos_candidatos(sondagem: Sondagem, lado_d: str, lado_r: str) -> bool:
    if not sondagem.candidato_d or not sondagem.candidato_r:
        return True
    return normalizar_nome(sondagem.candidato_d) == normalizar_nome(lado_d) and (
        normalizar_nome(sondagem.candidato_r) == normalizar_nome(lado_r)
    )


def erro_nacional(dados: Dados, ano: int) -> tuple[float, dict[int, float]]:
    """Raiz do erro quadrático médio do voto genérico nos anos anteriores, e erros por ano."""
    erros: dict[int, float] = {}
    for a in sorted(DATAS_ELEICAO):
        if a >= ano or a not in dados.nacional:
            continue
        m = _medias(dados, a, corte_final(a)).get("US")
        if m is not None:
            erros[a] = m.margem - dados.nacional[a]
    if len(erros) < 5:
        raise ValueError("Anos insuficientes para estimar o erro do voto genérico")
    return erro_quadratico_medio(list(erros.values())), erros


def estimar_erro(dados: Dados, ano: int, erros_gb: dict[int, float]) -> ErroSondagens:
    erros: list[tuple[int, int, float]] = []
    for a in sorted(DATAS_ELEICAO):
        if a >= ano:
            continue
        for corrida, m in _medias(dados, a, corte_final(a)).items():
            real = dados.resultados_senado.get((a, corrida))
            if corrida != "US" and real is not None:
                erros.append((a, m.institutos, m.margem - real))
    return estimar_erro_sondagens(erros, erros_gb)


def ambiente_senado(
    linhas: list[LinhaModelo], fund: Fundamentos, erro: ErroSondagens, medias: dict[str, Media]
) -> float | None:
    """Ambiente nacional implícito nas sondagens do Senado (quando não há voto genérico).

    Cada corrida com sondagens dá uma leitura: média - (intercepto + PVI + incumbência). A
    estimativa é a média ponderada pela precisão de cada leitura.
    """
    soma = pesos = 0.0
    for linha in linhas:
        m = medias.get(linha.id)
        if (
            m is None
            or linha.certo is not None
            or linha.lado_d_independente
            or linha.lado_r_independente
        ):
            continue
        leitura = m.margem - fund.esperado(linha, 0.0)
        peso = 1.0 / (fund.sd_corrida**2 + erro.variancia(m.institutos))
        soma += peso * leitura
        pesos += peso
    return soma / pesos if pesos else None


def composicao_senado(dados: Dados, ano: int) -> ComposicaoSenado:
    bancada_d, bancada_r, desempate = dados.composicao[ano]
    em_jogo_d = em_jogo_r = 0
    for corrida in dados.corridas[ano]:
        if corrida.camara != "senado" or not corrida.incumbentes:
            continue
        partido = corrida.incumbentes[0][1]
        if partido == "R":
            em_jogo_r += 1
        else:
            em_jogo_d += 1
    return ComposicaoSenado(
        continuam_d=bancada_d - em_jogo_d, continuam_r=bancada_r - em_jogo_r, desempate=desempate
    )


def prever(
    dados: Dados,
    ano: int,
    corte: date | None = None,
    ambiente_publicado: tuple[float, str] | None = None,
    semente: int = 2026,
) -> Previsao:
    """Previsão do ano ``ano`` com os dados disponíveis em ``corte`` (exclusive)."""
    corte = corte or corte_final(ano)
    fund_c, linhas_c = estimar(dados, ano, "camara")
    fund_s, linhas_s = estimar(dados, ano, "senado")
    sd_nacional, erros_gb = erro_nacional(dados, ano)
    erro = estimar_erro(dados, ano, erros_gb)
    medias = _medias(dados, ano, corte, linhas_s[ano])
    if "US" not in medias:
        medias.update({k: v for k, v in _medias(dados, ano, corte).items() if k == "US"})

    if ambiente_publicado is not None:
        margem, fonte = ambiente_publicado
        sd = sd_nacional
    elif "US" in medias:
        margem, fonte, sd = medias["US"].margem, "media_sondagens_voto_generico", sd_nacional
    else:
        implicito = ambiente_senado(linhas_s[ano], fund_s, erro, medias)
        if implicito is None:
            raise ValueError(f"Sem dados para estimar o ambiente nacional de {ano}")
        # Sem voto genérico, a leitura pelo Senado é menos precisa: soma-se o erro comum
        # das sondagens do Senado ao erro do voto genérico.
        margem, fonte = implicito, "sondagens_senado"
        sd = math.sqrt(sd_nacional**2 + erro.sd_ano**2)
    ambiente = Ambiente(margem=margem, sd=sd)

    rng = np.random.default_rng(semente)
    choques = sortear_choques(rng, SIMULACOES, ambiente, fund_c.sd_regiao)
    camara = simular_camara(linhas_c[ano], fund_c, ambiente, choques, rng)
    composicao = composicao_senado(dados, ano)
    senado = simular_senado(
        linhas_s[ano],
        fund_s,
        erro,
        medias,
        ambiente,
        composicao=composicao,
        choques=choques,
        rng=rng,
    )
    return Previsao(
        ano=ano,
        corte=corte,
        ambiente=ambiente,
        fonte_ambiente=fonte,
        fundamentos_camara=fund_c,
        fundamentos_senado=fund_s,
        erro_sondagens=erro,
        camara=camara,
        senado=senado,
        composicao=composicao,
        anos_treino=tuple(sorted(a for a in linhas_c if a < ano)),
        semente=semente,
    )
