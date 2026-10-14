"""Análise de uma corrida durante a contagem: o que os votos contados dizem da margem final.

Cada unidade ``u`` (um condado, ou a corrida inteira quando a fonte só dá o total) tem um
resultado de referência ``b_u`` (a presidencial anterior) e um voto esperado ``E_u``. A
margem final da unidade é ``F_u = b_u + s + e_u``: ``s`` é o desvio da corrida face à
referência (comum a todas as unidades) e ``e_u`` o desvio próprio da unidade. Enquanto a
unidade só tem uma fração ``c_u`` contada, a parte contada e a parte por contar diferem:

    contada:     m_u = F_u + (1 - c_u) * D_u
    por contar:  r_u = F_u - c_u * D_u

``D_u = D + d_u`` é a inclinação do voto contado primeiro (antecipado, correio, dia da
eleição), com uma parte comum à corrida e outra própria da unidade, ambas de média zero:
o modelo não presume que nenhum partido ganha com o voto tardio, mas admite que a
diferença existe e desaparece quando a unidade fica completa. O prior de ``s`` vem da
previsão congelada; ``D``, ``d_u`` e ``e_u`` são normais de média zero.
Como tudo é linear e normal, a margem final condicionada a ``s`` e às contagens é normal
com média ``alfa + beta * s`` e desvio ``gama``, calculados aqui de forma exata.
"""

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field

import numpy as np
import numpy.typing as npt

from pipeline.modelo.noite import modos
from pipeline.modelo.noite.entrada import TOTAL, Base, Contagem, VotosModo

Vetor = npt.NDArray[np.float64]


@dataclass(frozen=True, slots=True)
class Parametros:
    sd_unidade: float = 6.0
    """Desvio de cada condado face ao desvio da corrida (pontos). As presidenciais de
    2016-2024 dão 3 a 5 pontos entre condados do mesmo estado; uma intercalar com
    candidatos diferentes tem mais."""

    sd_inclinacao: float = 25.0
    """Escala da diferença entre o voto contado primeiro e o que falta (pontos, por
    unidade de fração por contar). Em 2022 o voto antecipado e por correspondência ficou
    15 a 45 pontos ao lado do resultado final na Carolina do Norte, na Geórgia e na
    Carolina do Sul, para um lado ou para o outro. Simétrica: a mesma para os dois
    partidos."""

    sd_inclinacao_unidade: float = 15.0
    """Parte da inclinação própria de cada unidade (os condados não votam todos da mesma
    forma por correio). Sem ela, a variação da fração contada entre condados permitiria
    extrapolar a margem final com uma confiança que os dados não justificam."""

    sd_lote: float = 4.0
    """Ruído adicional de uma contagem parcial, proporcional à fração por contar."""

    sd_participacao: float = 0.15
    """Incerteza relativa no volume do voto por contar."""

    participacao_intercalar: float = 0.72
    """Participação esperada face à presidencial de referência num ano intercalar
    (2022/2020: 0,71)."""

    participacao_presidencial: float = 1.0
    peso_participacao: float = 0.25
    """Peso (em fração do voto de referência) do prior da participação face às unidades
    que já dizem quanto falta."""

    residuo_seccoes: float = 0.02
    """Fração que se presume ainda por contar quando todas as secções reportaram mas a
    fonte não diz que a contagem acabou (provisórios, correio tardio)."""

    fracao_maxima: float = 0.9
    """Fração contada máxima de uma unidade sem fração declarada pela fonte."""

    limite_robusto: float = 3.0
    """Desvio (em desvios-padrão) a partir do qual uma unidade pesa menos: um condado
    trocado ou um lote mal lançado na fonte não deve arrastar a corrida inteira."""

    votos_minimos: int = 200
    """Abaixo deste número de votos a unidade não informa o desvio da corrida."""

    fracao_minima: float = 0.02
    sd_minimo_prior: float = 0.3
    """Fração mínima do desvio prior que se mantém no desvio da corrida."""

    ordem: modos.ParametrosModos = field(default_factory=modos.ParametrosModos)
    """Parâmetros do modelo com a ordem de contagem (``modos.py``)."""


@dataclass(frozen=True, slots=True)
class PriorCorrida:
    id: str
    estado: str
    media: float
    """Margem prevista (D-R) na previsão congelada."""

    sd: float

    @property
    def estatal(self) -> bool:
        """Senado e distritos únicos usam a referência de todo o estado."""
        return not self.id[3:].isdigit() or self.id.endswith("-00")


