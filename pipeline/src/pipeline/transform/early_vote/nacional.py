"""Resumo nacional do voto antecipado a partir dos ficheiros publicados de cada estado.

Lê só os ficheiros já validados (os contratos de cada estado), por isso não refaz cálculos:
cada linha cita números que já estão no ficheiro do estado. A comparação usa o primeiro ano
de referência de cada estado (a intercalar de 2022, quando existe).
"""

from collections.abc import Mapping, Sequence
from datetime import UTC, datetime

from contratos.base import Fonte, Metadados
from contratos.estados import CodigoEstado
from contratos.voto_antecipado import VotoAntecipadoEstado
from contratos.voto_antecipado_agregado import (
    EstadoSemDados,
    LinhaEstadoNacional,
    SinalCondados,
    VotoAntecipadoAgregado,
    VotoAntecipadoNacional,
)

FAIXAS_65_MAIS = ("65-74", "75+")

_BLOQUEADO = (
    "A fonte oficial publica os dados, mas recusa pedidos automáticos. Não contornamos "
    "bloqueios, por isso este estado fica de fora até haver uma via oficial aberta."
)
SEM_DADOS: tuple[EstadoSemDados, ...] = (
    EstadoSemDados(estado=CodigoEstado.GA, motivo="bloqueado", nota=_BLOQUEADO),
    EstadoSemDados(estado=CodigoEstado.TX, motivo="bloqueado", nota=_BLOQUEADO),
    EstadoSemDados(estado=CodigoEstado.MI, motivo="bloqueado", nota=_BLOQUEADO),
    EstadoSemDados(estado=CodigoEstado.OH, motivo="bloqueado", nota=_BLOQUEADO),
    EstadoSemDados(estado=CodigoEstado.NV, motivo="bloqueado", nota=_BLOQUEADO),
    EstadoSemDados(estado=CodigoEstado.AZ, motivo="bloqueado", nota=_BLOQUEADO),
)
"""Estados prioritários sem ficheiro (ver docs/metodologia/voto-antecipado-estados.md).
Um estado que passe a ter ficheiro sai automaticamente desta lista no resumo."""
TOTAL = "total"
CASAS = 6


def _q(parte: float | None, total: float | None) -> float | None:
    if parte is None or not total:
        return None
    return round(parte / total, CASAS)


def _ritmo(votos: int, base: int | None) -> float | None:
    return round(votos / base - 1, CASAS) if base else None


def sinal_condados(
    votos: Mapping[str, int], margens: Mapping[str, float], ano: int
) -> SinalCondados | None:
    """Votos por condado (FIPS) contra a margem presidencial de 2024 (D-R) de cada um.

    Os condados sem margem conhecida ficam de fora. Nenhuma regra distingue os partidos:
    trocar o sinal das margens troca ``votos_trump`` com ``votos_harris`` e o sinal da
    margem ponderada.
    """
    conhecidos = {c: v for c, v in votos.items() if c in margens}
    total = sum(conhecidos.values())
    if not total:
        return None
    return SinalCondados(
        ano=ano,
        votos_trump=sum(v for c, v in conhecidos.items() if margens[c] < 0),
        votos_harris=sum(v for c, v in conhecidos.items() if margens[c] > 0),
        margem_ponderada=round(sum(v * margens[c] for c, v in conhecidos.items()) / total, 4),
    )


def _sinais(
    por_ano: Mapping[int, Mapping[str, int]], margens: Mapping[str, float] | None
) -> tuple[SinalCondados, ...]:
    if not margens:
        return ()
    sinais = (sinal_condados(v, margens, ano) for ano, v in sorted(por_ano.items()))
    return tuple(s for s in sinais if s is not None)


def linha_completo(
    estado: VotoAntecipadoEstado,
    ficheiro: str,
    margens: Mapping[str, float] | None = None,
) -> LinhaEstadoNacional:
    """Estado com ficheiro de eleitores (Carolina do Norte)."""
    d = estado.dias_antes
    base = next((c.ano for c in estado.ciclos[1:] if c.tipo == "intercalar"), None)

    def votos(ano: int, *, faixa: str = TOTAL, partido: str = TOTAL) -> int | None:
        return next(
            (
                p.votos
                for p in estado.serie
                if p.ano == ano
                and p.dias_antes == d
                and p.faixa == faixa
                and p.partido == partido
                and p.modalidade == TOTAL
            ),
            None,
        )

    def mais_velhos(ano: int) -> int | None:
        partes = [votos(ano, faixa=f) for f in FAIXAS_65_MAIS]
        return None if any(p is None for p in partes) else sum(p or 0 for p in partes)

    total = estado.ciclos[0].votos_antecipados
    total_base = votos(base) if base else None
    condados: dict[int, dict[str, int]] = {}
    for g in estado.geografia:
        if g.nivel == "condado" and g.faixa == TOTAL and g.ano in (estado.ano, base):
            condados.setdefault(g.ano, {})[g.codigo] = g.votos
    return LinhaEstadoNacional(
        estado=estado.estado,
        ficheiro=ficheiro,
        granularidade="boletim",
        dados_ate=estado.dados_ate,
        dias_antes=d,
        modalidades=("correio", "presencial"),
        votos=total,
        ano_base=base,
        votos_base=total_base,
        ritmo=_ritmo(total, total_base),
        quota_dem=_q(votos(estado.ano, partido="dem"), total),
        quota_rep=_q(votos(estado.ano, partido="rep"), total),
        quota_dem_base=_q(votos(base, partido="dem"), total_base) if base else None,
        quota_rep_base=_q(votos(base, partido="rep"), total_base) if base else None,
        quota_65_mais=_q(mais_velhos(estado.ano), total),
        quota_65_mais_base=_q(mais_velhos(base), total_base) if base else None,
        condados_presidenciais=_sinais(condados, margens),
    )


