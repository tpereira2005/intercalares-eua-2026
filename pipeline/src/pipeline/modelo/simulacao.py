"""Simulação de Monte Carlo com erros correlacionados (nacional, regional e por corrida).

Cada cenário sorteia, por esta ordem:

1. um erro nacional comum a todas as corridas das duas câmaras (t de Student com 5 graus
   de liberdade, para caudas mais pesadas do que a normal);
2. um erro na tradução do ambiente nacional para os distritos (por câmara);
3. um choque por região do Census, partilhado pela Câmara e pelo Senado;
4. o erro próprio de cada corrida.

As corridas do Senado com sondagens combinam fundamentos e média de sondagens com pesos
inversamente proporcionais às respetivas variâncias. Tudo é simétrico: trocar os partidos
em todas as entradas troca exatamente os resultados.
"""

from dataclasses import dataclass, field

import numpy as np
import numpy.typing as npt

from pipeline.modelo.dados import LinhaModelo
from pipeline.modelo.estimacao import ErroSondagens, Fundamentos
from pipeline.modelo.media import Media

GRAUS_LIBERDADE = 5
REGIOES = ("nordeste", "centro_oeste", "sul", "oeste")


@dataclass(frozen=True, slots=True)
class Ambiente:
    margem: float
    """Estimativa do ambiente nacional (voto genérico D-R, em pontos)."""

    sd: float
    """Desvio-padrão do erro dessa estimativa face ao voto nacional real."""


@dataclass(frozen=True, slots=True)
class ComposicaoSenado:
    """Lugares que não vão a votos e regra de desempate."""

    continuam_d: int
    """Democratas e independentes que votam com eles, fora de eleição."""

    continuam_r: int
    desempate: str
    """Partido do vice-presidente, que desempata 50-50 (``R`` em 2026)."""


@dataclass(slots=True)
class ResultadoCorrida:
    linha: LinhaModelo
    fundamentos: float
    """Margem esperada só com fundamentos (com o ambiente nacional estimado)."""

    sondagens: Media | None
    peso_sondagens: float
    media: float
    p10: float
    p90: float
    prob_d: float
    """Probabilidade de vitória do lado democrata (incluindo independente nesse lado)."""


@dataclass(slots=True)
class ResultadoCamara:
    corridas: list[ResultadoCorrida]
    lugares_d: npt.NDArray[np.int64]
    """Lugares do lado democrata em cada cenário (inclui os que não vão a votos no Senado)."""

    lugares_i: npt.NDArray[np.int64]
    """Quantos desses lugares (de qualquer lado) ficam com independentes."""

    prob_controlo_d: float
    prob_controlo_r: float
    limiar_nacional: float | None
    """Ambiente nacional a partir do qual os Democratas passam a favoritos ao controlo."""

    nacional_simulado: npt.NDArray[np.float64] = field(repr=False)


def _t_unitario(
    rng: np.random.Generator, n: int, graus: int = GRAUS_LIBERDADE
) -> npt.NDArray[np.float64]:
    """t de Student com ``graus`` graus de liberdade, reescalada para variância 1."""
    t = rng.standard_t(graus, size=n)
    return np.asarray(t / np.sqrt(graus / (graus - 2)), dtype=np.float64)