@dataclass(frozen=True, slots=True)
class AnaliseCorrida:
    id: str
    votos_contados: int
    votos_esperados: float | None
    unidades_com_votos: int
    margem_contada: float | None
    s0: float
    """Média prior do desvio da corrida."""

    var_s: float
    s_chapeu: float | None
    """Estimativa do desvio só com as contagens (``None`` se não informam)."""

    var_chapeu: float | None
    alfa: float
    beta: float
    gama: float

    @property
    def fracao_contada(self) -> float | None:
        if self.votos_esperados is None or self.votos_esperados <= 0:
            return None
        return min(1.0, self.votos_contados / self.votos_esperados)


@dataclass(slots=True)
class _Unidades:
    n: Vetor
    m: Vetor
    t: Vetor
    """Votos de referência (NaN sem referência)."""

    b: Vetor
    f: Vetor
    """Fração contada declarada pela fonte (NaN sem ela)."""

    propria: npt.NDArray[np.bool_]
    """A unidade tem referência própria (condado), logo desvio próprio ``e_u``."""

    nc: Vetor
    """Votos antecipados contados (NaN quando a fonte não separa os modos)."""

    mc: Vetor
    nr: Vetor
    """Restantes votos contados (dia da eleição, provisórios e outros)."""

    mr: Vetor
    completa: npt.NDArray[np.bool_]
    """Todas as secções reportaram e a fonte não diz que falta contar."""


def _somar_modos(contagens: Sequence[Contagem]) -> tuple[VotosModo, ...]:
    """Votos por modo de várias partes; vazio se alguma parte com votos não os separa."""
    if any(c.votos > 0 and not c.modos for c in contagens):
        return ()
    somas: dict[str, list[int]] = {}
    for c in contagens:
        for m in c.modos:
            v = somas.setdefault(m.modo, [0, 0, 0])
            v[0] += m.votos_d
            v[1] += m.votos_r
            v[2] += m.votos_outros
    return tuple(VotosModo(k, *v) for k, v in sorted(somas.items()))


def _unidades(
    prior: PriorCorrida,
    contagens: Sequence[Contagem],
    base: Mapping[str, Base],
    p: Parametros,
    parcial: bool = False,
) -> _Unidades:
    referencia = base if prior.estatal else {}
    condados = [c for c in contagens if c.unidade != TOTAL]
    if referencia and any(c.unidade in referencia for c in condados):
        vistas = {c.unidade: c for c in condados}
        linhas: list[tuple[Contagem | None, Base | None]] = [
            (vistas.get(u), b) for u, b in sorted(referencia.items())
        ]
        linhas += [(c, None) for u, c in sorted(vistas.items()) if u not in referencia]
    else:
        totais = [c for c in contagens if c.unidade == TOTAL]
        if totais:
            contagem: Contagem | None = totais[-1]
        elif condados:
            # Partes de condados de um distrito: somam-se votos e secções. Num estado
            # acompanhado só por alguns condados, a soma pode não ser o distrito inteiro:
            # as secções não dizem quanto falta e o distrito fica sem voto esperado.
            seccoes = [(c.seccoes_reportadas, c.seccoes_totais) for c in condados]
            completas = not parcial and all(r is not None and t for r, t in seccoes)
            contagem = Contagem(
                prior.id,
                TOTAL,
                sum(c.votos_d for c in condados),
                sum(c.votos_r for c in condados),
                sum(c.votos_outros for c in condados),
                seccoes_reportadas=sum(r or 0 for r, _ in seccoes) if completas else None,
                seccoes_totais=sum(t or 0 for _, t in seccoes) if completas else None,
                modos=_somar_modos(condados),
            )
        else:
            contagem = None
        agregada: Base | None = None
        if referencia:
            votos = sum(b.votos for b in referencia.values())
            margem = sum(b.votos * b.margem for b in referencia.values()) / votos
            agregada = Base(votos, margem)
        linhas = [(contagem, agregada)]
    vazia = len(linhas) * [math.nan]
    u = _Unidades(
        n=np.zeros(len(linhas)),
        m=np.zeros(len(linhas)),
        t=np.array(vazia),
        b=np.array(vazia),
        f=np.array(vazia),
        propria=np.zeros(len(linhas), dtype=np.bool_),
        nc=np.array(vazia),
        mc=np.zeros(len(linhas)),
        nr=np.array(vazia),
        mr=np.zeros(len(linhas)),
        completa=np.zeros(len(linhas), dtype=np.bool_),
    )
    for i, (c, b) in enumerate(linhas):
        if c is not None and c.votos > 0:
            u.n[i] = c.votos
            u.m[i] = c.margem or 0.0
            u.f[i] = _fracao(c, tem_referencia=b is not None, residuo=p.residuo_seccoes)
            u.completa[i] = (c.fracao_seccoes or 0.0) >= 1.0 and (
                c.fracao_contada is None or c.fracao_contada >= 1.0
            )
            if c.modos:
                antecipados, margem_c = c.votos_modo(cedo=True)
                resto, margem_r = c.votos_modo(cedo=False)
                u.nc[i], u.mc[i] = antecipados, margem_c or 0.0
                u.nr[i], u.mr[i] = resto, margem_r or 0.0
        if b is not None:
            u.t[i] = b.votos
            u.b[i] = b.margem
            u.propria[i] = len(linhas) > 1
    return u


