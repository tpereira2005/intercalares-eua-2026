"""Do perfil etário do voto antecipado à margem: o modelo da secção 6.4 do plano.

Só a Carolina do Norte tem os ficheiros completos (eleitores, boletins e histórico de voto)
para o fazer de ponta a ponta. Os grupos são faixa etária e partido de registo (o
``outro`` junta-se aos não filiados, porque é muito pequeno). Três passos:

1. **Eleitorado final projetado.** Os votos antecipados de cada grupo até ``d`` dias antes
   da eleição multiplicam-se pela razão entre o eleitorado final e o voto antecipado até ao
   mesmo dia nas eleições de referência do mesmo tipo (curvas de chegada por grupo).
2. **Margem de cada grupo.** Regressão ecológica nas margens presidenciais por condado
   (2020 e 2024), com ``logit q_fp = mu_p + a_f`` (``q`` a parte democrata dos dois
   partidos) e penalização para zero, o que mantém as margens entre -100 e +100 e é
   simétrico entre partidos. As várias versões (anos e penalizações) dão a incerteza.
3. **Inclinação da participação.** ``T = Σ_g (v_g - r_g) · m_g``: quanto o eleitorado
   (``v``, quotas dos votantes) puxa a margem face aos registados (``r``). Comparar com
   os registados do próprio ano retira a deriva do registo partidário (democratas
   conservadores que passam a republicanos, por exemplo), que mudaria a composição sem
   mudar o voto. O sinal publicado é ``T`` projetado para 2026 menos ``T`` de 2022.

É um diagnóstico mostrado, com peso zero na previsão: os backtests dizem que acerta no
sentido mais vezes do que na magnitude (ver ``docs/metodologia/idade.md``).
"""

import math
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass

import numpy as np
import numpy.typing as npt
import polars as pl

Vetor = npt.NDArray[np.float64]

FAIXAS = ("18-24", "25-29", "30-39", "40-49", "50-64", "65-74", "75+")
PARTIDOS = ("dem", "rep", "nao_afiliado")
GRUPOS = tuple((f, p) for f in FAIXAS for p in PARTIDOS)
PENALIZACOES = (0.5, 2.0, 8.0)
"""Penalizações da regressão ecológica: da que deixa a idade variar mais à que quase só
deixa o partido. A central é a do meio."""

ITERACOES = 200


def _partido() -> pl.Expr:
    p = pl.col("partido")
    return pl.when(p.is_in(["dem", "rep"])).then(p).otherwise(pl.lit("nao_afiliado"))


def contagens(tabela: pl.DataFrame) -> Vetor:
    """Soma de ``n`` por grupo, na ordem de ``GRUPOS`` (faixas desconhecidas ficam de fora)."""
    g = (
        tabela.filter(pl.col("faixa").is_in(FAIXAS))
        .with_columns(partido=_partido())
        .group_by("faixa", "partido")
        .agg(pl.col("n").sum())
    )
    por_grupo = {(r["faixa"], r["partido"]): float(r["n"]) for r in g.iter_rows(named=True)}
    return np.array([por_grupo.get(k, 0.0) for k in GRUPOS])


def quotas(v: Vetor) -> Vetor:
    total = float(v.sum())
    return v / total if total > 0 else v


def antecipado_ate(demografico: pl.DataFrame, dias_antes: int) -> Vetor:
    """Votos antecipados por grupo chegados até ``dias_antes`` dias antes da eleição."""
    return contagens(
        demografico.filter(pl.col("modalidade") != "nao_votou", pl.col("dias_antes") >= dias_antes)
    )


def registados(demografico: pl.DataFrame) -> Vetor:
    """Quotas dos eleitores registados (o cubo do voto antecipado inclui quem não votou)."""
    return quotas(contagens(demografico))


@dataclass(frozen=True, slots=True)
class Referencia:
    """Uma eleição passada: o cubo do voto antecipado e o do eleitorado final."""

    ano: int
    demografico: pl.DataFrame
    final: pl.DataFrame


def projetar_final(antecipado: Vetor, referencias: Sequence[Referencia], dias_antes: int) -> Vetor:
    """Quotas do eleitorado final projetadas a partir do voto antecipado até ``dias_antes``."""
    razoes = [
        contagens(r.final) / np.maximum(antecipado_ate(r.demografico, dias_antes), 1.0)
        for r in referencias
    ]
    return quotas(antecipado * np.mean(razoes, axis=0))


