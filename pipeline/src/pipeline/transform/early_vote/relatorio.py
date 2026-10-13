"""Montagem do ficheiro publicado ``VotoAntecipadoEstado`` a partir dos cubos.

É igual para todos os estados: o conector de cada estado só tem de produzir os cubos.
"""

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import Any

import polars as pl

from contratos.base import Fonte, Metadados
from contratos.estados import CodigoEstado
from contratos.voto_antecipado import (
    CicloVotoAntecipado,
    LinhaComparacao,
    LinhaCruzamento,
    LinhaGeografia,
    LinhaHistorico,
    LinhaHistoricoGeografia,
    LinhaReserva,
    PontoSerie,
    VotoAntecipadoEstado,
)
from pipeline.comum.calendario import EleicaoGeral
from pipeline.comum.categorias import Modalidade
from pipeline.transform.early_vote import indicadores as ind

INICIO_SERIE = 60
"""Primeiro dia das séries (dias antes da eleição). Antes disto há muito poucos votos."""

CASAS_DECIMAIS = 6
LIMIAR_POPULACAO = 10
"""Linhas cuja população (recenseados ou eleitores habituais) fica entre 1 e este limiar
menos um não são publicadas: são células sem valor analítico (quase sempre a faixa
desconhecida) e reduzem o risco de reidentificação. Os totais são calculados antes."""
DIMENSOES_CRUZAMENTO = ("partido", "raca", "etnia", "genero", "modalidade")


@dataclass(frozen=True, slots=True)
class CubosAno:
    eleicao: EleicaoGeral
    demografico: pl.DataFrame
    geografico: pl.DataFrame


def _arredondar(valor: Any) -> Any:
    if isinstance(valor, float):
        return round(valor, CASAS_DECIMAIS)
    return valor


def _suprimir(tabela: pl.DataFrame, coluna: str) -> pl.DataFrame:
    return tabela.filter((pl.col(coluna) == 0) | (pl.col(coluna) >= LIMIAR_POPULACAO))


def _linhas(
    tabela: pl.DataFrame, *, populacao: str = "registados", **fixos: Any
) -> Iterable[dict[str, Any]]:
    for linha in _suprimir(tabela, populacao).iter_rows(named=True):
        yield {**fixos, **{k: _arredondar(v) for k, v in linha.items()}}


def _ciclo(cubos: CubosAno, d_final: int) -> CicloVotoAntecipado:
    e = cubos.eleicao
    janela = e.janela_presencial_dias_antes()
    totais = ind.contagens(cubos.demografico.with_columns(pl.lit(1).alias("_t")), d_final, ["_t"])
    return CicloVotoAntecipado(
        ano=e.ano,
        tipo="intercalar" if e.tipo == "intercalar" else "presidencial",
        data_eleicao=e.data,
        inicio_presencial_dias_antes=janela[0] if janela else None,
        fim_presencial_dias_antes=janela[1] if janela else None,
        ano_referencia_historico=e.referencia_historico,
        registados=int(totais["registados"][0]),
        votos_antecipados=int(totais["votos"][0]),
        notas=e.notas,
    )


def _serie(cubos: CubosAno, d_final: int) -> list[PontoSerie]:
    dias = list(range(INICIO_SERIE, d_final - 1, -1))
    cubo = cubos.demografico
    pontos: list[PontoSerie] = []
    por_partido = ind.serie(cubo, ["faixa", "partido"], dias)
    por_partido = ind.com_total(por_partido, "partido", ("votos", "registados"))
    por_partido = ind.com_total(por_partido, "faixa", ("votos", "registados"))
    pontos.extend(
        PontoSerie.model_validate(linha)
        for linha in _linhas(por_partido, ano=cubos.eleicao.ano, modalidade="total")
    )
    votantes = cubo.filter(pl.col("modalidade") != str(Modalidade.NAO_VOTOU))
    registados = ind.com_total(
        cubo.group_by("faixa").agg(pl.col("n").sum().cast(pl.Int64).alias("registados")),
        "faixa",
        ("registados",),
    )
    por_modo = ind.serie(votantes, ["faixa", "modalidade"], dias).drop("registados")
    por_modo = ind.com_total(por_modo, "faixa", ("votos",)).join(registados, on="faixa")
    pontos.extend(
        PontoSerie.model_validate(linha)
        for linha in _linhas(por_modo, ano=cubos.eleicao.ano, partido="total")
    )
    return pontos