def _fracao(c: Contagem, *, tem_referencia: bool, residuo: float) -> float:
    """Fração contada que se usa para o voto esperado (NaN quando não se sabe).

    A fração de secções só se usa quando a unidade está completa ou quando não há eleição
    de referência: o voto antecipado chega antes das secções e torná-la-ia enviesada.
    """
    if c.fracao_contada is not None and c.fracao_contada > 0:
        return min(c.fracao_contada, 1.0)
    s = c.fracao_seccoes
    if s is not None and (s >= 1.0 or (not tem_referencia and s > 0)):
        return min(s, 1.0 - residuo)
    return math.nan


def _esperados(u: _Unidades, participacao: float, p: Parametros) -> Vetor | None:
    """Voto esperado por unidade; ``None`` quando nada permite estimá-lo."""
    com_t = ~np.isnan(u.t)
    com_f = ~np.isnan(u.f) & (u.f >= p.fracao_minima)
    if not com_t.any() and not com_f.all():
        return None
    total_t = float(u.t[com_t].sum())
    peso = p.peso_participacao * total_t
    ambos = com_t & com_f
    k = (float((u.n[ambos] / u.f[ambos]).sum()) + participacao * peso) / (
        float(u.t[ambos].sum()) + peso
    ) if total_t > 0 else participacao  # fmt: skip
    # Sem fração declarada, uma unidade nunca se dá por completa: se já passou o voto
    # esperado, o esperado é que estava errado.
    e = np.where(com_t, np.maximum(u.n / p.fracao_maxima, k * np.nan_to_num(u.t)), u.n)
    return np.where(com_f, np.maximum(u.n, u.n / np.where(com_f, u.f, 1.0)), e)


@dataclass(frozen=True, slots=True)
class _Observacoes:
    """Unidades com votos suficientes: desvio face à referência e frações."""

    y: Vetor
    a: Vetor
    c: Vetor
    rho: Vetor
    n: Vetor
    sd_e: Vetor


def _condicionar(
    o: _Observacoes, g: float, p: Parametros
) -> tuple[float, float, float, float, float]:
    """Estimativa de ``s`` e o efeito das contagens na margem final dado ``s``.

    Devolve ``s`` estimado, a sua variância, as correções a ``alfa`` e ``beta`` e a
    redução da variância de ``gama``. A inclinação comum entra pela fórmula de
    Sherman-Morrison (covariância diagonal mais uma matriz de característica 1).
    """
    sd_d2 = p.sd_inclinacao_unidade**2
    d = o.sd_e**2 + sd_d2 * o.a**2 + p.sd_lote**2 * o.a + 1e4 / o.n
    desvio = np.abs(o.y - np.median(o.y)) / np.sqrt(d + p.sd_inclinacao**2 * o.a**2)
    d *= np.maximum(desvio / p.limite_robusto, 1.0) ** 2
    d_inv = 1.0 / d
    da = d_inv * o.a
    denominador = 1.0 + p.sd_inclinacao**2 * float(o.a @ da)

    def c_inv(v: Vetor) -> Vetor:
        return d_inv * v - p.sd_inclinacao**2 * da * float(da @ v) / denominador

    um = np.ones_like(o.y)
    informacao = float(um @ c_inv(um))
    cov = o.rho * o.sd_e**2 - g * o.a * p.sd_inclinacao**2 - o.rho * o.c * o.a * sd_d2
    q = c_inv(cov)
    return (
        float(um @ c_inv(o.y)) / informacao,
        1.0 / informacao,
        float(q @ o.y),
        float(q @ um),
        float(cov @ q),
    )


