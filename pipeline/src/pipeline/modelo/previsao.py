"""Orquestração do modelo: estimar com o passado, simular o ano pedido.

A mesma função ``prever`` serve a previsão de 2026 e os backtests (2018, 2022, 2024): só
mudam o ano e os dados disponíveis à data de corte.
"""

import math
from dataclasses import dataclass, replace
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
from pipeline.modelo.media import MEIA_VIDA_DIAS, Media, media
from pipeline.modelo.simulacao import (
    GRAUS_LIBERDADE,
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
class Ajustes:
    """Variações das escolhas do modelo, só para a análise de sensibilidade.

    Os valores por omissão são o modelo publicado. Cada ajuste é simétrico entre partidos
    (``desvio_ambiente`` testa-se sempre com os dois sinais).
    """

    desvio_ambiente: float = 0.0
    """Pontos somados ao ambiente nacional estimado (D-R)."""

    fator_sd_nacional: float = 1.0
    """Multiplica o desvio-padrão do erro do ambiente nacional."""

    fator_sd_corrida: float = 1.0
    """Multiplica o erro próprio de cada corrida nos fundamentos (Câmara e Senado)."""

    fator_erro_sondagens: float = 1.0
    """Multiplica o erro das médias de sondagens do Senado (próprio e comum ao ano)."""

    graus_liberdade: int = GRAUS_LIBERDADE
    """Graus de liberdade da t de Student do erro nacional (caudas mais ou menos pesadas)."""

    meia_vida_dias: float = MEIA_VIDA_DIAS
    """Meia-vida do peso de uma sondagem na média."""

    sem_sondagens_senado: bool = False
    """Ignora as sondagens de cada corrida ao Senado (fica só com os fundamentos)."""

    vies_generico: bool = True
    """Desconta ao voto genérico o erro médio das médias dos anos anteriores
    (``vies_voto_generico``). Adotado a 15 de outubro de 2026: ver a secção 3 da
    metodologia."""

    incumbentes_sondagens: bool = False
    """Corrige a média de sondagens de cada incumbente do Senado pelo desvio médio dos
    incumbentes face às sondagens nos anos anteriores, igual para os dois partidos
    (``desvio_incumbentes``). Testado e não adotado: ver a secção 8 da metodologia."""


AJUSTES_PUBLICADOS = Ajustes()


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
    correcao_vies: float = 0.0
    """Pontos descontados à média do voto genérico pelo viés histórico (D-R)."""


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


def sondagens_por_corrida(
    dados: Dados, ano: int, linhas: list[LinhaModelo] | None = None
) -> dict[str, list[Sondagem]]:
    """Sondagens de cada corrida; com ``linhas``, só perguntas com os candidatos reais."""
    candidatos = {ln.id: (ln.lado_d, ln.lado_r) for ln in linhas or []}
    por_corrida: dict[str, list[Sondagem]] = {}
    for s in dados.sondagens:
        if s.ano != ano:
            continue
        if s.corrida in candidatos and not _mesmos_candidatos(s, *candidatos[s.corrida]):
            continue
        por_corrida.setdefault(s.corrida, []).append(s)
    return por_corrida


def _medias(
    dados: Dados,
    ano: int,
    corte: date,
    linhas: list[LinhaModelo] | None = None,
    meia_vida: float = MEIA_VIDA_DIAS,
) -> dict[str, Media]:
    """Média de sondagens por corrida; com ``linhas``, só perguntas com os candidatos reais."""
    medias = {}
    for corrida, lista in sondagens_por_corrida(dados, ano, linhas).items():
        m = media(lista, corte, meia_vida)
        if m is not None:
            medias[corrida] = m
    return medias


def _mesmos_candidatos(sondagem: Sondagem, lado_d: str, lado_r: str) -> bool:
    if not sondagem.candidato_d or not sondagem.candidato_r:
        return True
    return normalizar_nome(sondagem.candidato_d) == normalizar_nome(lado_d) and (
        normalizar_nome(sondagem.candidato_r) == normalizar_nome(lado_r)
    )


def erro_nacional(
    dados: Dados, ano: int, meia_vida: float = MEIA_VIDA_DIAS, dias_antes: int = DIAS_CORTE
) -> tuple[float, dict[int, float]]:
    """Raiz do erro quadrático médio do voto genérico nos anos anteriores, e erros por ano.

    Cada ano mede-se à mesma distância da eleição (``dias_antes``) que o corte: longe da
    eleição, a média ainda pode mexer, e o erro é maior.
    """
    erros: dict[int, float] = {}
    for a in sorted(DATAS_ELEICAO):
        if a >= ano or a not in dados.nacional:
            continue
        corte = DATAS_ELEICAO[a] - timedelta(days=max(dias_antes, DIAS_CORTE))
        m = _medias(dados, a, corte, meia_vida=meia_vida).get("US")
        if m is not None:
            erros[a] = m.margem - dados.nacional[a]
    if len(erros) < 5:
        raise ValueError("Anos insuficientes para estimar o erro do voto genérico")
    return erro_quadratico_medio(list(erros.values())), erros


ENCOLHIMENTO_VIES = 2.0
"""Anos fictícios sem erro somados aos reais: encolhem para zero a média histórica."""


def vies_voto_generico(erros: dict[int, float], encolhimento: float = ENCOLHIMENTO_VIES) -> float:
    """Erro médio (média de sondagens menos resultado) do voto genérico nos anos dados.

    Positivo quando as sondagens sobrestimaram os democratas. A média encolhe para zero
    como se houvesse ``encolhimento`` anos a mais sem erro. A regra não depende do sentido:
    com os partidos trocados, o erro e a correção trocam de sinal.
    """
    if not erros:
        return 0.0
    return sum(erros.values()) / (len(erros) + encolhimento)


def estimar_erro(
    dados: Dados, ano: int, erros_gb: dict[int, float], meia_vida: float = MEIA_VIDA_DIAS
) -> ErroSondagens:
    erros: list[tuple[int, int, float]] = []
    for a in sorted(DATAS_ELEICAO):
        if a >= ano:
            continue
        for corrida, m in _medias(dados, a, corte_final(a), meia_vida=meia_vida).items():
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


def desvio_incumbentes(dados: Dados, ano: int, meia_vida: float = MEIA_VIDA_DIAS) -> float:
    """Quanto as médias de sondagens do Senado sobrestimaram o incumbente recandidato.

    Média, nos anos anteriores a ``ano``, de ``s x (média - resultado - erro médio do
    ano)``, em que ``s`` é +1 para um incumbente do lado democrata e -1 do lado
    republicano. Negativo quando as sondagens subestimaram os incumbentes. O sinal do
    incumbente torna a regra simétrica: não há constante por partido.
    """
    valores: list[float] = []
    for a in sorted(dados.corridas):
        if a >= ano:
            continue
        linhas = _linhas(dados, a, "senado")
        medias = _medias(dados, a, corte_final(a), linhas, meia_vida)
        erros: list[tuple[int, float]] = []
        for ln in linhas:
            m = medias.get(ln.id)
            real = dados.resultados_senado.get((a, ln.id))
            if m is None or real is None or ln.certo is not None:
                continue
            if ln.lado_d_independente or ln.lado_r_independente:
                continue
            erros.append((ln.incumbente, m.margem - real))
        if not erros:
            continue
        centro = sum(e for _, e in erros) / len(erros)
        valores.extend(s * (e - centro) for s, e in erros if s != 0)
    if not valores:
        raise ValueError("Sem incumbentes com sondagens nos anos anteriores")
    return sum(valores) / len(valores)


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
    *,
    ajustes: Ajustes = AJUSTES_PUBLICADOS,
) -> Previsao:
    """Previsão do ano ``ano`` com os dados disponíveis em ``corte`` (exclusive).

    ``ajustes`` só serve a análise de sensibilidade; por omissão é o modelo publicado.
    """
    corte = corte or corte_final(ano)
    aj = ajustes
    fund_c, linhas_c = estimar(dados, ano, "camara")
    fund_s, linhas_s = estimar(dados, ano, "senado")
    _, erros_gb = erro_nacional(dados, ano, aj.meia_vida_dias)
    erro = estimar_erro(dados, ano, erros_gb, aj.meia_vida_dias)
    try:
        sd_nacional, erros_dia = erro_nacional(
            dados, ano, aj.meia_vida_dias, (DATAS_ELEICAO[ano] - corte).days
        )
    except ValueError:
        # Longe demais da eleição para haver médias suficientes: fica o erro final.
        sd_nacional, erros_dia = erro_nacional(dados, ano, aj.meia_vida_dias)
    medias = _medias(dados, ano, corte, linhas_s[ano], aj.meia_vida_dias)
    if "US" not in medias:
        gerais = _medias(dados, ano, corte, meia_vida=aj.meia_vida_dias)
        medias.update({k: v for k, v in gerais.items() if k == "US"})
    if aj != AJUSTES_PUBLICADOS:
        sd_nacional *= aj.fator_sd_nacional
        fund_c = replace(fund_c, sd_corrida=fund_c.sd_corrida * aj.fator_sd_corrida)
        fund_s = replace(fund_s, sd_corrida=fund_s.sd_corrida * aj.fator_sd_corrida)
        f = aj.fator_erro_sondagens
        erro = replace(
            erro, base=erro.base * f, por_instituto=erro.por_instituto * f, sd_ano=erro.sd_ano * f
        )

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
    correcao = 0.0
    if aj.vies_generico and fonte != "sondagens_senado":
        correcao = vies_voto_generico(erros_dia)
        margem -= correcao
    ambiente = Ambiente(margem=margem + aj.desvio_ambiente, sd=sd)

    rng = np.random.default_rng(semente)
    choques = sortear_choques(rng, SIMULACOES, ambiente, fund_c.sd_regiao, aj.graus_liberdade)
    camara = simular_camara(linhas_c[ano], fund_c, ambiente, choques, rng)
    composicao = composicao_senado(dados, ano)
    if aj.incumbentes_sondagens:
        vies = desvio_incumbentes(dados, ano, aj.meia_vida_dias)
        for linha in linhas_s[ano]:
            m = medias.get(linha.id)
            if m is not None and linha.incumbente != 0:
                medias[linha.id] = replace(m, margem=m.margem - vies * linha.incumbente)
    if aj.sem_sondagens_senado:
        # O ambiente já foi estimado; só a simulação de cada corrida fica sem sondagens.
        medias = {k: v for k, v in medias.items() if k == "US"}
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
        correcao_vies=correcao,
    )
