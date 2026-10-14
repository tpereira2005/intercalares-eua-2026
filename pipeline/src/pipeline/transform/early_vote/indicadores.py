"""Indicadores do voto antecipado calculados sobre cubos de contagens.

Todas as funções recebem cubos (ver :mod:`pipeline.transform.early_vote.cubos`) e um dia do
ciclo ``d`` em dias antes da eleição. "Votou até ``d``" significa ter um boletim devolvido
ou um voto presencial registado a ``d`` ou mais dias da eleição, o que permite comparar
2026 com os anos anteriores exatamente na mesma altura do ciclo.

Nenhuma função distingue partidos: os partidos são valores de uma coluna como outra
qualquer, e o teste de troca de rótulos garante que trocar ``dem`` por ``rep`` nos dados
troca os resultados e nada mais.
"""

from collections.abc import Sequence

import numpy as np
import polars as pl

from pipeline.comum.categorias import GrupoHistorico, Modalidade
from pipeline.comum.faixas_etarias import CANONICA_PARA_LARGA

TOTAL = "total"
"""Rótulo das linhas que somam todas as categorias de uma dimensão."""


def votou_ate(d: int) -> pl.Expr:
    return (pl.col("modalidade") != str(Modalidade.NAO_VOTOU)) & (pl.col("dias_antes") >= d)


def contagens(cubo: pl.DataFrame, d: int, por: Sequence[str]) -> pl.DataFrame:
    """Votos até ``d`` e recenseados por combinação de ``por``."""
    return (
        cubo.group_by(list(por))
        .agg(
            pl.col("n").sum().cast(pl.Int64).alias("registados"),
            pl.col("n").filter(votou_ate(d)).sum().cast(pl.Int64).alias("votos"),
        )
        .sort(list(por))
    )


def com_total(tabela: pl.DataFrame, coluna: str, somar: Sequence[str]) -> pl.DataFrame:
    """Acrescenta linhas ``coluna = "total"`` com a soma de ``somar`` sobre ``coluna``."""
    chaves = [c for c in tabela.columns if c not in (coluna, *somar)]
    total = (
        tabela.group_by(chaves).agg([pl.col(c).sum() for c in somar])
        if chaves
        else (tabela.select([pl.col(c).sum() for c in somar]))
    )
    total = total.with_columns(pl.lit(TOTAL).alias(coluna)).select(tabela.columns)
    return pl.concat([tabela, total.cast(tabela.schema)], how="vertical")


def serie(cubo: pl.DataFrame, por: Sequence[str], dias: Sequence[int]) -> pl.DataFrame:
    """Votos acumulados por dia do ciclo, para cada combinação de ``por``.

    ``dias`` é a lista de dias antes da eleição a devolver. Os votos anteriores ao primeiro
    dia pedido entram no primeiro ponto, para que a série comece no total acumulado.
    """
    if not dias:
        msg = "É preciso pelo menos um dia"
        raise ValueError(msg)
    d_max, d_min = max(dias), min(dias)
    chaves = list(por)
    registados = cubo.group_by(chaves).agg(pl.col("n").sum().cast(pl.Int64).alias("registados"))
    por_dia = (
        cubo.filter(votou_ate(d_min))
        .with_columns(pl.col("dias_antes").clip(upper_bound=d_max))
        .group_by([*chaves, "dias_antes"])
        .agg(pl.col("n").sum().cast(pl.Int64).alias("novos"))
    )
    grelha = registados.select(chaves).join(
        pl.DataFrame({"dias_antes": pl.Series(sorted(set(dias), reverse=True), dtype=pl.Int16)}),
        how="cross",
    )
    todos = pl.DataFrame({"dias_antes": pl.Series(range(d_max, d_min - 1, -1), dtype=pl.Int16)})
    completa = (
        registados.select(chaves)
        .join(todos, how="cross")
        .join(por_dia, on=[*chaves, "dias_antes"], how="left")
        .with_columns(pl.col("novos").fill_null(0))
        .sort([*chaves, "dias_antes"], descending=[False] * len(chaves) + [True])
        .with_columns(pl.col("novos").cum_sum().over(chaves).alias("votos"))
        .drop("novos")
    )
    return (
        grelha.join(completa, on=[*chaves, "dias_antes"], how="left")
        .join(registados, on=chaves, how="left")
        .sort([*chaves, "dias_antes"], descending=[False] * len(chaves) + [True])
    )