def margens_grupos(
    composicao_condados: npt.NDArray[np.float64],
    margens: Vetor,
    votos: Vetor,
    penalizacao: float,
) -> npt.NDArray[np.float64]:
    """Margem D-R (pontos) de cada grupo, ``7 x 3``, por regressão ecológica.

    ``composicao_condados`` tem uma linha por condado com as quotas dos grupos no
    eleitorado final; ``margens`` e ``votos`` são o resultado presidencial do condado.
    Gauss-Newton com penalização em ``mu`` (fraca) e em ``a`` (``penalizacao``), a partir de
    zero; tudo é simétrico entre os dois partidos.
    """
    n = len(margens)
    pesos = votos / votos.mean()
    theta = np.zeros(len(PARTIDOS) + len(FAIXAS))
    penal = np.diag([0.01] * len(PARTIDOS) + [penalizacao] * len(FAIXAS)) * n * 25.0
    for _ in range(ITERACOES):
        logit = theta[len(PARTIDOS) :, None] + theta[None, : len(PARTIDOS)]
        q = 1.0 / (1.0 + np.exp(-logit))
        residuo = margens - composicao_condados @ (100.0 * (2.0 * q - 1.0)).ravel()
        derivada = composicao_condados * (200.0 * q * (1.0 - q)).ravel()
        jacobiano = np.zeros((n, len(theta)))
        for i, (f, p) in enumerate(GRUPOS):
            jacobiano[:, PARTIDOS.index(p)] += derivada[:, i]
            jacobiano[:, len(PARTIDOS) + FAIXAS.index(f)] += derivada[:, i]
        passo = np.linalg.solve(
            jacobiano.T @ (jacobiano * pesos[:, None]) + penal,
            jacobiano.T @ (residuo * pesos) - penal @ theta,
        )
        theta += 0.5 * passo
        if float(np.abs(passo).max()) < 1e-10:
            break
    logit = theta[len(PARTIDOS) :, None] + theta[None, : len(PARTIDOS)]
    return 100.0 * (2.0 / (1.0 + np.exp(-logit)) - 1.0)


def composicao_condados(final: pl.DataFrame, condados: Sequence[str]) -> npt.NDArray[np.float64]:
    """Quotas dos grupos no eleitorado final de cada condado (uma linha por condado)."""
    linhas = []
    por_condado = final.partition_by("fips_condado", as_dict=True)
    for c in condados:
        tabela = por_condado.get((c,))
        linhas.append(quotas(contagens(tabela)) if tabela is not None else np.zeros(len(GRUPOS)))
    return np.array(linhas)


def conjunto_margens(
    finais: Mapping[int, pl.DataFrame],
    presidenciais: Mapping[int, Mapping[str, tuple[float, float]]],
) -> dict[tuple[int, float], Vetor]:
    """Margens dos grupos para cada ano presidencial e penalização (vetor na ordem de
    ``GRUPOS``). ``presidenciais[ano][fips] = (votos, margem)``."""
    conjunto: dict[tuple[int, float], Vetor] = {}
    for ano, resultados in sorted(presidenciais.items()):
        condados = sorted(resultados)
        composicao = composicao_condados(finais[ano], condados)
        votos = np.array([resultados[c][0] for c in condados])
        margens = np.array([resultados[c][1] for c in condados])
        for lam in PENALIZACOES:
            conjunto[ano, lam] = margens_grupos(composicao, margens, votos, lam).ravel()
    return conjunto


def _tipo(ano: int) -> bool:
    """Presidencial (``True``) ou intercalar."""
    return ano % 4 == 0


def inclinacao(votantes: Vetor, registo: Vetor, margens: Vetor) -> float:
    """Pontos de margem que o eleitorado puxa face aos registados."""
    return float((votantes - registo) @ margens)


@dataclass(frozen=True, slots=True)
class Backtest:
    ano: int
    referencias: tuple[int, ...]
    dias_antes: int
    real: float
    """Inclinação do eleitorado final desse ano (margens centrais)."""

    projetada: float


