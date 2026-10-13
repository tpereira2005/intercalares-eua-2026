"""Modelo C (noite eleitoral) em noites sintéticas com resultado conhecido.

Cada noite parte de uma previsão sintética, sorteia um resultado final coerente com ela e
revela a contagem aos poucos, com o voto contado primeiro inclinado para um dos lados (ao
acaso, com sinal aleatório). Verifica-se que sem votos a projeção é a previsão, que com
tudo contado é o resultado, que trocar os partidos troca a projeção e que os intervalos
de 80% contêm o resultado com a frequência certa.
"""

import math
from dataclasses import dataclass
from datetime import UTC, datetime

import numpy as np
import pytest

from contratos.base import Fonte, Metadados
from contratos.noite import ProjecaoNoite
from contratos.previsao import PrevisaoCongresso, PrevisaoCorrida, ResumoCamara
from contratos.resultados import ResultadosParciais, UnidadeContagem
from pipeline.modelo.noite.corrida import Parametros, PriorCorrida, analisar
from pipeline.modelo.noite.entrada import TOTAL, Base, Contagem, Instantaneo, de_parciais
from pipeline.modelo.noite.projecao import Z_P90, projetar
from pipeline.modelo.previsao import Dados, prever
from pipeline.modelo.publicar import montar

AGORA = datetime(2018, 11, 6, 20, tzinfo=UTC)
FONTE = Fonte(nome="Sintética", url="https://example.org/", obtida_em=AGORA)
SIMULACOES = 4000


