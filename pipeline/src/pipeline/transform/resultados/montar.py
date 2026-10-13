"""Monta os contratos de resultados a partir da tabela longa produzida por cada conector.

Cada conector devolve uma ``Leitura``: uma linha por corrida, candidato e unidade
geográfica (o estado inteiro, um condado ou um município), com os votos tal como a fonte
os publica. Aqui não há estimativas: só somas, validação e o formato do contrato.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime

import polars as pl

from contratos.base import Fonte, Metadados
from contratos.estados import CodigoEstado
from contratos.resultados import (
    Candidatura,
    Cargo,
    Corrida,
    LinhaCorridaNacional,
    ResultadoGeografico,
    ResultadosEstado,
    ResultadosNacional,
    UnidadeApuramento,
    VotosCandidato,
    VotosModalidade,
)

COLUNAS_VOTOS: dict[str, type[pl.DataType] | pl.DataType] = {
    "corrida": pl.String,
    "candidato": pl.String,
    "nome": pl.String,
    "partido": pl.String,
    "partido_fonte": pl.String,
    "nivel": pl.String,
    "codigo": pl.String,
    "votos": pl.Int64,
}
"""``nivel`` é ``estado`` (``codigo`` nulo), ``condado`` (FIPS) ou ``municipio``."""

COLUNAS_MODALIDADES: dict[str, type[pl.DataType] | pl.DataType] = {
    "corrida": pl.String,
    "candidato": pl.String,
    "nivel": pl.String,
    "codigo": pl.String,
    "modalidade": pl.String,
    "votos": pl.Int64,
}
"""Votos por tipo de voto, com o mesmo ``nivel``/``codigo`` dos votos (opcional; só
quando a fonte os separa)."""

COLUNAS_UNIDADES: dict[str, type[pl.DataType] | pl.DataType] = {
    "corrida": pl.String,
    "nivel": pl.String,
    "codigo": pl.String,
    "reportadas": pl.Int64,
    "totais": pl.Int64,
}

PARTIDOS = ("dem", "rep", "outro")


@dataclass(frozen=True, slots=True)
class DescricaoCorrida:
    id: str
    nome_fonte: str
    cargo: Cargo
    distrito: int | None = None
    especial: bool = False
    notas: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class Leitura:
    """O que um conector extrai de um retrato do feed oficial."""

    corridas: tuple[DescricaoCorrida, ...]
    votos: pl.DataFrame
    unidades: pl.DataFrame
    tipo_unidade: UnidadeApuramento | None
    atualizado_fonte: datetime | None = None
    modalidades: pl.DataFrame | None = None


def vazio_unidades() -> pl.DataFrame:
    return pl.DataFrame(schema=COLUNAS_UNIDADES)


def _verificar(leitura: Leitura) -> None:
    for nome, tabela, esquema in (
        ("votos", leitura.votos, COLUNAS_VOTOS),
        ("unidades", leitura.unidades, COLUNAS_UNIDADES),
    ):
        faltam = set(esquema) - set(tabela.columns)
        if faltam:
            msg = f"Faltam colunas em {nome}: {sorted(faltam)}"
            raise ValueError(msg)
    partidos = set(leitura.votos["partido"].unique().to_list()) - set(PARTIDOS)
    if partidos:
        msg = f"Partidos não normalizados: {sorted(partidos)}"
        raise ValueError(msg)
    if leitura.votos["votos"].min() is not None and (leitura.votos["votos"] < 0).any():
        msg = "Votos negativos"
        raise ValueError(msg)
    conhecidas = {c.id for c in leitura.corridas}
    desconhecidas = set(leitura.votos["corrida"].unique().to_list()) - conhecidas
    if desconhecidas:
        msg = f"Corridas sem descrição: {sorted(desconhecidas)}"
        raise ValueError(msg)


def _totais_estado(votos: pl.DataFrame) -> pl.DataFrame:
    """Votos por corrida e candidato no estado: a linha ``estado`` da fonte quando existe,
    senão a soma das unidades geográficas."""
    estado = votos.filter(pl.col("nivel") == "estado")
    somados = (
        votos.filter(pl.col("nivel") != "estado")
        .group_by("corrida", "candidato")
        .agg(pl.col("votos").sum())
    )
    com_estado = set(estado["corrida"].unique().to_list())
    somados = somados.filter(~pl.col("corrida").is_in(list(com_estado)))
    return pl.concat([estado.select("corrida", "candidato", "votos"), somados])


def _por_modalidade(
    modalidades: pl.DataFrame | None, corrida: str
) -> dict[str, tuple[VotosModalidade, ...]]:
    if modalidades is None:
        return {}
    da_corrida = modalidades.filter(pl.col("corrida") == corrida)
    estado = da_corrida.filter(pl.col("nivel") == "estado")
    linhas = (
        (estado if estado.height else da_corrida)
        .group_by("candidato", "modalidade")
        .agg(pl.col("votos").sum())
        .sort("candidato", "modalidade")
    )
    resultado: dict[str, list[VotosModalidade]] = {}
    for cand, modalidade, votos in linhas.iter_rows():
        resultado.setdefault(cand, []).append(
            VotosModalidade(modalidade=modalidade, votos=int(votos))
        )
    return {k: tuple(v) for k, v in resultado.items()}


def _unidades(unidades: pl.DataFrame, corrida: str) -> tuple[int | None, int | None]:
    linhas = unidades.filter(pl.col("corrida") == corrida)
    estado = linhas.filter(pl.col("nivel") == "estado")
    escolhidas = estado if estado.height else linhas
    if not escolhidas.height:
        return None, None
    rep, tot = escolhidas["reportadas"].sum(), escolhidas["totais"].sum()
    return int(rep), int(tot)


def montar(
    *,
    estado: CodigoEstado,
    data_eleicao: date,
    leitura: Leitura,
    fontes: Sequence[Fonte],
    nomes_geo: Mapping[str, str] | None = None,
    avisos: Sequence[str] = (),
    gerado_em: datetime | None = None,
) -> ResultadosEstado:
    _verificar(leitura)
    votos = leitura.votos
    nomes_geo = nomes_geo or {}
    estado_total = _totais_estado(votos)
    candidatos_info = votos.unique(["corrida", "candidato"], keep="first", maintain_order=True)
    corridas: list[Corrida] = []
    for desc in leitura.corridas:
        info = candidatos_info.filter(pl.col("corrida") == desc.id)
        if not info.height:
            continue
        totais = dict(
            estado_total.filter(pl.col("corrida") == desc.id)
            .select("candidato", "votos")
            .iter_rows()
        )
        por_modalidade = _por_modalidade(leitura.modalidades, desc.id)
        candidatos = sorted(
            (
                Candidatura(
                    id=linha["candidato"],
                    nome=linha["nome"],
                    partido=linha["partido"],
                    partido_fonte=linha["partido_fonte"],
                    votos=int(totais.get(linha["candidato"], 0)),
                    por_modalidade=por_modalidade.get(linha["candidato"], ()),
                )
                for linha in info.iter_rows(named=True)
            ),
            key=lambda c: (-c.votos, c.id),
        )
        geografia = _geografia(votos, leitura.unidades, desc.id, nomes_geo)
        reportadas, totais_unidades = _unidades(leitura.unidades, desc.id)
        corridas.append(
            Corrida(
                id=desc.id,
                estado=estado,
                cargo=desc.cargo,
                distrito=desc.distrito,
                especial=desc.especial,
                nome_fonte=desc.nome_fonte,
                candidatos=tuple(candidatos),
                total=sum(c.votos for c in candidatos),
                unidades_reportadas=reportadas,
                unidades_totais=totais_unidades,
                tipo_unidade=leitura.tipo_unidade,
                geografia=geografia,
                notas=desc.notas,
            )
        )
    return ResultadosEstado(
        metadados=Metadados(gerado_em=gerado_em or datetime.now(UTC), fontes=tuple(fontes)),
        estado=estado,
        data_eleicao=data_eleicao,
        atualizado_fonte=leitura.atualizado_fonte,
        corridas=tuple(corridas),
        avisos=tuple(avisos),
    )


def _geografia(
    votos: pl.DataFrame,
    unidades: pl.DataFrame,
    corrida: str,
    nomes_geo: Mapping[str, str],
) -> tuple[ResultadoGeografico, ...]:
    locais = votos.filter((pl.col("corrida") == corrida) & (pl.col("nivel") != "estado"))
    if not locais.height:
        return ()
    contagem = {
        (n, c): (r, t)
        for n, c, r, t in unidades.filter(
            (pl.col("corrida") == corrida) & (pl.col("nivel") != "estado")
        )
        .select("nivel", "codigo", "reportadas", "totais")
        .iter_rows()
    }
    resultado = []
    for (nivel, codigo), grupo in sorted(
        locais.group_by("nivel", "codigo"), key=lambda g: (str(g[0][0]), str(g[0][1]))
    ):
        rep, tot = contagem.get((nivel, codigo), (None, None))
        votos_cand = tuple(
            VotosCandidato(candidato=c, votos=int(v))
            for c, v in grupo.sort("candidato").select("candidato", "votos").iter_rows()
        )
        resultado.append(
            ResultadoGeografico(
                nivel=str(nivel),
                codigo=str(codigo),
                nome=nomes_geo.get(str(codigo), str(codigo)),
                votos=votos_cand,
                total=sum(v.votos for v in votos_cand),
                unidades_reportadas=rep,
                unidades_totais=tot,
            )
        )
    return tuple(resultado)


def linhas_nacionais(resultados: ResultadosEstado, ficheiro: str) -> list[LinhaCorridaNacional]:
    linhas = []
    for c in resultados.corridas:
        por_partido = {p: sum(x.votos for x in c.candidatos if x.partido == p) for p in PARTIDOS}
        apuramento = (
            round(c.unidades_reportadas / c.unidades_totais, 4)
            if c.unidades_reportadas is not None and c.unidades_totais
            else None
        )
        linhas.append(
            LinhaCorridaNacional(
                id=c.id,
                estado=c.estado,
                cargo=c.cargo,
                distrito=c.distrito,
                ficheiro=ficheiro,
                atualizado_fonte=resultados.atualizado_fonte,
                total=c.total,
                votos_dem=por_partido["dem"],
                votos_rep=por_partido["rep"],
                votos_outros=por_partido["outro"],
                apuramento=apuramento,
            )
        )
    return linhas


def nacional(
    estados: Sequence[tuple[ResultadosEstado, str]],
    *,
    data_eleicao: date,
    gerado_em: datetime | None = None,
) -> ResultadosNacional:
    fontes = tuple(f for r, _ in estados for f in r.metadados.fontes)
    linhas = [linha for r, f in estados for linha in linhas_nacionais(r, f)]
    return ResultadosNacional(
        metadados=Metadados(gerado_em=gerado_em or datetime.now(UTC), fontes=fontes),
        data_eleicao=data_eleicao,
        corridas=tuple(sorted(linhas, key=lambda x: x.id)),
        avisos=(
            "Resultados oficiais tal como publicados por cada estado no momento da recolha; "
            "não são projeções nem chamadas de vencedor.",
        ),
    )
