"""Atualiza o voto antecipado da Florida (totais por condado e partido).

Uso::

    uv run python -m pipeline.jobs.voto_antecipado_fl --saida data/publicado/fl.json \\
        --arquivo data/publicado/historico-fl-2026.csv

A fonte só publica o retrato do dia. Cada execução acrescenta-o ao ``--arquivo`` (CSV com
uma linha por dia, condado, partido e tipo), que o workflow guarda na Release ao lado do
JSON; é desse arquivo que sai a série diária.
"""

import argparse
import logging
from datetime import UTC, date, datetime
from pathlib import Path

import httpx
import polars as pl

from contratos.base import Fonte, Metadados
from contratos.estados import CodigoEstado
from contratos.voto_antecipado_agregado import (
    CicloAgregado,
    LinhaGeografiaAgregada,
    LinhaPedidos,
    PontoSerieAgregado,
    VotoAntecipadoAgregado,
)
from pipeline.comum.calendario import eleicao_geral
from pipeline.comum.descarga import USER_AGENT, Descarga, descarregar
from pipeline.connectors.early_vote.fl import fontes
from pipeline.connectors.early_vote.fl.codigos import FIPS_CONDADO
from pipeline.connectors.early_vote.fl.ler import juntar_arquivo, ler_arquivo, ler_estatisticas
from pipeline.transform.early_vote.indicadores import TOTAL, com_total

registo = logging.getLogger(__name__)

ANO = 2026
VOTOS = ("correio", "presencial")
NOMES_CONDADOS = {
    fips: nome.title().replace("Desoto", "DeSoto") for nome, fips in FIPS_CONDADO.items()
}
AVISOS = (
    "A Florida só publica totais por condado e partido, sem idade: não há comparação com "
    "anos anteriores no mesmo dia do ciclo. A série diária começa no primeiro retrato que "
    "guardámos.",
    "Os condados enviam os relatórios a horas diferentes; cada condado entra com o último "
    "relatório disponível.",
)


def ao_dia(arquivo: pl.DataFrame, dia: date) -> pl.DataFrame:
    """Último retrato de cada condado, partido e tipo com dados até ``dia`` (inclusive)."""
    return (
        arquivo.filter(pl.col("dados_ate") <= dia)
        .sort("dados_ate")
        .group_by("fips_condado", "partido", "tipo")
        .agg(pl.col("n").last(), pl.col("dados_ate").last())
    )


def serie(
    arquivo: pl.DataFrame, dias_ate: list[date], data_eleicao: date
) -> list[dict[str, object]]:
    pontos: list[dict[str, object]] = []
    for dia in dias_ate:
        votos = ao_dia(arquivo, dia).filter(pl.col("tipo").is_in(VOTOS))
        d = (data_eleicao - dia).days
        por_partido = com_total(
            votos.group_by("partido").agg(pl.col("n").sum().alias("votos")), "partido", ("votos",)
        )
        pontos += [
            {"ano": ANO, "dias_antes": d, "faixa": TOTAL, "modalidade": TOTAL, **x}
            for x in por_partido.iter_rows(named=True)
        ]
        por_modo = votos.group_by("tipo").agg(pl.col("n").sum().alias("votos"))
        pontos += [
            {
                "ano": ANO,
                "dias_antes": d,
                "faixa": TOTAL,
                "partido": TOTAL,
                "modalidade": x["tipo"],
                "votos": x["votos"],
            }
            for x in por_modo.iter_rows(named=True)
        ]
    return pontos