def _quota(valores: np.ndarray) -> np.ndarray:
    total = valores.sum()
    return valores / total if total > 0 else np.zeros_like(valores)


def _quota_votos(r: np.ndarray, t: np.ndarray) -> np.ndarray:
    return _quota(r * t)


def decomposicao_shapley(
    r_base: np.ndarray, t_base: np.ndarray, r_atual: np.ndarray, t_atual: np.ndarray
) -> tuple[np.ndarray, np.ndarray]:
    """Divide a variação da quota de cada grupo no voto em dois efeitos que somam exatamente.

    A quota do grupo g é ``s_g = r_g t_g / Σ r_h t_h``, com ``r`` a quota no recenseamento e
    ``t`` a taxa de participação até ao dia ``d``. O efeito do recenseamento é quanto a quota
    mudaria só por mudar ``r``; o efeito da participação, só por mudar ``t``. A média das
    duas ordens possíveis (valor de Shapley) torna a divisão exata e independente da ordem.
    """
    s = _quota_votos
    efeito_r = 0.5 * (
        (s(r_atual, t_base) - s(r_base, t_base)) + (s(r_atual, t_atual) - s(r_base, t_atual))
    )
    efeito_t = 0.5 * (
        (s(r_base, t_atual) - s(r_base, t_base)) + (s(r_atual, t_atual) - s(r_atual, t_base))
    )
    return efeito_r, efeito_t


def _taxa(votos: pl.Expr, registados: pl.Expr) -> pl.Expr:
    return pl.when(registados > 0).then(votos / registados).otherwise(None)


JANELA_CALENDARIO = 3
"""Dias para cada lado do mesmo dia do ciclo no intervalo do desvio."""


def comparacao(atual: pl.DataFrame, base: pl.DataFrame, d: int, por: str = "faixa") -> pl.DataFrame:
    """Compara 2026 com um ano de referência no mesmo dia ``d``, por categoria de ``por``.

    Colunas: votos, registados, quota (no voto), quota_recenseamento, taxa, as mesmas com
    o sufixo ``_base``, ``esperado`` (recenseados de hoje x taxa da base no mesmo dia),
    ``desvio`` (votos / esperado - 1), ``desvio_min`` e ``desvio_max`` (ver
    ``intervalo_desvio``) e os dois efeitos da decomposição da quota.
    """
    a = contagens(atual, d, [por])
    b = contagens(base, d, [por]).rename({"votos": "votos_base", "registados": "registados_base"})
    t = (
        a.join(b, on=por, how="full", coalesce=True)
        .with_columns(pl.col(pl.Int64).fill_null(0))
        .sort(por)
    )
    t = (
        t.with_columns(
            (pl.col("votos") / pl.col("votos").sum()).alias("quota"),
            (pl.col("votos_base") / pl.col("votos_base").sum()).alias("quota_base"),
            (pl.col("registados") / pl.col("registados").sum()).alias("quota_recenseamento"),
            (pl.col("registados_base") / pl.col("registados_base").sum()).alias(
                "quota_recenseamento_base"
            ),
            _taxa(pl.col("votos"), pl.col("registados")).alias("taxa"),
            _taxa(pl.col("votos_base"), pl.col("registados_base")).alias("taxa_base"),
        )
        .with_columns(
            (pl.col("registados") * pl.col("taxa_base").fill_null(0)).alias("esperado"),
        )
        .with_columns(
            pl.when(pl.col("esperado") > 0)
            .then(pl.col("votos") / pl.col("esperado") - 1)
            .otherwise(None)
            .alias("desvio"),
        )
    )
    efeito_r, efeito_t = decomposicao_shapley(
        t["quota_recenseamento_base"].fill_nan(0).to_numpy(),
        t["taxa_base"].fill_null(0).to_numpy(),
        t["quota_recenseamento"].fill_nan(0).to_numpy(),
        t["taxa"].fill_null(0).to_numpy(),
    )
    return t.with_columns(
        pl.Series("efeito_recenseamento", efeito_r),
        pl.Series("efeito_participacao", efeito_t),
    ).join(intervalo_desvio(atual, base, d, por), on=por, how="left")


