"""Voto antecipado nos estados com boletins mas sem recenseados por grupo.

Cada conector produz uma tabela com **um boletim por linha**, já normalizada e sem
identificadores:

* ``idade`` (Int16, idade no fim do ano da eleição; nula quando a fonte não a tem);
* ``partido`` e ``modalidade`` (valores de :mod:`pipeline.comum.categorias`);
* ``fips_condado`` (texto, cinco dígitos) e ``distrito`` (Int8, mapa de 2026), ou nulos;
* ``data_pedido`` e ``data_devolucao`` (Date; ``data_devolucao`` nula se não foi devolvido).

Daqui saem dois cubos de contagens (votos por dia de devolução e pedidos por dia de pedido
e de devolução) e os indicadores, que comparam votos com votos no mesmo dia do ciclo.
Como na Carolina do Norte, nenhuma regra distingue partidos.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import Any

import polars as pl

from contratos.base import Fonte, Metadados
from contratos.estados import CodigoEstado
from contratos.voto_antecipado_agregado import (
    CicloAgregado,
    Granularidade,
    LinhaComparacaoAgregada,
    LinhaGeografiaAgregada,
    LinhaPedidos,
    PontoSerieAgregado,
    VotoAntecipadoAgregado,
)
from pipeline.comum.calendario import EleicaoGeral
from pipeline.comum.faixas_etarias import CANONICA, CANONICA_PARA_LARGA
from pipeline.transform.early_vote.indicadores import TOTAL, com_total
from pipeline.transform.early_vote.painel import DIAS_ANTES_MAXIMO, DIAS_ANTES_MINIMO
from pipeline.transform.early_vote.relatorio import CASAS_DECIMAIS, INICIO_SERIE, LIMIAR_POPULACAO

COLUNAS_BOLETINS = (
    "idade",
    "partido",
    "modalidade",
    "fips_condado",
    "distrito",
    "data_pedido",
    "data_devolucao",
)
DIMENSOES_VOTOS = ("faixa", "partido", "modalidade", "fips_condado", "distrito", "dias_antes")
DIMENSOES_PEDIDOS = ("faixa", "partido", "dias_pedido", "dias_antes")


@dataclass(frozen=True, slots=True)
class CubosAgregados:
    eleicao: EleicaoGeral
    votos: pl.DataFrame
    pedidos: pl.DataFrame


def _dias(eleicao: EleicaoGeral, coluna: str) -> pl.Expr:
    return (
        (pl.lit(eleicao.data) - pl.col(coluna))
        .dt.total_days()
        .clip(DIAS_ANTES_MINIMO, DIAS_ANTES_MAXIMO)
        .cast(pl.Int16)
    )


def cubos(boletins: pl.DataFrame, eleicao: EleicaoGeral) -> CubosAgregados:
    """Agrega os boletins de uma eleição nos dois cubos de contagens."""
    em_falta = [c for c in COLUNAS_BOLETINS if c not in boletins.columns]
    if em_falta:
        msg = f"Faltam colunas nos boletins: {', '.join(em_falta)}"
        raise ValueError(msg)
    base = boletins.with_columns(
        CANONICA.expressao("idade", "faixa"),
        _dias(eleicao, "data_devolucao").alias("dias_antes"),
        # Sem data de pedido (alguns registos antigos), conta como pedido desde o início.
        _dias(eleicao, "data_pedido").fill_null(DIAS_ANTES_MAXIMO).alias("dias_pedido"),
    )
    votos = (
        base.filter(pl.col("dias_antes").is_not_null())
        .group_by(list(DIMENSOES_VOTOS))
        .agg(pl.len().cast(pl.Int64).alias("n"))
        .sort(list(DIMENSOES_VOTOS), nulls_last=True)
    )
    pedidos = (
        base.group_by(list(DIMENSOES_PEDIDOS))
        .agg(pl.len().cast(pl.Int64).alias("n"))
        .sort(list(DIMENSOES_PEDIDOS), nulls_last=True)
    )
    return CubosAgregados(eleicao, votos, pedidos)


def cubos_de_retratos(retratos: pl.DataFrame, eleicao: EleicaoGeral) -> CubosAgregados:
    """Cubos a partir de totais acumulados publicados pela fonte (estados sem um registo
    por boletim, como o Iowa).

    ``retratos`` tem ``dados_ate``, ``distrito`` (Int8), ``partido``, ``tipo`` e ``n``, com
    ``tipo`` em ``correio``, ``presencial`` (votos recebidos) e ``pedidos``. Cada dia com
    relatório recebe a diferença face ao relatório anterior, por isso a soma até um dia do
    ciclo reproduz o acumulado publicado nesse dia (ou no último dia com relatório). Uma
    diferença pode ser negativa quando a fonte corrige números: fica, para os acumulados
    baterem certo com a fonte. Os relatórios posteriores à eleição não entram.
    """
    base = retratos.filter(pl.col("dados_ate") <= eleicao.data).with_columns(
        _dias(eleicao, "dados_ate").alias("dias_antes")
    )

    def incrementos(tabela: pl.DataFrame, chaves: list[str]) -> pl.DataFrame:
        return tabela.sort("dados_ate").with_columns(
            (pl.col("n") - pl.col("n").shift(1).over(chaves).fill_null(0)).alias("n")
        )

    votos = (
        incrementos(
            base.filter(pl.col("tipo").is_in(["correio", "presencial"])),
            ["distrito", "partido", "tipo"],
        )
        .select(
            pl.lit("desconhecida").alias("faixa"),
            "partido",
            pl.col("tipo").alias("modalidade"),
            pl.lit(None, pl.String).alias("fips_condado"),
            pl.col("distrito").cast(pl.Int8),
            "dias_antes",
            pl.col("n").cast(pl.Int64),
        )
        .group_by(list(DIMENSOES_VOTOS))
        .agg(pl.col("n").sum())
        .sort(list(DIMENSOES_VOTOS), nulls_last=True)
    )
    # Pedidos: cada dia, os recebidos novos (devolvidos nesse dia) e o resto dos pedidos
    # novos (por devolver). Assim, até cada dia, pedidos e devolvidos batem com a fonte.
    por_dia = base.group_by("dados_ate", "dias_antes", "partido").agg(
        pl.col("n").filter(pl.col("tipo") == "pedidos").sum().alias("pedidos"),
        pl.col("n").filter(pl.col("tipo").is_in(["correio", "presencial"])).sum().alias("votos"),
    )
    por_dia = por_dia.sort("dados_ate").with_columns(
        (pl.col(c) - pl.col(c).shift(1).over("partido").fill_null(0)).alias(c)
        for c in ("pedidos", "votos")
    )
    devolvidos = por_dia.select(
        "partido",
        pl.col("dias_antes").alias("dias_pedido"),
        "dias_antes",
        pl.col("votos").alias("n"),
    )
    por_devolver = por_dia.select(
        "partido",
        pl.col("dias_antes").alias("dias_pedido"),
        pl.lit(None, pl.Int16).alias("dias_antes"),
        (pl.col("pedidos") - pl.col("votos")).alias("n"),
    )
    pedidos_ = (
        pl.concat([devolvidos, por_devolver])
        .with_columns(pl.lit("desconhecida").alias("faixa"), pl.col("n").cast(pl.Int64))
        .group_by(list(DIMENSOES_PEDIDOS))
        .agg(pl.col("n").sum())
        .sort(list(DIMENSOES_PEDIDOS), nulls_last=True)
    )
    return CubosAgregados(eleicao, votos, pedidos_)


def _ate(cubo: pl.DataFrame, d: int) -> pl.DataFrame:
    return cubo.filter(pl.col("dias_antes") >= d)


def total_votos(cubo: pl.DataFrame, d: int) -> int:
    return int(_ate(cubo, d)["n"].sum())


def total_pedidos(cubo: pl.DataFrame, d: int) -> int:
    return int(cubo.filter(pl.col("dias_pedido") >= d)["n"].sum())


def serie(cubo: pl.DataFrame, dias: Sequence[int]) -> pl.DataFrame:
    """Votos acumulados por dia, por faixa e partido (todas as modalidades) e por faixa e
    modalidade (todos os partidos), com as linhas ``total``."""
    partes = []
    for d in dias:
        ate = _ate(cubo, d)
        por_partido = ate.group_by("faixa", "partido").agg(pl.col("n").sum().alias("votos"))
        por_partido = com_total(com_total(por_partido, "partido", ("votos",)), "faixa", ("votos",))
        partes.append(
            por_partido.with_columns(
                pl.lit(TOTAL).alias("modalidade"), pl.lit(d, pl.Int16).alias("dias_antes")
            )
        )
        por_modo = ate.group_by("faixa", "modalidade").agg(pl.col("n").sum().alias("votos"))
        por_modo = com_total(por_modo, "faixa", ("votos",))
        partes.append(
            por_modo.with_columns(
                pl.lit(TOTAL).alias("partido"), pl.lit(d, pl.Int16).alias("dias_antes")
            )
        )
    colunas = ["dias_antes", "faixa", "partido", "modalidade", "votos"]
    return pl.concat([p.select(colunas) for p in partes]).sort(colunas[:-1])


def _quota(votos: pl.Expr, total: pl.Expr) -> pl.Expr:
    return pl.when(total > 0).then(votos / total).otherwise(None)


def comparacao(
    atual: pl.DataFrame, base: pl.DataFrame, d: int, dimensoes: Sequence[str]
) -> pl.DataFrame:
    """Para cada dimensão, votos e quota de cada categoria em 2026 e no ano de referência."""
    linhas = []
    for dim in dimensoes:
        a = _ate(atual, d).group_by(dim).agg(pl.col("n").sum().alias("votos"))
        b = _ate(base, d).group_by(dim).agg(pl.col("n").sum().alias("votos_base"))
        juntos = (
            a.join(b, on=dim, how="full", coalesce=True)
            .with_columns(pl.col("votos", "votos_base").fill_null(0))
            .rename({dim: "categoria"})
            .with_columns(pl.col("categoria").cast(pl.String))
        )
        juntos = com_total(juntos, "categoria", ("votos", "votos_base"))
        total_a = juntos.filter(pl.col("categoria") == TOTAL)["votos"].sum()
        total_b = juntos.filter(pl.col("categoria") == TOTAL)["votos_base"].sum()
        linhas.append(
            juntos.with_columns(
                pl.lit(dim).alias("dimensao"),
                _quota(pl.col("votos"), pl.lit(total_a)).alias("quota"),
                _quota(pl.col("votos_base"), pl.lit(total_b)).alias("quota_base"),
                pl.when(pl.col("votos_base") > 0)
                .then(pl.col("votos") / pl.col("votos_base") - 1)
                .otherwise(None)
                .alias("ritmo"),
            )
        )
    colunas = ["dimensao", "categoria", "votos", "votos_base", "quota", "quota_base", "ritmo"]
    return pl.concat([x.select(colunas) for x in linhas]).sort("dimensao", "categoria")


def geografia(cubo: pl.DataFrame, d: int, coluna: str) -> pl.DataFrame:
    """Votos até ``d`` por unidade geográfica e partido, com a linha ``total``."""
    tabela = (
        _ate(cubo, d)
        .drop_nulls(coluna)
        .group_by(coluna, "partido")
        .agg(pl.col("n").sum().alias("votos"))
    )
    return com_total(tabela, "partido", ("votos",)).sort(coluna, "partido")


def geografia_por_faixa(cubo: pl.DataFrame, d: int, coluna: str) -> pl.DataFrame:
    """Votos até ``d`` por unidade geográfica e faixa larga (todos os partidos), com a
    linha ``total``. Só nos estados com idade."""
    tabela = (
        _ate(cubo, d)
        .drop_nulls(coluna)
        .with_columns(
            pl.col("faixa").replace_strict(CANONICA_PARA_LARGA, default=None).alias("faixa")
        )
        .group_by(coluna, "faixa")
        .agg(pl.col("n").sum().alias("votos"))
    )
    return com_total(tabela, "faixa", ("votos",)).sort(coluna, "faixa", nulls_last=True)


def pedidos(cubo: pl.DataFrame, d: int) -> pl.DataFrame:
    """Pedidos até ``d``, quantos estavam devolvidos e quantos por devolver nesse dia."""
    pedidos_ = cubo.filter(pl.col("dias_pedido") >= d)
    devolvido = pl.col("dias_antes").is_not_null() & (pl.col("dias_antes") >= d)
    tabela = pedidos_.group_by("faixa", "partido").agg(
        pl.col("n").sum().alias("pedidos"),
        pl.col("n").filter(devolvido).sum().alias("devolvidos"),
    )
    soma = ("pedidos", "devolvidos")
    tabela = com_total(com_total(tabela, "partido", soma), "faixa", soma)
    return tabela.with_columns((pl.col("pedidos") - pl.col("devolvidos")).alias("pendentes")).sort(
        "faixa", "partido"
    )


def _linhas(tabela: pl.DataFrame, **fixos: Any) -> list[dict[str, Any]]:
    def arredondar(v: Any) -> Any:
        return round(v, CASAS_DECIMAIS) if isinstance(v, float) else v

    return [
        {**fixos, **{k: arredondar(v) for k, v in linha.items()}}
        for linha in tabela.iter_rows(named=True)
    ]


def _ciclo(c: CubosAgregados, d_final: int, d_atual: int | None) -> CicloAgregado:
    e = c.eleicao
    return CicloAgregado(
        ano=e.ano,
        tipo="intercalar" if e.tipo == "intercalar" else "presidencial",
        data_eleicao=e.data,
        votos=total_votos(c.votos, d_final),
        votos_mesmo_dia=None if d_atual is None else total_votos(c.votos, d_atual),
        pedidos=total_pedidos(c.pedidos, d_final if d_atual is None else d_atual)
        if c.pedidos.height
        else None,
        notas=e.notas,
    )


def montar(
    *,
    estado: CodigoEstado,
    atual: CubosAgregados,
    bases: Sequence[CubosAgregados],
    dados_ate: date,
    dimensoes: Sequence[str],
    modalidades: Sequence[str],
    fontes: Sequence[Fonte],
    nomes_condados: Mapping[str, str],
    avisos: Sequence[str] = (),
    gerado_em: datetime | None = None,
    granularidade: Granularidade = "boletim",
) -> VotoAntecipadoAgregado:
    """Monta o ficheiro publicado de um estado (``granularidade`` diz de onde vêm os cubos:
    um registo por boletim ou totais publicados pela fonte)."""
    d = atual.eleicao.dias_antes(dados_ate)
    if d < 0:
        msg = f"Os dados ({dados_ate}) são posteriores à eleição ({atual.eleicao.data})"
        raise ValueError(msg)
    dims_comparacao = [x for x in ("faixa", "partido", "modalidade") if x in dimensoes]

    ciclos = [_ciclo(atual, d, None), *(_ciclo(b, 0, d) for b in bases)]

    pontos: list[PontoSerieAgregado] = []
    for c, d_fim in [(atual, d), *((b, 0) for b in bases)]:
        dias = list(range(max(INICIO_SERIE, d_fim), d_fim - 1, -1))
        pontos.extend(
            PontoSerieAgregado.model_validate(x)
            for x in _linhas(serie(c.votos, dias), ano=c.eleicao.ano)
        )

    comp = [
        LinhaComparacaoAgregada.model_validate(x)
        for b in bases
        for x in _linhas(
            comparacao(atual.votos, b.votos, d, dims_comparacao), ano_base=b.eleicao.ano
        )
    ]

    geo: list[LinhaGeografiaAgregada] = []
    unidades = [
        (coluna, nivel)
        for coluna, nivel in (("fips_condado", "condado"), ("distrito", "distrito"))
        if nivel in dimensoes
    ]
    # Todos os anos ao mesmo dia do ciclo, como a comparação (não o total final).
    for c in [atual, *bases]:
        for coluna, nivel in unidades:
            tabelas = [geografia(c.votos, d, coluna).with_columns(pl.lit(TOTAL).alias("faixa"))]
            if "faixa" in dimensoes:
                # Sem a linha total, que já vem na tabela por partido.
                tabelas.append(
                    geografia_por_faixa(c.votos, d, coluna)
                    .filter(pl.col("faixa") != TOTAL)
                    .with_columns(pl.lit(TOTAL).alias("partido"))
                )
            for tabela in tabelas:
                for x in _linhas(tabela.drop_nulls("faixa"), ano=c.eleicao.ano):
                    valor = x.pop(coluna)
                    codigo, nome = (
                        (valor, nomes_condados.get(valor, valor))
                        if nivel == "condado"
                        else (str(valor), f"{estado.value}-{valor:02d}")
                    )
                    geo.append(
                        LinhaGeografiaAgregada.model_validate(
                            {**x, "nivel": nivel, "codigo": codigo, "nome": nome}
                        )
                    )

    # Os pedidos de cada ano até ao mesmo dia do ciclo; células com menos de
    # LIMIAR_POPULACAO pedidos não são publicadas (ver a metodologia).
    linhas_pedidos = [
        LinhaPedidos.model_validate(x)
        for c in [atual, *bases]
        if c.pedidos.height
        for x in _linhas(
            pedidos(c.pedidos, d).filter(
                (pl.col("pedidos") == 0) | (pl.col("pedidos") >= LIMIAR_POPULACAO)
            ),
            ano=c.eleicao.ano,
        )
    ]

    return VotoAntecipadoAgregado(
        metadados=Metadados(gerado_em=gerado_em or datetime.now(UTC), fontes=tuple(fontes)),
        estado=estado,
        ano=atual.eleicao.ano,
        dados_ate=dados_ate,
        dias_antes=d,
        granularidade=granularidade,
        dimensoes=tuple(dimensoes),
        modalidades=tuple(modalidades),
        ciclos=tuple(ciclos),
        serie=tuple(pontos),
        comparacao=tuple(comp),
        geografia=tuple(geo),
        pedidos=tuple(linhas_pedidos),
        avisos=tuple(avisos),
    )