def montar(arquivo: pl.DataFrame, fontes_: list[Fonte]) -> VotoAntecipadoAgregado:
    eleicao = eleicao_geral("FL", ANO)
    com_votos = arquivo.filter(pl.col("tipo").is_in(VOTOS))
    dados_ate: date = com_votos["dados_ate"].max()  # type: ignore[assignment]
    # O retrato mais recente de cada tipo, mesmo que os ficheiros de pedidos e de votos
    # tenham sido compilados em dias diferentes.
    atual = ao_dia(arquivo, arquivo["dados_ate"].max())  # type: ignore[arg-type]
    votos = atual.filter(pl.col("tipo").is_in(VOTOS))
    total = int(votos["n"].sum())

    geografia = com_total(
        votos.group_by("fips_condado", "partido").agg(pl.col("n").sum().alias("votos")),
        "partido",
        ("votos",),
    ).sort("fips_condado", "partido")
    linhas_geo = [
        LinhaGeografiaAgregada(
            ano=ANO,
            nivel="condado",
            codigo=x["fips_condado"],
            nome=NOMES_CONDADOS[x["fips_condado"]],
            partido=x["partido"],
            votos=x["votos"],
        )
        for x in geografia.iter_rows(named=True)
    ]

    correio = atual.filter(pl.col("tipo").is_in(["correio", "pendentes"]))
    pedidos = com_total(
        correio.group_by("partido").agg(
            pl.col("n").sum().alias("pedidos"),
            pl.col("n").filter(pl.col("tipo") == "correio").sum().alias("devolvidos"),
        ),
        "partido",
        ("pedidos", "devolvidos"),
    )
    linhas_pedidos = [
        LinhaPedidos(
            ano=ANO,
            faixa=TOTAL,
            partido=x["partido"],
            pedidos=x["pedidos"],
            devolvidos=x["devolvidos"],
            pendentes=x["pedidos"] - x["devolvidos"],
        )
        for x in pedidos.iter_rows(named=True)
    ]

    dias = sorted(set(com_votos["dados_ate"].to_list()))
    pontos = [PontoSerieAgregado.model_validate(p) for p in serie(arquivo, dias, eleicao.data)]

    atrasados = atual.filter(pl.col("tipo").is_in(VOTOS) & (pl.col("dados_ate") < dados_ate))
    avisos = list(AVISOS)
    if atrasados.height:
        n = atrasados["fips_condado"].n_unique()
        avisos.append(f"{n} condados ainda não enviaram o relatório do último dia.")
    if "presencial" not in set(votos["tipo"].to_list()):
        avisos.append("O voto antecipado presencial ainda não começou ou não foi reportado.")

    return VotoAntecipadoAgregado(
        metadados=Metadados(gerado_em=datetime.now(UTC), fontes=tuple(fontes_)),
        estado=CodigoEstado.FL,
        ano=ANO,
        dados_ate=dados_ate,
        dias_antes=eleicao.dias_antes(dados_ate),
        granularidade="condado",
        dimensoes=("partido", "modalidade", "condado"),
        modalidades=("correio", "presencial"),
        ciclos=(
            CicloAgregado(
                ano=ANO,
                tipo="intercalar",
                data_eleicao=eleicao.data,
                votos=total,
                pedidos=int(correio["n"].sum()),
                notas=(),
            ),
        ),
        serie=tuple(pontos),
        comparacao=(),
        geografia=tuple(linhas_geo),
        pedidos=tuple(linhas_pedidos),
        avisos=tuple(avisos),
    )


def executar(raiz: Path, saida: Path, arquivo: Path, *, descarregar_: bool) -> None:
    pasta = raiz / "data" / "brutos" / "fl"
    descargas: list[Descarga] = []
    if descarregar_:
        with httpx.Client(timeout=httpx.Timeout(60.0), follow_redirects=True) as cliente:
            pagina = cliente.get(fontes.PAGINA, headers={"User-Agent": USER_AGENT})
            pagina.raise_for_status()
            urls = fontes.urls_estatisticas(pagina.text)
            if not urls:
                msg = f"Sem ficheiros de estatísticas em {fontes.PAGINA}"
                raise RuntimeError(msg)
            descargas = [
                descarregar(u, pasta / u.rsplit("/", 1)[-1], cliente=cliente) for u in urls
            ]
        caminhos = [d.caminho for d in descargas]
    else:
        caminhos = sorted(pasta.glob("Stats_*.txt"))
    retrato = ler_estatisticas(caminhos)
    completo = juntar_arquivo(ler_arquivo(arquivo), retrato)
    arquivo.parent.mkdir(parents=True, exist_ok=True)
    completo.write_csv(arquivo)
    agora = datetime.now(UTC)
    fontes_ = [
        Fonte(nome=fontes.NOME_FONTE, url=d.url, licenca=fontes.LICENCA, obtida_em=d.obtido_em)
        for d in descargas
    ] or [Fonte(nome=fontes.NOME_FONTE, url=fontes.PAGINA, licenca=fontes.LICENCA, obtida_em=agora)]
    publicado = montar(completo, fontes_)
    saida.parent.mkdir(parents=True, exist_ok=True)
    saida.write_text(publicado.model_dump_json(), encoding="utf-8")
    registo.info(
        "Escrito %s: dados até %s, %s votos, arquivo com %s dias",
        saida,
        publicado.dados_ate,
        publicado.ciclos[0].votos,
        completo["dados_ate"].n_unique(),
    )


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--raiz", type=Path, default=Path.cwd())
    parser.add_argument("--saida", type=Path, required=True)
    parser.add_argument("--arquivo", type=Path, required=True, help="CSV com os retratos diários")
    parser.add_argument("--sem-descarga", action="store_true")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    executar(args.raiz, args.saida, args.arquivo, descarregar_=not args.sem_descarga)


if __name__ == "__main__":
    main()
