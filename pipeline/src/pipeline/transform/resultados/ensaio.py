"""Verificações de uma sequência de retratos de resultados (noite real ou ensaio).

Num feed oficial, os totais só sobem, salvo correções. Estas verificações não bloqueiam a
publicação de correções legítimas: devolvem avisos que o ensaio geral trata como falhas e
que, na noite eleitoral, ficam registados para revisão.
"""

import random
from collections.abc import Sequence
from dataclasses import dataclass, replace

import polars as pl

from contratos.resultados import ResultadosEstado
from pipeline.transform.resultados.montar import Leitura

TOLERANCIA_DESCIDA = 0.001
"""Descida relativa do total de uma corrida que se aceita sem aviso (arredondamentos)."""


@dataclass(frozen=True, slots=True)
class Problema:
    indice: int
    """Posição do retrato na sequência."""

    corrida: str
    descricao: str


def verificar_sequencia(retratos: Sequence[ResultadosEstado]) -> list[Problema]:
    problemas: list[Problema] = []
    anterior: dict[str, tuple[int, int | None, set[str]]] = {}
    for i, retrato in enumerate(retratos):
        atuais = {c.id for c in retrato.corridas}
        for corrida_id in sorted(set(anterior) - atuais):
            problemas.append(Problema(i, corrida_id, "corrida desapareceu do feed"))
        for c in retrato.corridas:
            ids = {x.id for x in c.candidatos}
            if c.id in anterior:
                total, unidades, candidatos = anterior[c.id]
                if c.total < total * (1 - TOLERANCIA_DESCIDA):
                    problemas.append(Problema(i, c.id, f"total desceu de {total} para {c.total}"))
                if (
                    unidades is not None
                    and c.unidades_reportadas is not None
                    and c.unidades_reportadas < unidades
                ):
                    problemas.append(
                        Problema(
                            i,
                            c.id,
                            f"unidades reportadas desceram de {unidades} para "
                            f"{c.unidades_reportadas}",
                        )
                    )
                if candidatos - ids:
                    problemas.append(
                        Problema(i, c.id, f"candidatos desapareceram: {sorted(candidatos - ids)}")
                    )
            anterior[c.id] = (c.total, c.unidades_reportadas, ids)
    return problemas


def progressao(leitura: Leitura, passos: int, semente: int = 0) -> list[Leitura]:
    """Reconstrói uma noite plausível a partir do resultado final de 2022 ou 2024.

    Os feeds oficiais só guardam o ficheiro final, por isso o ensaio revela os condados
    por uma ordem aleatória (como chegam na noite), recalculando o estado a partir dos
    condados já revelados. Sem condados (Geórgia), revela uma fração crescente dos votos
    e das unidades. O último passo é sempre o resultado final completo.
    """
    gerador = random.Random(semente)  # noqa: S311 (ordem de ensaio, não criptografia)
    locais = leitura.votos.filter(pl.col("nivel") != "estado")
    if locais.height:
        codigos = sorted(set(locais["codigo"].drop_nulls().to_list()))
        gerador.shuffle(codigos)
        cortes = [round(len(codigos) * (i + 1) / passos) for i in range(passos)]
        return [_revelar(leitura, set(codigos[:k])) for k in cortes[:-1]] + [leitura]
    fracoes = [(i + 1) / passos for i in range(passos)]
    return [_fracao(leitura, f) for f in fracoes[:-1]] + [leitura]


def _revelar(leitura: Leitura, revelados: set[str]) -> Leitura:
    visivel = pl.col("codigo").is_in(list(revelados))
    votos = leitura.votos.filter(pl.col("nivel") != "estado").with_columns(
        pl.when(visivel).then(pl.col("votos")).otherwise(0).alias("votos")
    )
    unidades = leitura.unidades.filter(pl.col("nivel") != "estado").with_columns(
        pl.when(visivel).then(pl.col("reportadas")).otherwise(0).alias("reportadas")
    )
    modalidades = leitura.modalidades
    if modalidades is not None:
        modalidades = modalidades.filter(pl.col("nivel") != "estado").with_columns(
            pl.when(visivel).then(pl.col("votos")).otherwise(0).alias("votos")
        )
    return replace(leitura, votos=votos, unidades=unidades, modalidades=modalidades)


def _fracao(leitura: Leitura, fracao: float) -> Leitura:
    votos = leitura.votos.with_columns((pl.col("votos") * fracao).floor().cast(pl.Int64))
    unidades = leitura.unidades.with_columns(
        (pl.col("totais") * fracao).floor().cast(pl.Int64).alias("reportadas")
    )
    modalidades = leitura.modalidades
    if modalidades is not None:
        modalidades = modalidades.with_columns((pl.col("votos") * fracao).floor().cast(pl.Int64))
    return replace(leitura, votos=votos, unidades=unidades, modalidades=modalidades)
