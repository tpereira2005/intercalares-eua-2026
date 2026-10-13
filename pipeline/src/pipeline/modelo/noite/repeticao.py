"""Repetição de noites passadas para testar o Modelo C.

As fontes oficiais só guardam o resultado final. O ensaio da recolha de resultados
(``pipeline.jobs.ensaio_resultados``) reconstrói a noite revelando condados inteiros por
ordem aleatória; aqui acrescenta-se uma segunda reconstrução, mais exigente para o
modelo, que usa os votos reais por modo de cada condado: primeiro o voto antecipado e por
correspondência, depois o dia da eleição aos poucos e, no fim, os provisórios. Assim cada
condado passa por estados parciais com a inclinação real do voto contado primeiro, que é
o que o modelo tem de tratar com honestidade. As duas são reconstruções, não a sequência
real da noite, e são marcadas como tal (``reconstruido``).
"""

import random
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import timedelta

from contratos.resultados import ContagemModo, ResultadosParciais, UnidadeContagem

CEDO = frozenset({"antecipado_presencial", "correio"})
TARDE = frozenset({"provisorio", "outro"})
INTERVALO = timedelta(minutes=20)


def _soma(modos: Iterable[ContagemModo], fator: float = 1.0) -> tuple[int, int, int]:
    d = r = o = 0
    for m in modos:
        d += int(m.votos_d * fator)
        r += int(m.votos_r * fator)
        o += int(m.votos_outros * fator)
    return d, r, o


def _unidade(u: UnidadeContagem, t: float, chegada: float) -> UnidadeContagem:
    """A unidade no instante ``t`` (entre 0 e 1), se chegou em ``chegada``."""
    if t >= 1.0:
        return u
    if t < chegada:
        return u.model_copy(
            update={"votos_d": 0, "votos_r": 0, "votos_outros": 0, "por_modo": (),
                    "seccoes_reportadas": 0 if u.seccoes_totais is not None else None}
        )  # fmt: skip
    if not u.por_modo:
        return u  # sem votos por modo, chega inteira
    fracao_dia = min(1.0, (t - chegada) / 0.3)
    modos: list[ContagemModo] = []
    for m in u.por_modo:
        if m.modo in CEDO:
            modos.append(m)
        elif m.modo == "dia_eleicao":
            d, r, o = _soma([m], fracao_dia)
            modos.append(ContagemModo(modo=m.modo, votos_d=d, votos_r=r, votos_outros=o))
    d, r, o = _soma(modos)
    seccoes = u.seccoes_reportadas
    if u.seccoes_totais is not None:
        seccoes = int(u.seccoes_totais * fracao_dia)
    return u.model_copy(
        update={"votos_d": d, "votos_r": r, "votos_outros": o, "por_modo": tuple(modos),
                "seccoes_reportadas": seccoes}
    )  # fmt: skip


def por_modos(final: ResultadosParciais, passos: int, semente: int = 0) -> list[ResultadosParciais]:
    """``passos`` instantes do resultado final, o último igual ao final."""
    gerador = random.Random(semente)  # noqa: S311 (ordem de ensaio, não criptografia)
    chegadas = {
        u.unidade: gerador.uniform(0.0, 0.6)
        for u in sorted(final.unidades, key=lambda u: u.unidade)
    }
    instantes: list[ResultadosParciais] = []
    for i in range(1, passos + 1):
        t = i / passos
        instantes.append(
            final.model_copy(
                update={
                    "instante": final.instante - (passos - i) * INTERVALO,
                    "reconstruido": True,
                    "unidades": tuple(_unidade(u, t, chegadas[u.unidade]) for u in final.unidades),
                }
            )
        )
    return instantes


@dataclass(frozen=True, slots=True)
class Final:
    margem: float
    vencedor: str


def finais(final: ResultadosParciais) -> dict[str, Final]:
    """Margem e vencedor de cada corrida no resultado final (lados D e R)."""
    somas: dict[str, list[int]] = {}
    for u in final.unidades:
        s = somas.setdefault(u.corrida, [0, 0, 0])
        s[0] += u.votos_d
        s[1] += u.votos_r
        s[2] += u.votos_outros
    return {
        c: Final(100.0 * (d - r) / (d + r + o), "D" if d > r else "R")
        for c, (d, r, o) in somas.items()
        if d + r + o > 0 and d != r
    }


def juntar(instantes: Sequence[ResultadosParciais]) -> ResultadosParciais:
    """Junta instantes de vários estados num só (o mesmo passo de cada estado)."""
    primeiro = instantes[0]
    return primeiro.model_copy(
        update={
            "instante": max(i.instante for i in instantes),
            "unidades": tuple(u for i in instantes for u in i.unidades),
        }
    )