def montar(
    *,
    estado: CodigoEstado,
    atual: CubosAno,
    bases: Sequence[CubosAno],
    dados_ate: date,
    fontes: Sequence[Fonte],
    nomes_condados: Mapping[str, str],
    avisos: Sequence[str] = (),
    gerado_em: datetime | None = None,
) -> VotoAntecipadoEstado:
    d = atual.eleicao.dias_antes(dados_ate)
    if d < 0:
        msg = f"Os dados ({dados_ate}) são posteriores à eleição ({atual.eleicao.data})"
        raise ValueError(msg)
    todos = [atual, *bases]

    ciclos = [_ciclo(atual, d), *(_ciclo(b, 0) for b in bases)]
    serie = _serie(atual, d) + [p for b in bases for p in _serie(b, 0)]

    comparacao = [
        LinhaComparacao.model_validate(linha)
        for b in bases
        for linha in _linhas(
            ind.comparacao(atual.demografico, b.demografico, d), ano_base=b.eleicao.ano
        )
    ]

    historico = [
        LinhaHistorico.model_validate(linha)
        for c in todos
        if c.eleicao.referencia_historico is not None
        for linha in _linhas(
            ind.decomposicao_historico(c.demografico, d),
            ano=c.eleicao.ano,
            ano_referencia=c.eleicao.referencia_historico,
        )
    ]

    reserva: list[LinhaReserva] = []
    for c in todos:
        if c.eleicao.referencia_historico is None:
            continue
        tabela = ind.reserva(c.demografico, d)
        tabela = ind.com_total(tabela, "partido", ("habituais", "ja_votaram", "restantes"))
        tabela = ind.com_total(tabela, "faixa", ("habituais", "ja_votaram", "restantes"))
        reserva.extend(
            LinhaReserva.model_validate(x)
            for x in _linhas(tabela, populacao="habituais", ano=c.eleicao.ano)
        )

    geografia: list[LinhaGeografia] = []
    for c in todos:
        condados = ind.geografia(c.geografico, d, "fips_condado").drop_nulls("fips_condado")
        for linha in _linhas(condados, ano=c.eleicao.ano, nivel="condado"):
            fips = linha.pop("fips_condado")
            geografia.append(
                LinhaGeografia.model_validate(
                    {**linha, "codigo": fips, "nome": nomes_condados.get(fips, fips)}
                )
            )
        distritos = ind.geografia(c.geografico, d, "distrito_atual").drop_nulls("distrito_atual")
        for linha in _linhas(distritos, ano=c.eleicao.ano, nivel="distrito"):
            numero = linha.pop("distrito_atual")
            geografia.append(
                LinhaGeografia.model_validate(
                    {**linha, "codigo": str(numero), "nome": f"{estado.value}-{numero:02d}"}
                )
            )

    historico_geografia: list[LinhaHistoricoGeografia] = []
    for c in todos:
        referencia = c.eleicao.referencia_historico
        if referencia is None or "grupo" not in c.geografico.columns:
            continue
        for coluna, nivel in (("fips_condado", "condado"), ("distrito_atual", "distrito")):
            tabela = ind.historico_geografia(c.geografico, d, coluna)
            for linha in _linhas(tabela, ano=c.eleicao.ano, ano_referencia=referencia):
                valor = linha.pop(coluna)
                codigo, nome = (
                    (valor, nomes_condados.get(valor, valor))
                    if nivel == "condado"
                    else (str(valor), f"{estado.value}-{valor:02d}")
                )
                historico_geografia.append(
                    LinhaHistoricoGeografia.model_validate(
                        {**linha, "nivel": nivel, "codigo": codigo, "nome": nome}
                    )
                )

    cruzamentos = [
        LinhaCruzamento.model_validate(linha)
        for c in todos
        for dim in DIMENSOES_CRUZAMENTO
        for linha in _linhas(ind.cruzamento(c.demografico, d, dim), ano=c.eleicao.ano, dimensao=dim)
    ]

    agora = gerado_em or datetime.now(UTC)
    return VotoAntecipadoEstado(
        metadados=Metadados(gerado_em=agora, fontes=tuple(fontes)),
        estado=estado,
        ano=atual.eleicao.ano,
        dados_ate=dados_ate,
        dias_antes=d,
        ciclos=tuple(ciclos),
        serie=tuple(serie),
        comparacao=tuple(comparacao),
        historico=tuple(historico),
        reserva=tuple(reserva),
        geografia=tuple(geografia),
        cruzamentos=tuple(cruzamentos),
        avisos=tuple(avisos),
        historico_geografia=tuple(historico_geografia),
    )