def intervalo_desvio(
    atual: pl.DataFrame, base: pl.DataFrame, d: int, por: str = "faixa"
) -> pl.DataFrame:
    """Menor e maior desvio quando a taxa de referência se lê até ``JANELA_CALENDARIO``
    dias antes ou depois do mesmo dia do ciclo.

    Mede a sensibilidade ao alinhamento do calendário (feriados, dias de abertura dos
    locais de voto, atrasos no registo dos boletins), não o erro de amostragem, que é
    desprezável com estas contagens. O intervalo inclui sempre o desvio do mesmo dia.
    """
    a = contagens(atual, d, [por]).select(por, "votos", "registados")
    desvios = []
    for dia in range(max(0, d - JANELA_CALENDARIO), d + JANELA_CALENDARIO + 1):
        b = contagens(base, dia, [por]).select(
            por, _taxa(pl.col("votos"), pl.col("registados")).alias("taxa_base")
        )
        esperado = pl.col("registados") * pl.col("taxa_base")
        desvios.append(
            a.join(b, on=por, how="left").select(
                por,
                pl.when(esperado > 0)
                .then(pl.col("votos") / esperado - 1)
                .otherwise(None)
                .alias("desvio_dia"),
            )
        )
    return (
        pl.concat(desvios)
        .group_by(por)
        .agg(
            pl.col("desvio_dia").min().alias("desvio_min"),
            pl.col("desvio_dia").max().alias("desvio_max"),
        )
    )


GRUPOS_HABITUAIS = (
    str(GrupoHistorico.ANTECIPADO_NA_REFERENCIA),
    str(GrupoHistorico.DIA_ELEICAO_NA_REFERENCIA),
)
"""Eleitores que votaram na eleição de referência, por qualquer método."""


def decomposicao_historico(cubo: pl.DataFrame, d: int, por: str = "faixa") -> pl.DataFrame:
    """Contributo de cada grupo histórico para a taxa de participação até ``d``.

    ``contributo`` = votos do grupo / recenseados da categoria. A soma dos contributos dos
    grupos é a taxa de participação da categoria, por isso a variação da taxa entre dois anos
    divide-se exatamente entre antecipação, voto habitual e voto novo.
    """
    registados = cubo.group_by(por).agg(pl.col("n").sum().cast(pl.Int64).alias("registados"))
    votos = (
        cubo.filter(votou_ate(d))
        .group_by([por, "grupo"])
        .agg(pl.col("n").sum().cast(pl.Int64).alias("votos"))
    )
    grupos = cubo.select("grupo").unique()
    return (
        registados.join(grupos, how="cross")
        .join(votos, on=[por, "grupo"], how="left")
        .with_columns(pl.col("votos").fill_null(0))
        .with_columns(_taxa(pl.col("votos"), pl.col("registados")).alias("contributo"))
        .sort([por, "grupo"])
    )


