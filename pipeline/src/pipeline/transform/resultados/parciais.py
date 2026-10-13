"""``ResultadosParciais``: os votos de cada corrida por unidade, para o estimador ao vivo.

Parte das ``Leitura`` dos conectores (não dos ficheiros publicados), porque só aí estão os
votos por tipo em cada condado. Regras da interface acordada com o Modelo C:

- uma linha por corrida e condado quando a fonte dá condados; ``total`` quando só dá o
  total da corrida;
- ``votos_d``/``votos_r`` somam os candidatos com rótulo democrata/republicano; o resto
  vai para ``votos_outros``. Os partidos são só rótulos (teste de troca de rótulos);
- só Senado e Câmara, com os identificadores da previsão;
- nos estados acompanhados só por alguns condados, as unidades são esses condados (nunca
  ``total``) e o estado vem em ``cobertura_parcial``, para o Modelo C não tomar a soma
  desses condados pelo estado inteiro.
"""

from collections.abc import Sequence
from datetime import UTC, datetime

import polars as pl

from contratos.base import Fonte, Metadados
from contratos.estados import CodigoEstado
from contratos.resultados import (
    CoberturaParcial,
    ContagemModo,
    ResultadosParciais,
    UnidadeContagem,
)
from pipeline.transform.resultados.montar import Leitura

_LADOS = (
    pl.when(pl.col("partido") == "dem").then(pl.lit("votos_d"))
    .when(pl.col("partido") == "rep").then(pl.lit("votos_r"))
    .otherwise(pl.lit("votos_outros"))
)  # fmt: skip


def _por_lado(tabela: pl.DataFrame, chaves: list[str]) -> pl.DataFrame:
    largo = (
        tabela.with_columns(_LADOS.alias("lado"))
        .group_by([*chaves, "lado"])
        .agg(pl.col("votos").sum())
        .pivot(on="lado", index=chaves, values="votos")
    )
    for coluna in ("votos_d", "votos_r", "votos_outros"):
        if coluna not in largo.columns:
            largo = largo.with_columns(pl.lit(0, dtype=pl.Int64).alias(coluna))
    return largo.fill_null(0)


def _unidades_leitura(leitura: Leitura) -> list[UnidadeContagem]:
    congresso = {c.id for c in leitura.corridas if c.cargo in ("senado", "camara")}
    votos = leitura.votos.filter(pl.col("corrida").is_in(list(congresso)))
    com_locais = set(votos.filter(pl.col("nivel") != "estado")["corrida"].unique().to_list())

    def escolher(tabela: pl.DataFrame) -> pl.DataFrame:
        return tabela.filter(
            pl.when(pl.col("corrida").is_in(list(com_locais)))
            .then(pl.col("nivel") != "estado")
            .otherwise(pl.col("nivel") == "estado")
        ).with_columns(pl.col("codigo").fill_null("total").alias("unidade"))

    chaves = ["corrida", "unidade"]
    base = _por_lado(escolher(votos), chaves)
    partidos = votos.select("corrida", "candidato", "partido").unique()
    modos: dict[tuple[str, str], list[ContagemModo]] = {}
    if leitura.modalidades is not None and leitura.modalidades.height:
        tabela = escolher(
            leitura.modalidades.filter(pl.col("corrida").is_in(list(congresso)))
        ).join(partidos, on=["corrida", "candidato"], how="left")
        for linha in (
            _por_lado(tabela, [*chaves, "modalidade"])
            .sort("corrida", "unidade", "modalidade")
            .iter_rows(named=True)
        ):
            modos.setdefault((linha["corrida"], linha["unidade"]), []).append(
                ContagemModo(
                    modo=linha["modalidade"],
                    votos_d=linha["votos_d"],
                    votos_r=linha["votos_r"],
                    votos_outros=linha["votos_outros"],
                )
            )
    seccoes = {
        (c, u or "total"): (r, t)
        for c, n, u, r, t in leitura.unidades.select(
            "corrida", "nivel", "codigo", "reportadas", "totais"
        ).iter_rows()
        if (n != "estado") == (c in com_locais)
    }
    return [
        UnidadeContagem(
            corrida=linha["corrida"],
            unidade=linha["unidade"],
            votos_d=linha["votos_d"],
            votos_r=linha["votos_r"],
            votos_outros=linha["votos_outros"],
            por_modo=tuple(modos.get((linha["corrida"], linha["unidade"]), ())),
            seccoes_reportadas=seccoes.get((linha["corrida"], linha["unidade"]), (None, None))[0],
            seccoes_totais=seccoes.get((linha["corrida"], linha["unidade"]), (None, None))[1],
        )
        for linha in base.sort("corrida", "unidade").iter_rows(named=True)
    ]


NOTA_PARCIAL = (
    "O site estadual recusa pedidos automáticos; só estes condados têm fonte oficial aberta. "
    "Os outros condados não estão por apurar: estão fora da recolha."
)


def montar_parciais(
    leituras: Sequence[Leitura],
    *,
    ano: int,
    instante: datetime,
    fontes: Sequence[Fonte],
    reconstruido: bool = False,
    gerado_em: datetime | None = None,
) -> ResultadosParciais:
    unidades = [u for leitura in leituras for u in _unidades_leitura(leitura)]
    cobertura = [
        CoberturaParcial(
            estado=CodigoEstado(leitura.corridas[0].id[:2]),
            condados=tuple(sorted(leitura.cobertura_condados)),
            nota=NOTA_PARCIAL,
        )
        for leitura in leituras
        if leitura.cobertura_condados and leitura.corridas
    ]
    return ResultadosParciais(
        cobertura_parcial=tuple(sorted(cobertura, key=lambda c: c.estado.value)),
        metadados=Metadados(gerado_em=gerado_em or datetime.now(UTC), fontes=tuple(fontes)),
        ano=ano,
        instante=instante,
        reconstruido=reconstruido,
        unidades=tuple(sorted(unidades, key=lambda u: (u.corrida, u.unidade))),
    )
