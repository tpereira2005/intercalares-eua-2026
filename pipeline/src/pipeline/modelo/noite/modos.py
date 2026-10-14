"""Modelo C com a ordem de contagem: o voto antecipado conta-se primeiro e inteiro.

Nos estados de ``ORDEM_CONTAGEM`` a lei ou a prática mandam publicar o voto antecipado
(presencial e por correio recebido até à véspera) logo a seguir ao fecho das urnas,
condado a condado, antes do voto do dia da eleição. Quando a fonte separa os votos por
modo, sabe-se então que parte de cada condado já chegou e que parte falta, e o modelo usa
isso em vez de uma inclinação genérica do voto contado primeiro.

Para cada unidade ``u`` com votos, com margem final ``F_u = b_u + s + e_u``, a diferença
entre o voto antecipado e o resto é ``G_u = Δ + Δ_u`` (comum à corrida mais própria da
unidade, ambas de média zero: o modelo não sabe à partida que partido ganha o voto
antecipado). Com ``π_u`` a parte antecipada do voto esperado e ``x_u`` a parte do resto já
contada:

    antecipado:         F_u + (1 - π_u) G_u
    resto contado:      F_u - π_u G_u + (1 - x_u) λ_u
    resto por contar:   F_u - π_u G_u - x_u λ_u

``λ_u`` é a inclinação, dentro do resto, das secções que chegam primeiro. As três partes
somam ``E_u F_u``, como têm de somar. Tudo é linear e normal, por isso a margem final
condicionada ao desvio ``s`` e às contagens é normal com média ``alfa + beta * s`` e
desvio ``gama``, calculados aqui de forma exata (condicionamento gaussiano).
"""

from dataclasses import dataclass

import numpy as np
import numpy.typing as npt

Vetor = npt.NDArray[np.float64]

ORDEM_CONTAGEM = frozenset({"NC", "GA", "FL", "TX", "OH"})
"""Estados que publicam o voto antecipado de cada condado inteiro antes do dia da
eleição. Ficam de fora os que contam o correio depois (PA, AZ, MI, WI, NV, entre outros) e
aqueles em que a ordem não é clara (SC, IA)."""


@dataclass(frozen=True, slots=True)
class ParametrosModos:
    sd_diferenca: float = 25.0
    """Diferença comum entre o voto antecipado e o resto (pontos). Nas repetições de 2022
    e 2024 foi de 0 a 25 pontos na Carolina do Norte, na Geórgia e na Carolina do Sul,
    para um lado ou para o outro. Simétrica: a mesma para os dois partidos."""

    sd_diferenca_unidade: float = 10.0
    """Parte da diferença própria de cada unidade (5 a 10 pontos entre condados da mesma
    corrida nos mesmos dados)."""

    sd_resto: float = 8.0
    """Inclinação das secções do dia da eleição que chegam primeiro, por unidade de fração
    do resto por contar."""


@dataclass(frozen=True, slots=True)
class Condicionado:
    alfa: float
    beta: float
    var_l: float
    """Variância da margem final dados ``s`` e as contagens (sem o volume)."""

    s_chapeu: float | None
    var_chapeu: float | None


def elegivel(estado: str, n: Vetor, nc: Vetor, nr: Vetor, condados: npt.NDArray[np.bool_]) -> bool:
    """Todas as unidades com votos são condados com o voto antecipado e os modos somam o
    total.

    Só o condado garante que o voto antecipado chega inteiro: um distrito feito de partes
    de condados, ou o total de uma corrida, junta condados que já reportaram com outros
    que não, e a parte antecipada do que falta deixa de se conhecer.
    """
    com = n > 0
    if estado not in ORDEM_CONTAGEM or not com.any() or not condados[com].all():
        return False
    antecipado = np.nan_to_num(nc[com], nan=0.0)
    return bool(np.all(antecipado > 0)) and bool(
        np.allclose(antecipado + np.nan_to_num(nr[com]), n[com])
    )


@dataclass(frozen=True, slots=True)
class Contados:
    """Por unidade: votos contados (total, antecipado e resto), margens do antecipado e do
    resto, voto esperado, referência e desvio próprio."""

    n: Vetor
    nc: Vetor
    mc: Vetor
    nr: Vetor
    mr: Vetor
    e: Vetor
    b: Vetor
    sd_e: Vetor
    estimado: npt.NDArray[np.bool_]
    """O voto esperado vem da participação estimada (a fonte não diz quanto falta)."""

    completa: npt.NDArray[np.bool_]
    """Todas as secções reportaram: o pouco que falta pode ser de qualquer modo."""


@dataclass(frozen=True, slots=True)
class _Linhas:
    h: Vetor
    y: Vetor
    ruido: Vetor
    antecipado: npt.NDArray[np.bool_]


@dataclass(frozen=True, slots=True)
class _Fracoes:
    v: npt.NDArray[np.intp]
    """Índices das unidades com votos."""

    pi: Vetor
    """Parte antecipada do voto esperado."""

    x: Vetor
    """Parte do resto já contada."""

    volume: Vetor
    """Efeito na margem observada de um erro relativo de 1 no voto esperado (``π_u Ĝ``)."""