def linha_agregado(
    estado: VotoAntecipadoAgregado,
    ficheiro: str,
    margens: Mapping[str, float] | None = None,
) -> LinhaEstadoNacional:
    """Estado só com boletins ou com totais por condado."""
    base_ciclo = next((c for c in estado.ciclos[1:] if c.votos_mesmo_dia is not None), None)
    base = base_ciclo.ano if base_ciclo else None
    linhas = [c for c in estado.comparacao if c.ano_base == base]

    def quota(dimensao: str, categorias: Sequence[str], campo: str) -> float | None:
        escolhidas = [c for c in linhas if c.dimensao == dimensao and c.categoria in categorias]
        if not escolhidas:
            return None
        valores = [getattr(c, campo) for c in escolhidas]
        return None if any(v is None for v in valores) else round(sum(valores), CASAS)

    # Sem ano de referência (Florida), as quotas de 2026 saem da série do último dia.
    total = estado.ciclos[0].votos
    if base is None:
        ultimo = {
            p.partido: p.votos
            for p in estado.serie
            if p.dias_antes == estado.dias_antes and p.faixa == TOTAL and p.modalidade == TOTAL
        }
        quota_dem, quota_rep = _q(ultimo.get("dem"), total), _q(ultimo.get("rep"), total)
    else:
        quota_dem, quota_rep = (
            quota("partido", ["dem"], "quota"),
            quota("partido", ["rep"], "quota"),
        )
    votos_base = base_ciclo.votos_mesmo_dia if base_ciclo else None
    condados: dict[int, dict[str, int]] = {}
    for g in estado.geografia:
        if (
            g.nivel == "condado"
            and g.partido == TOTAL
            and g.faixa == TOTAL
            and g.ano in (estado.ano, base)
        ):
            condados.setdefault(g.ano, {})[g.codigo] = g.votos
    return LinhaEstadoNacional(
        estado=estado.estado,
        ficheiro=ficheiro,
        granularidade=estado.granularidade,
        dados_ate=estado.dados_ate,
        dias_antes=estado.dias_antes,
        modalidades=estado.modalidades,
        votos=total,
        ano_base=base,
        votos_base=votos_base,
        ritmo=_ritmo(total, votos_base),
        quota_dem=quota_dem,
        quota_rep=quota_rep,
        quota_dem_base=quota("partido", ["dem"], "quota_base"),
        quota_rep_base=quota("partido", ["rep"], "quota_base"),
        quota_65_mais=quota("faixa", FAIXAS_65_MAIS, "quota"),
        quota_65_mais_base=quota("faixa", FAIXAS_65_MAIS, "quota_base"),
        condados_presidenciais=_sinais(condados, margens),
    )


def montar(
    linhas: Sequence[LinhaEstadoNacional],
    fontes: Sequence[Fonte],
    *,
    ano: int,
    gerado_em: datetime | None = None,
) -> VotoAntecipadoNacional:
    datas = {linha.dados_ate for linha in linhas}
    avisos = [
        "Soma só dos estados acompanhados; não é um total nacional.",
        "O partido é o de registo do eleitor, não o voto.",
    ]
    if len(datas) > 1:
        avisos.append(
            "Os estados publicam a ritmos diferentes: cada linha tem a sua data e as "
            "comparações são sempre com o mesmo dia do ciclo do próprio estado."
        )
    acompanhados = {linha.estado for linha in linhas}
    return VotoAntecipadoNacional(
        metadados=Metadados(gerado_em=gerado_em or datetime.now(UTC), fontes=tuple(fontes)),
        ano=ano,
        estados=tuple(sorted(linhas, key=lambda x: x.estado.value)),
        votos=sum(linha.votos for linha in linhas),
        avisos=tuple(avisos),
        estados_sem_dados=tuple(e for e in SEM_DADOS if e.estado not in acompanhados),
    )