def _limiar(nacional: npt.NDArray[np.float64], controlo: npt.NDArray[np.bool_]) -> float | None:
    """Valor do ambiente nacional em que a probabilidade de controlo D cruza 50%."""
    ordem = np.argsort(nacional)
    n = len(ordem)
    blocos = 40
    xs, ps = [], []
    for i in range(blocos):
        idx = ordem[i * n // blocos : (i + 1) * n // blocos]
        xs.append(float(np.mean(nacional[idx])))
        ps.append(float(np.mean(controlo[idx])))
    for i in range(1, blocos):
        if ps[i - 1] < 0.5 <= ps[i]:
            frac = (0.5 - ps[i - 1]) / (ps[i] - ps[i - 1])
            return xs[i - 1] + frac * (xs[i] - xs[i - 1])
    return None


@dataclass(frozen=True, slots=True)
class Choques:
    nacional: npt.NDArray[np.float64]
    regioes: dict[str, npt.NDArray[np.float64]]


def sortear_choques(
    rng: np.random.Generator,
    n: int,
    ambiente: Ambiente,
    sd_regiao: float,
    graus_liberdade: int = GRAUS_LIBERDADE,
) -> Choques:
    return Choques(
        nacional=ambiente.sd * _t_unitario(rng, n, graus_liberdade),
        regioes={r: rng.normal(0.0, sd_regiao, n) for r in REGIOES},
    )


def simular_camara(
    linhas: list[LinhaModelo],
    fundamentos: Fundamentos,
    ambiente: Ambiente,
    choques: Choques,
    rng: np.random.Generator,
) -> ResultadoCamara:
    n = len(choques.nacional)
    erro_ano = rng.normal(0.0, fundamentos.sd_ano, n)
    lugares = np.zeros(n, dtype=np.int64)
    lugares_i = np.zeros(n, dtype=np.int64)
    corridas: list[ResultadoCorrida] = []
    for linha in linhas:
        esperado = fundamentos.esperado(linha, ambiente.margem)
        if linha.certo is not None:
            vence = np.full(n, linha.certo in {"D", "I"})
            margens = np.full(n, 100.0 if linha.certo in {"D", "I"} else -100.0)
        else:
            margens = (
                esperado
                + choques.nacional
                + erro_ano
                + choques.regioes[linha.regiao]
                + rng.normal(0.0, fundamentos.sd_corrida, n)
            )
            vence = margens > 0
        lugares += vence
        lugares_i += _independentes(linha, vence)
        corridas.append(_resumo(linha, esperado, None, 0.0, margens))
    # Maioria absoluta dos lugares em jogo (218 de 435), igual para os dois lados.
    maioria = len(linhas) // 2 + 1
    controlo_d = lugares >= maioria
    controlo_r = len(linhas) - lugares >= maioria
    return ResultadoCamara(
        corridas=corridas,
        lugares_d=lugares,
        lugares_i=lugares_i,
        prob_controlo_d=float(np.mean(controlo_d)),
        prob_controlo_r=float(np.mean(controlo_r)),
        limiar_nacional=_limiar(ambiente.margem + choques.nacional, controlo_d),
        nacional_simulado=ambiente.margem + choques.nacional,
    )


def simular_senado(
    linhas: list[LinhaModelo],
    fundamentos: Fundamentos,
    erro: ErroSondagens,
    medias: dict[str, Media],
    ambiente: Ambiente,
    *,
    composicao: ComposicaoSenado,
    choques: Choques,
    rng: np.random.Generator,
) -> ResultadoCamara:
    n = len(choques.nacional)
    erro_ano = rng.normal(0.0, fundamentos.sd_ano, n)
    # Parte do erro comum das sondagens que não acompanha o voto genérico.
    sd_residual = float(
        np.sqrt(max(erro.sd_ano**2 - (erro.ligacao_nacional * ambiente.sd) ** 2, 0.0))
    )
    erro_sondagens_ano = rng.normal(0.0, sd_residual, n)
    lugares_d = np.full(n, composicao.continuam_d, dtype=np.int64)
    lugares_r = np.full(n, composicao.continuam_r, dtype=np.int64)
    lugares_i = np.zeros(n, dtype=np.int64)
    corridas: list[ResultadoCorrida] = []
    for linha in linhas:
        esperado = fundamentos.esperado(linha, ambiente.margem)
        sond = medias.get(linha.id)
        if linha.certo is not None:
            margens = np.full(n, 100.0 if linha.certo in {"D", "I"} else -100.0)
            peso = 0.0
        else:
            var_f = fundamentos.sd_corrida**2
            var_p = erro.variancia(sond.institutos) if sond else np.inf
            peso = float(var_f / (var_f + var_p)) if sond else 0.0
            centro = (1 - peso) * esperado + peso * (sond.margem if sond else 0.0)
            var_propria = var_f * var_p / (var_f + var_p) if sond else var_f
            comum = (1 - peso) * (choques.nacional + erro_ano) + peso * (
                erro.ligacao_nacional * choques.nacional + erro_sondagens_ano
            )
            margens = (
                centro
                + comum
                + choques.regioes[linha.regiao]
                + rng.normal(0.0, float(np.sqrt(var_propria)), n)
            )
        vence = margens > 0
        lugares_d += vence
        lugares_r += ~vence
        lugares_i += _independentes(linha, vence)
        corridas.append(_resumo(linha, esperado, sond, peso, margens))
    controlo_r = (lugares_r >= 51) | ((lugares_r == 50) & (composicao.desempate == "R"))
    controlo_d = (lugares_d >= 51) | ((lugares_d == 50) & (composicao.desempate == "D"))
    return ResultadoCamara(
        corridas=corridas,
        lugares_d=lugares_d,
        lugares_i=lugares_i,
        prob_controlo_d=float(np.mean(controlo_d)),
        prob_controlo_r=float(np.mean(controlo_r)),
        limiar_nacional=_limiar(ambiente.margem + choques.nacional, ~controlo_r),
        nacional_simulado=ambiente.margem + choques.nacional,
    )


def _independentes(linha: LinhaModelo, vence: npt.NDArray[np.bool_]) -> npt.NDArray[np.int64]:
    """Lugares ganhos por independentes (contam para a bancada do lado que ocupam)."""
    if linha.lado_d_independente or linha.certo == "I":
        return vence.astype(np.int64)
    if linha.lado_r_independente:
        return (~vence).astype(np.int64)
    return np.zeros(len(vence), dtype=np.int64)


def _resumo(
    linha: LinhaModelo,
    esperado: float,
    sond: Media | None,
    peso: float,
    margens: npt.NDArray[np.float64],
) -> ResultadoCorrida:
    return ResultadoCorrida(
        linha=linha,
        fundamentos=esperado,
        sondagens=sond,
        peso_sondagens=peso,
        media=float(np.mean(margens)),
        p10=float(np.percentile(margens, 10)),
        p90=float(np.percentile(margens, 90)),
        prob_d=float(np.mean(margens > 0)),
    )