def analisar(
    prior: PriorCorrida,
    contagens: Sequence[Contagem],
    base: Mapping[str, Base],
    participacao: float,
    p: Parametros,
    *,
    parcial: bool = False,
) -> AnaliseCorrida:
    """Distribuição da margem final condicionada ao desvio ``s`` e às contagens.

    ``parcial``: o estado só é acompanhado em alguns condados. Numa corrida estadual, os
    condados sem dados ficam no voto esperado (previstos pelo desvio da corrida) e a
    corrida nunca se dá por completa; num distrito, as partes de condados não dizem
    quanto falta e o distrito só aprende pelos fatores comuns.
    """
    u = _unidades(prior, contagens, base, p, parcial)
    contados = int(u.n.sum())
    margem_contada = float(u.n @ u.m / contados) if contados > 0 else None
    com_votos = int((u.n > 0).sum())
    var_prior = prior.sd**2
    e = _esperados(u, participacao, p)
    if e is None or e.sum() <= 0:
        return AnaliseCorrida(
            prior.id, contados, None, com_votos, margem_contada,
            0.0, var_prior, None, None, prior.media, 1.0, 0.0,
        )  # fmt: skip

    total = float(e.sum())
    w = e / total
    c = np.divide(u.n, e, out=np.zeros_like(e), where=e > 0)
    a = 1.0 - c
    rho = (e - u.n) / total
    com_b = ~np.isnan(u.b)
    if com_b.any():
        agregada = float(np.nansum(u.t * u.b) / np.nansum(np.where(com_b, u.t, 0.0)))
    else:
        agregada = prior.media
    b = np.where(com_b, u.b, agregada)
    sd_e = np.where(u.propria, p.sd_unidade, 0.0)
    s0 = prior.media - float(w @ b)
    var_s = max(var_prior - float(w**2 @ sd_e**2), (p.sd_minimo_prior * prior.sd) ** 2)

    k_contado = float(u.n @ u.m) / total
    if modos.elegivel(prior.estado, u.n, u.nc, u.nr, u.propria):
        contados_modo = modos.Contados(
            n=u.n, nc=u.nc, mc=u.mc, nr=u.nr, mr=u.mr, e=e, b=b, sd_e=sd_e,
            estimado=np.isnan(u.f) | (u.f < p.fracao_minima), completa=u.completa,
        )  # fmt: skip
        r = modos.condicionar(
            contados_modo, k_contado, p.ordem, sd_lote=p.sd_lote, sd_volume=p.sd_participacao,
            votos_minimos=p.votos_minimos, limite_robusto=p.limite_robusto,
        )  # fmt: skip
        return _com_volume(prior, u, r, k_contado=k_contado, e=e, s0=s0, var_s=var_s, p=p)
    g = float(rho @ c)
    sd_d2 = p.sd_inclinacao_unidade**2
    var_l = (
        float(rho**2 @ sd_e**2) + g**2 * p.sd_inclinacao**2 + sd_d2 * float((rho * c) @ (rho * c))
    )
    alfa = k_contado + float(rho @ b)
    beta = float(rho.sum())
    s_chapeu: float | None = None
    var_chapeu: float | None = None
    obs = u.n >= p.votos_minimos
    if obs.any():
        o = _Observacoes(y=u.m[obs] - b[obs], a=a[obs], c=c[obs], rho=rho[obs], n=u.n[obs],
                         sd_e=sd_e[obs])  # fmt: skip
        s_chapeu, var_chapeu, correcao_alfa, correcao_beta, reducao = _condicionar(o, g, p)
        alfa += correcao_alfa
        beta -= correcao_beta
        var_l = max(var_l - reducao, 0.0)
    r = modos.Condicionado(alfa, beta, var_l, s_chapeu, var_chapeu)
    return _com_volume(prior, u, r, k_contado=k_contado, e=e, s0=s0, var_s=var_s, p=p)


def _com_volume(
    prior: PriorCorrida,
    u: _Unidades,
    r: modos.Condicionado,
    *,
    k_contado: float,
    e: Vetor,
    s0: float,
    var_s: float,
    p: Parametros,
) -> AnaliseCorrida:
    """Junta à variância a incerteza no volume do que falta e monta a análise."""
    alfa, beta, var_l = r.alfa, r.beta, r.var_l
    s_chapeu, var_chapeu = r.s_chapeu, r.var_chapeu
    total = float(e.sum())
    rho = (e - u.n) / total
    contados = int(u.n.sum())
    margem_contada = float(u.n @ u.m / contados) if contados > 0 else None
    # Incerteza no volume do que falta: só pesa quando o que falta vota diferente do
    # que já foi contado, e desaparece no início e no fim da contagem.
    falta = float(rho.sum())
    if 0.0 < falta < 1.0:
        s_ref = s0
        if s_chapeu is not None and var_chapeu is not None:
            s_ref = (s0 / var_s + s_chapeu / var_chapeu) / (1 / var_s + 1 / var_chapeu)
        restante = (alfa + beta * s_ref - k_contado) / falta
        contado = k_contado / (1.0 - falta)
        var_l += (p.sd_participacao * falta * (1.0 - falta) * (restante - contado)) ** 2

    return AnaliseCorrida(
        prior.id, contados, total, int((u.n > 0).sum()), margem_contada,
        s0, var_s, s_chapeu, var_chapeu, alfa, beta, math.sqrt(var_l),
    )  # fmt: skip