def reserva(cubo: pl.DataFrame, d: int, por: Sequence[str] = ("faixa", "partido")) -> pl.DataFrame:
    """Eleitores habituais (votaram na eleição de referência) que ainda não votaram até ``d``.

    Comparar a fração restante com a do mesmo dia do ciclo anterior diz quanta base de cada
    grupo já foi mobilizada e quanta falta, que é o que a liderança no voto não diz.
    """
    habituais = cubo.filter(pl.col("grupo").is_in(GRUPOS_HABITUAIS))
    return (
        habituais.group_by(list(por))
        .agg(
            pl.col("n").sum().cast(pl.Int64).alias("habituais"),
            pl.col("n").filter(votou_ate(d)).sum().cast(pl.Int64).alias("ja_votaram"),
        )
        .with_columns((pl.col("habituais") - pl.col("ja_votaram")).alias("restantes"))
        .sort(list(por))
    )


def geografia(cubo_geo: pl.DataFrame, d: int, nivel: str) -> pl.DataFrame:
    """Votos e recenseados por unidade geográfica (``fips_condado`` ou ``distrito_atual``)
    e por faixa larga, mais a linha ``total`` de cada unidade."""
    larga = cubo_geo.with_columns(
        pl.col("faixa").replace_strict(CANONICA_PARA_LARGA, default=None).alias("faixa")
    )
    t = contagens(larga, d, [nivel, "faixa"])
    return com_total(t, "faixa", ("registados", "votos")).sort([nivel, "faixa"], nulls_last=True)


def historico_geografia(cubo_geo: pl.DataFrame, d: int, nivel: str) -> pl.DataFrame:
    """Contributo de cada grupo histórico por unidade geográfica e faixa larga até ``d``,
    com a linha ``total`` de cada unidade (como ``decomposicao_historico``, por lugar)."""
    larga = cubo_geo.drop_nulls(nivel).with_columns(
        pl.col("faixa").replace_strict(CANONICA_PARA_LARGA, default=None).alias("faixa")
    )
    larga = pl.concat([larga, larga.with_columns(pl.lit(TOTAL).alias("faixa"))])
    por = [nivel, "faixa"]
    registados = larga.group_by(por).agg(pl.col("n").sum().cast(pl.Int64).alias("registados"))
    votos = (
        larga.filter(votou_ate(d))
        .group_by([*por, "grupo"])
        .agg(pl.col("n").sum().cast(pl.Int64).alias("votos"))
    )
    grupos = larga.select("grupo").unique()
    return (
        registados.join(grupos, how="cross")
        .join(votos, on=[*por, "grupo"], how="left")
        .with_columns(pl.col("votos").fill_null(0))
        .with_columns(_taxa(pl.col("votos"), pl.col("registados")).alias("contributo"))
        .sort([*por, "grupo"], nulls_last=True)
    )


def cruzamento(cubo: pl.DataFrame, d: int, dimensao: str) -> pl.DataFrame:
    """Votos e recenseados por faixa x ``dimensao``.

    Para a modalidade, os recenseados não se dividem por modalidade: o denominador é o total
    da faixa, para que as taxas de correio e presencial somem a taxa total.
    """
    if dimensao == "modalidade":
        registados = cubo.group_by("faixa").agg(
            pl.col("n").sum().cast(pl.Int64).alias("registados")
        )
        votos = (
            cubo.filter(votou_ate(d))
            .group_by(["faixa", "modalidade"])
            .agg(pl.col("n").sum().cast(pl.Int64).alias("votos"))
        )
        modos = pl.DataFrame({"modalidade": [str(Modalidade.CORREIO), str(Modalidade.PRESENCIAL)]})
        return (
            registados.join(modos, how="cross")
            .join(votos, on=["faixa", "modalidade"], how="left")
            .with_columns(pl.col("votos").fill_null(0))
            .select("faixa", pl.col("modalidade").alias("categoria"), "votos", "registados")
            .sort(["faixa", "categoria"])
        )
    return contagens(cubo, d, ["faixa", dimensao]).rename({dimensao: "categoria"})