def _linhas(k: Contados, fr: _Fracoes, *, sd_lote: float, minimos: int) -> _Linhas | None:
    """Uma observação por modo de cada unidade com votos suficientes."""
    u = len(fr.v)
    tamanho = 3 * u + 2
    linhas: list[Vetor] = []
    y: list[float] = []
    ruido: list[float] = []
    tipos: list[bool] = []
    for i, j in enumerate(fr.v):
        pi, x = fr.pi[i], fr.x[i]
        if k.nc[j] >= minimos:
            h = np.zeros(tamanho)
            h[0] = h[1 + u + i] = 1.0 - pi
            h[1 + i] = 1.0
            h[-1] = fr.volume[i]
            linhas.append(h)
            y.append(float(k.mc[j] - k.b[j]))
            ruido.append(1e4 / k.nc[j])
            tipos.append(True)
        if k.nr[j] >= minimos:
            h = np.zeros(tamanho)
            h[0] = h[1 + u + i] = -pi
            h[1 + i] = 1.0
            h[1 + 2 * u + i] = 1.0 - x
            h[-1] = fr.volume[i]
            linhas.append(h)
            y.append(float(k.mr[j] - k.b[j]))
            ruido.append(1e4 / k.nr[j] + sd_lote**2 * (1.0 - x))
            tipos.append(False)
    if not linhas:
        return None
    return _Linhas(np.array(linhas), np.array(y), np.array(ruido), np.array(tipos))


def _diferenca_observada(k: Contados, v: npt.NDArray[np.intp], minimos: int) -> float:
    """Diferença média entre o voto antecipado e o resto nas unidades que já têm os dois."""
    nc, nr = k.nc[v], k.nr[v]
    ambos = (nc >= minimos) & (nr >= minimos)
    if not ambos.any():
        return 0.0
    peso = nc[ambos] * nr[ambos] / (nc[ambos] + nr[ambos])
    return float(peso @ (k.mc[v][ambos] - k.mr[v][ambos]) / peso.sum())


def condicionar(
    k: Contados,
    k_contado: float,
    pm: ParametrosModos,
    *,
    sd_lote: float,
    sd_volume: float,
    votos_minimos: int,
    limite_robusto: float,
) -> Condicionado:
    """Margem final da corrida dado ``s``, com o voto antecipado e o resto separados.

    A parte antecipada ``π_u`` depende do voto esperado, que se estima com uma participação
    comum a todo o estado; um erro nela desloca todas as unidades no mesmo sentido. Entra
    como mais um latente comum (``κ``, erro relativo do voto esperado), com efeito
    linearizado ``π_u Ĝ`` nas margens, em que ``Ĝ`` é a diferença média já observada
    entre o voto antecipado e o resto.
    """
    total = float(k.e.sum())
    rho_todas = (k.e - k.n) / total
    alfa0 = k_contado + float(rho_todas @ k.b)
    beta0 = float(rho_todas.sum())
    sem_votos = k.n <= 0
    var_sem_votos = float(rho_todas[sem_votos] ** 2 @ k.sd_e[sem_votos] ** 2)

    v = np.flatnonzero(~sem_votos)
    u = len(v)
    resto = k.e[v] - k.nc[v]
    pi = np.clip(k.nc[v] / k.e[v], 0.0, 1.0)
    fr = _Fracoes(
        v=v,
        pi=pi,
        x=np.where(resto > 0, np.clip(k.nr[v] / np.maximum(resto, 1.0), 0.0, 1.0), 1.0),
        volume=np.where(k.estimado[v], pi * _diferenca_observada(k, v, votos_minimos), 0.0),
    )
    # O que falta numa unidade completa (correio tardio, provisórios) não tem modo certo:
    # conta como a margem final da unidade, sem a diferença entre modos.
    rho = rho_todas[v]
    rho_modo = np.where(k.completa[v], 0.0, rho)

    # Latentes: Δ, depois e_u, Δ_u e λ_u de cada unidade com votos. ``f`` dá o peso de
    # cada um na parte da margem final que falta contar.
    var_z = np.concatenate(
        [[pm.sd_diferenca**2], k.sd_e[v] ** 2, np.full(u, pm.sd_diferenca_unidade**2),
         np.full(u, pm.sd_resto**2), [sd_volume**2]]
    )  # fmt: skip
    f = np.concatenate(
        [[-float(rho_modo @ pi)], rho, -rho_modo * pi, -rho_modo * fr.x,
         [float(rho_modo @ fr.volume)]]
    )  # fmt: skip
    var_l = float(f**2 @ var_z) + var_sem_votos

    obs = _linhas(k, fr, sd_lote=sd_lote, minimos=votos_minimos)
    if obs is None:
        return Condicionado(alfa0, beta0, var_l, None, None)

    hm, yv = obs.h, obs.y
    hs = hm * var_z
    propria = np.einsum("ij,ij->i", hs, hm) - hm[:, 0] ** 2 * var_z[0] + obs.ruido
    # Peso robusto: um condado trocado ou um lote mal lançado não arrasta a corrida. A
    # mediana compara-se dentro de cada tipo (antecipado ou resto), porque a diferença
    # comum entre eles é precisamente o que o modelo estima.
    desvio = np.zeros_like(yv)
    for tipo in (obs.antecipado, ~obs.antecipado):
        if tipo.any():
            desvio[tipo] = np.abs(yv[tipo] - np.median(yv[tipo])) / np.sqrt(propria[tipo])
    fator = np.maximum(desvio / limite_robusto, 1.0) ** 2
    s = hs @ hm.T + np.diag(obs.ruido + (fator - 1.0) * propria)

    um = np.ones_like(yv)
    g = hs @ f
    resolvido = np.linalg.solve(s, np.column_stack([g, um]))
    q, w = resolvido[:, 0], resolvido[:, 1]
    informacao = float(um @ w)
    return Condicionado(
        alfa=alfa0 + float(q @ yv),
        beta=beta0 - float(q @ um),
        var_l=max(var_l - float(g @ q), 0.0),
        s_chapeu=float(w @ yv) / informacao,
        var_chapeu=1.0 / informacao,
    )