@pytest.fixture(scope="module")
def previsao(dados_sinteticos: Dados) -> PrevisaoCongresso:
    previsao = montar(prever(dados_sinteticos, 2018), fontes=[FONTE], gerado_em=AGORA)
    # Os dados sintéticos só têm 129 distritos: a câmara sintética tem esse tamanho.
    lugares = sum(c.camara == "camara" for c in previsao.corridas)
    camara = previsao.camara.model_copy(
        update={"lugares_total": lugares, "maioria": lugares // 2 + 1}
    )
    return previsao.model_copy(update={"camara": camara})


@dataclass(frozen=True, slots=True)
class Noite:
    referencia: dict[str, dict[str, Base]]
    estagios: dict[float, Instantaneo]
    finais: dict[str, float]


def _votos(corrida: str, unidade: str, n: int, margem: float) -> Contagem:
    outros = round(0.02 * n)
    validos = n - outros
    d = round(validos * (1 + margem / 100) / 2)
    return Contagem(corrida, unidade, d, validos - d, outros)


def gerar_noite(previsao: PrevisaoCongresso, semente: int) -> Noite:
    """Uma noite: referência por condado, resultado final e contagens parciais."""
    rng = np.random.default_rng(semente)
    sd_nacional = previsao.ambiente.desvio_padrao
    nacional = rng.normal(0, sd_nacional)
    referencia: dict[str, dict[str, Base]] = {}
    unidades: dict[str, list[tuple[str, float, float]]] = {}
    for c in previsao.corridas:
        if c.decidida is not None:
            continue
        sd = (c.margem_p90 - c.margem_p10) / (2 * Z_P90)
        comum = nacional * min(1.0, 0.8 * sd / sd_nacional)
        desvio = comum + rng.normal(0, math.sqrt(max(sd**2 - comum**2 / 2, 0.25)))
        if c.camara == "senado":
            condados = referencia.setdefault(c.estado, {})
            if not condados:
                for i in range(int(rng.integers(4, 30))):
                    condados[f"{i:05d}"] = Base(
                        float(rng.lognormal(10, 1)), float(rng.normal(c.margem_prevista, 12))
                    )
            votos = sum(b.votos for b in condados.values())
            base = sum(b.votos * b.margem for b in condados.values()) / votos
            s = c.margem_prevista - base + desvio
            unidades[c.id] = [
                (u, 0.72 * b.votos * float(rng.lognormal(0, 0.1)), b.margem + s + rng.normal(0, 6))
                for u, b in condados.items()
            ]
        else:
            votos_d = float(rng.uniform(150_000, 350_000))
            unidades[c.id] = [(TOTAL, votos_d, c.margem_prevista + desvio)]

    estagios: dict[float, Instantaneo] = {}
    inclinacao = {k: rng.normal(0, 10) for k in unidades}
    ruido = {k: rng.normal(0, 0.25, len(v)) for k, v in unidades.items()}
    for fase in (0.0, 0.1, 0.3, 0.6, 0.9, 1.0):
        contagens: list[Contagem] = []
        for corrida, lista in unidades.items():
            for (unidade, esperados, final), r in zip(lista, ruido[corrida], strict=True):
                fracao = 0.0 if fase == 0 else 1.0 if fase == 1 else float(np.clip(fase + r, 0, 1))
                n = round(fracao * esperados)
                if n == 0:
                    continue
                contagem = _votos(corrida, unidade, n, final + (1 - fracao) * inclinacao[corrida])
                seccoes = (
                    100
                    if fracao == 1
                    else int(np.clip(100 * (fracao + rng.normal(0, 0.05)), 1, 99))
                )
                contagem = Contagem(
                    contagem.corrida,
                    contagem.unidade,
                    contagem.votos_d,
                    contagem.votos_r,
                    contagem.votos_outros,
                    1.0 if fracao == 1 else None,
                    seccoes_reportadas=seccoes,
                    seccoes_totais=100,
                )
                contagens.append(contagem)
        estagios[fase] = Instantaneo(AGORA, tuple(contagens))
    somas: dict[str, list[int]] = {}
    for contagem in estagios[1.0].contagens:
        soma = somas.setdefault(contagem.corrida, [0, 0])
        soma[0] += contagem.votos_d - contagem.votos_r
        soma[1] += contagem.votos
    finais = {k: 100 * d / t for k, (d, t) in somas.items()}
    return Noite(referencia, estagios, finais)


def _projetar(previsao: PrevisaoCongresso, noite: Noite, fase: float) -> ProjecaoNoite:
    return projetar(
        previsao,
        noite.estagios[fase],
        noite.referencia,
        fontes=[FONTE],
        gerado_em=AGORA,
        simulacoes=SIMULACOES,
    )


def test_sem_votos_fica_a_previsao(previsao: PrevisaoCongresso) -> None:
    projecao = _projetar(previsao, gerar_noite(previsao, 1), 0.0)
    for c in projecao.corridas:
        assert abs(c.prob_d - c.prob_d_prior) < 0.05, c.id
        assert abs(c.margem_projetada - c.margem_prior) < 0.5, c.id
    assert abs(projecao.desvio_nacional.media) < 1e-9
    for resumo in (projecao.camara, projecao.senado):
        assert abs(resumo.prob_controlo_d - resumo.prob_controlo_d_prior) < 0.1
        assert resumo.corridas_com_votos == 0


def _variacao_total(a: ResumoCamara, b: ProjecaoNoite, camara: str) -> float:
    noite = b.camara if camara == "camara" else b.senado
    p = {x.lugares: x.probabilidade for x in a.distribuicao}
    q = {x.lugares: x.probabilidade for x in noite.distribuicao}
    return 0.5 * sum(abs(p.get(k, 0.0) - q.get(k, 0.0)) for k in p.keys() | q.keys())


def test_sem_votos_reproduz_o_controlo_da_previsao(previsao: PrevisaoCongresso) -> None:
    """Sem votos, a projeção tem a estrutura de erros da previsão: o controlo das câmaras
    e a distribuição de lugares coincidem, a menos do erro de Monte Carlo das duas."""
    projecao = projetar(
        previsao,
        Instantaneo(AGORA, ()),
        {},
        fontes=[FONTE],
        gerado_em=AGORA,
        simulacoes=20_000,
    )
    for prevista, noite in ((previsao.camara, projecao.camara), (previsao.senado, projecao.senado)):
        assert noite.prob_controlo_d == pytest.approx(prevista.prob_controlo_d, abs=0.015)
        assert noite.lugares_d_media == pytest.approx(prevista.lugares_d_media, abs=0.3)
        assert _variacao_total(prevista, projecao, prevista.camara) < 0.04
    diferencas = [c.prob_d - c.prob_d_prior for c in projecao.corridas]
    assert abs(float(np.mean(diferencas))) < 0.003
    assert max(map(abs, diferencas)) < 0.03


def test_contagem_completa_da_o_resultado(previsao: PrevisaoCongresso) -> None:
    noite = gerar_noite(previsao, 2)
    projecao = _projetar(previsao, noite, 1.0)
    for c in projecao.corridas:
        if c.decidida:
            continue
        assert c.margem_projetada == pytest.approx(noite.finais[c.id], abs=1e-6), c.id
        assert c.margem_p90 - c.margem_p10 < 1e-6
        assert c.prob_d == float(noite.finais[c.id] > 0)
        assert c.fracao_contada == pytest.approx(1.0)


def _espelhar_corrida(c: PrevisaoCorrida) -> PrevisaoCorrida:
    trocar = {"D": "R", "R": "D", "I": "I", None: None}
    return c.model_copy(
        update={
            "margem_prevista": -c.margem_prevista,
            "margem_fundamentos": -c.margem_fundamentos,
            "margem_sondagens": None if c.margem_sondagens is None else -c.margem_sondagens,
            "margem_p10": -c.margem_p90,
            "margem_p90": -c.margem_p10,
            "prob_d": 1 - c.prob_d,
            "decidida": trocar[c.decidida],
        }
    )


def _espelhar_resumo(r: ResumoCamara) -> ResumoCamara:
    return r.model_copy(
        update={
            "prob_controlo_d": r.prob_controlo_r,
            "prob_controlo_r": r.prob_controlo_d,
            "lugares_fora_de_jogo_d": r.lugares_fora_de_jogo_r,
            "lugares_fora_de_jogo_r": r.lugares_fora_de_jogo_d,
        }
    )


def test_trocar_os_partidos_troca_a_projecao(previsao: PrevisaoCongresso) -> None:
    noite = gerar_noite(previsao, 3)
    espelho = previsao.model_copy(
        update={
            "corridas": tuple(_espelhar_corrida(c) for c in previsao.corridas),
            "camara": _espelhar_resumo(previsao.camara),
            "senado": _espelhar_resumo(previsao.senado),
        }
    )
    contagens = tuple(
        Contagem(c.corrida, c.unidade, c.votos_r, c.votos_d, c.votos_outros, c.fracao_contada,
                 c.seccoes_reportadas, c.seccoes_totais)
        for c in noite.estagios[0.3].contagens
    )  # fmt: skip
    referencia = {
        e: {u: Base(b.votos, -b.margem) for u, b in condados.items()}
        for e, condados in noite.referencia.items()
    }
    original = _projetar(previsao, noite, 0.3)
    trocada = projetar(
        espelho,
        Instantaneo(AGORA, contagens),
        referencia,
        fontes=[FONTE],
        gerado_em=AGORA,
        desempate="D",
        simulacoes=SIMULACOES,
    )
    assert trocada.desvio_nacional.media == pytest.approx(-original.desvio_nacional.media)
    for a, b in zip(original.corridas, trocada.corridas, strict=True):
        assert b.margem_contada == (None if a.margem_contada is None else -a.margem_contada)
        assert b.margem_projetada == pytest.approx(-a.margem_projetada, abs=1e-6), a.id
        assert b.margem_p10 == pytest.approx(-a.margem_p90, abs=1e-6), a.id
        assert b.prob_d == pytest.approx(1 - a.prob_d, abs=1e-9), a.id
    for x, y in ((original.camara, trocada.camara), (original.senado, trocada.senado)):
        assert y.prob_controlo_d == pytest.approx(x.prob_controlo_r, abs=1e-9)
        assert y.lugares_d_media == pytest.approx(x.lugares_total - x.lugares_d_media, abs=1e-9)


def test_analise_de_uma_corrida_e_exatamente_simetrica() -> None:
    prior = PriorCorrida("PA-S", "PA", 2.0, 5.0)
    espelho = PriorCorrida("PA-S", "PA", -2.0, 5.0)
    base = {"42001": Base(1000.0, -20.0), "42003": Base(3000.0, 15.0), "42005": Base(500, 3)}
    base_e = {u: Base(b.votos, -b.margem) for u, b in base.items()}
    contagens = [
        Contagem("PA-S", "42001", 300, 420, 10),
        Contagem("PA-S", "42003", 900, 600, 20, seccoes_reportadas=5, seccoes_totais=5),
    ]
    trocadas = [Contagem(c.corrida, c.unidade, c.votos_r, c.votos_d, c.votos_outros,
                         c.fracao_contada, c.seccoes_reportadas, c.seccoes_totais)
                for c in contagens]  # fmt: skip
    p = Parametros(votos_minimos=100)
    a = analisar(prior, contagens, base, 0.72, p)
    b = analisar(espelho, trocadas, base_e, 0.72, p)
    assert b.alfa == pytest.approx(-a.alfa)
    assert b.beta == pytest.approx(a.beta)
    assert b.gama == pytest.approx(a.gama)
    assert b.s0 == pytest.approx(-a.s0)
    assert a.s_chapeu is not None
    assert b.s_chapeu == pytest.approx(-a.s_chapeu)


def test_intervalos_de_80_estao_calibrados(previsao: PrevisaoCongresso) -> None:
    dentro: dict[float, list[bool]] = {0.1: [], 0.3: [], 0.6: [], 0.9: []}
    brier: dict[float, list[float]] = {0.0: [], 0.3: [], 0.6: [], 0.9: []}
    for semente in range(10, 16):
        noite = gerar_noite(previsao, semente)
        for fase in sorted(set(dentro) | set(brier)):
            projecao = _projetar(previsao, noite, fase)
            for c in projecao.corridas:
                if c.decidida:
                    continue
                real = noite.finais[c.id]
                if fase in dentro:
                    dentro[fase].append(c.margem_p10 <= real <= c.margem_p90)
                if fase in brier:
                    brier[fase].append((c.prob_d - (real > 0)) ** 2)
    for fase, valores in dentro.items():
        cobertura = sum(valores) / len(valores)
        assert 0.72 <= cobertura <= 0.95, (fase, cobertura)
    medias = [sum(v) / len(v) for _, v in sorted(brier.items())]
    assert medias == sorted(medias, reverse=True)


def test_corrida_sem_feed_mantem_a_incerteza(previsao: PrevisaoCongresso) -> None:
    noite = gerar_noite(previsao, 4)
    sem_senado = Instantaneo(
        AGORA, tuple(c for c in noite.estagios[0.6].contagens if not c.corrida.endswith("-S"))
    )
    projecao = projetar(
        previsao, sem_senado, noite.referencia, fontes=[FONTE], gerado_em=AGORA,
        simulacoes=SIMULACOES,
    )  # fmt: skip
    priores = {c.id: c for c in previsao.corridas}
    for c in projecao.corridas:
        if c.camara != "senado" or c.decidida:
            continue
        p = priores[c.id]
        assert c.votos_contados == 0
        assert c.fracao_contada is None or c.fracao_contada == 0
        assert c.margem_p90 - c.margem_p10 > 0.6 * (p.margem_p90 - p.margem_p10), c.id


def test_converte_os_resultados_parciais() -> None:
    parciais = ResultadosParciais(
        metadados=Metadados(gerado_em=AGORA, fontes=(FONTE,)),
        ano=2026,
        instante=AGORA,
        unidades=(
            UnidadeContagem(
                corrida="NC-S", unidade="37001", votos_d=10, votos_r=20, votos_outros=1,
                seccoes_reportadas=3, seccoes_totais=4,
            ),
            UnidadeContagem(
                corrida="GA-02", unidade="total", votos_d=5, votos_r=5, votos_outros=0,
                percentagem_contada=0.4,
            ),
        ),
    )  # fmt: skip
    instantaneo = de_parciais(parciais)
    nc, ga = instantaneo.contagens
    assert (nc.votos_d, nc.votos_r, nc.votos_outros, nc.fracao_seccoes) == (10, 20, 1, 0.75)
    assert nc.fracao_contada is None
    assert ga.fracao_contada == 0.4
    assert ga.fracao_seccoes is None