def backtests(anos: Mapping[int, Referencia], margens: Vetor, dias_antes: int) -> list[Backtest]:
    """Cada ano projetado com as eleições do mesmo tipo (exceto ele próprio)."""
    resultado = []
    for ano, alvo in sorted(anos.items()):
        refs = [r for a, r in sorted(anos.items()) if a != ano and _tipo(a) == _tipo(ano)]
        if not refs:
            continue
        registo = registados(alvo.demografico)
        projetadas = projetar_final(antecipado_ate(alvo.demografico, dias_antes), refs, dias_antes)
        resultado.append(
            Backtest(
                ano=ano,
                referencias=tuple(r.ano for r in refs),
                dias_antes=dias_antes,
                real=inclinacao(quotas(contagens(alvo.final)), registo, margens),
                projetada=inclinacao(projetadas, registo, margens),
            )
        )
    return resultado


@dataclass(frozen=True, slots=True)
class Diagnostico:
    dias_antes: int
    votos_antecipados: int
    ano_referencia: int
    quotas_antecipado: Vetor
    quotas_projetadas: Vetor
    quotas_registados: Vetor
    quotas_final_referencia: Vetor
    margens: Vetor
    """Margens centrais dos grupos."""

    margens_minimas: Vetor
    margens_maximas: Vetor
    inclinacao_projetada: float
    inclinacao_referencia: float
    efeito: float
    """Inclinação projetada menos a da eleição de referência (pontos D-R)."""

    efeito_p10: float
    efeito_p90: float
    erro_backtest: float
    """Raiz do erro quadrático médio da inclinação projetada nos backtests, no mesmo dia."""

    backtests: tuple[Backtest, ...]


Z_P90 = 1.2815515655446004
MARGENS_CENTRAIS = (2024, 2.0)


def diagnosticar(
    atual: pl.DataFrame,
    anos: Mapping[int, Referencia],
    conjunto: Mapping[tuple[int, float], Vetor],
    *,
    ano: int,
    dias_antes: int,
) -> Diagnostico:
    """O sinal etário de ``ano`` com o voto antecipado até ``dias_antes`` (cubo ``atual``).

    As curvas de chegada vêm das eleições do mesmo tipo; a referência é a última delas.
    O intervalo de 80% junta o erro dos backtests no mesmo dia e a dispersão entre as
    versões das margens dos grupos.
    """
    mesmas = [r for a, r in sorted(anos.items()) if _tipo(a) == _tipo(ano)]
    referencia = mesmas[-1]
    margens = conjunto[MARGENS_CENTRAIS]
    antecipado = antecipado_ate(atual, dias_antes)
    registo = registados(atual)
    projetadas = projetar_final(antecipado, mesmas, dias_antes)
    registo_ref = registados(referencia.demografico)
    final_ref = quotas(contagens(referencia.final))

    def efeito(m: Vetor) -> float:
        return inclinacao(projetadas, registo, m) - inclinacao(final_ref, registo_ref, m)

    efeitos = [efeito(m) for m in conjunto.values()]
    testes = backtests(anos, margens, dias_antes)
    erro = math.sqrt(float(np.mean([(b.projetada - b.real) ** 2 for b in testes])))
    central = efeito(margens)
    sd = math.sqrt(erro**2 + float(np.var(efeitos)))
    matriz = np.array(list(conjunto.values()))
    return Diagnostico(
        dias_antes=dias_antes,
        votos_antecipados=int(antecipado.sum()),
        ano_referencia=referencia.ano,
        quotas_antecipado=quotas(antecipado),
        quotas_projetadas=projetadas,
        quotas_registados=registo,
        quotas_final_referencia=final_ref,
        margens=margens,
        margens_minimas=matriz.min(axis=0),
        margens_maximas=matriz.max(axis=0),
        inclinacao_projetada=inclinacao(projetadas, registo, margens),
        inclinacao_referencia=inclinacao(final_ref, registo_ref, margens),
        efeito=central,
        efeito_p10=central - Z_P90 * sd,
        efeito_p90=central + Z_P90 * sd,
        erro_backtest=erro,
        backtests=tuple(testes),
    )


def ler_presidenciais(
    linhas: Iterable[Mapping[str, str]], estado: str = "NC"
) -> dict[str, tuple[float, float]]:
    """``fips -> (votos, margem)`` de um CSV ``estado,fips,votos,margem``."""
    return {
        r["fips"]: (float(r["votos"]), float(r["margem"])) for r in linhas if r["estado"] == estado
    }
