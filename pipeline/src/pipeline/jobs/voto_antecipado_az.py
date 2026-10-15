"""Atualiza o voto antecipado do Arizona (boletins devolvidos por condado, fonte não oficial).

Uso::

    uv run python -m pipeline.jobs.voto_antecipado_az --saida data/publicado/az.json \\
        --arquivo data/publicado/historico-az-2026.csv

A fonte (Stealth Analytics) só publica o retrato do dia. Cada execução acrescenta-o ao
``--arquivo`` (CSV com uma linha por dia de atualização e condado), que o workflow guarda na
Release ao lado do JSON; é desse arquivo que sai a série diária.
"""

import argparse
import logging
from datetime import UTC, date, datetime
from pathlib import Path

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
from pipeline.comum.descarga import descarregar
from pipeline.connectors.early_vote.az import fontes
from pipeline.connectors.early_vote.az.codigos import NOMES_CONDADO
from pipeline.connectors.early_vote.az.ler import juntar_arquivo, ler_arquivo, ler_pagina
from pipeline.transform.early_vote.indicadores import TOTAL

registo = logging.getLogger(__name__)

ANO = 2026
AVISOS = (
    "Fonte não oficial: um agregador independente (Stealth Analytics, Derek Weech) que reúne "
    "os relatórios dos condados do Arizona. O Secretary of State e o condado de Maricopa "
    "bloqueiam pedidos automáticos, por isso não há fonte oficial aberta.",
    "No Arizona quase todo o voto antecipado é por boletim enviado pelo correio ou entregue em "
    "mão: os boletins devolvidos contam como votos e os emitidos como pedidos. O voto "
    "presencial antecipado não vem separado e fica incluído.",
    "A fonte não dá partido nem idade, e não há comparação com anos anteriores. A série "
    "diária começa no primeiro retrato que guardámos.",
    "Cada condado atualiza a horas diferentes: cada condado entra com o último dia que a "
    "fonte indica para ele.",
)


def ao_dia(arquivo: pl.DataFrame, dia: date) -> pl.DataFrame:
    """Último retrato de cada condado com dados até ``dia`` (inclusive)."""
    return (
        arquivo.filter(pl.col("dados_ate") <= dia)
        .sort("dados_ate")
        .group_by("fips_condado")
        .agg(pl.col("devolvidos").last(), pl.col("emitidos").last(), pl.col("dados_ate").last())
    )


def dias_da_serie(arquivo: pl.DataFrame) -> list[date]:
    """Dias com retrato de todos os condados: a série só começa quando já temos um valor de
    cada um (antes, a soma seria parcial e pareceria um salto)."""
    por_condado = arquivo.group_by("fips_condado").agg(pl.col("dados_ate").min())
    primeiro: date = por_condado["dados_ate"].max()  # type: ignore[assignment]
    return sorted(d for d in set(arquivo["dados_ate"].to_list()) if d >= primeiro)


def serie(arquivo: pl.DataFrame, data_eleicao: date) -> list[PontoSerieAgregado]:
    pontos: list[PontoSerieAgregado] = []
    for dia in dias_da_serie(arquivo):
        votos = int(ao_dia(arquivo, dia)["devolvidos"].sum())
        for modalidade in (TOTAL, "correio"):
            pontos.append(
                PontoSerieAgregado(
                    ano=ANO,
                    dias_antes=(data_eleicao - dia).days,
                    faixa=TOTAL,
                    partido=TOTAL,
                    modalidade=modalidade,
                    votos=votos,
                )
            )
    return pontos


def montar(arquivo: pl.DataFrame, fontes_: list[Fonte]) -> VotoAntecipadoAgregado:
    eleicao = eleicao_geral("AZ", ANO)
    dados_ate: date = arquivo["dados_ate"].max()  # type: ignore[assignment]
    atual = ao_dia(arquivo, dados_ate).sort("fips_condado")
    devolvidos = int(atual["devolvidos"].sum())
    emitidos = int(atual["emitidos"].sum())

    geografia = tuple(
        LinhaGeografiaAgregada(
            ano=ANO,
            nivel="condado",
            codigo=x["fips_condado"],
            nome=NOMES_CONDADO[x["fips_condado"]],
            partido=TOTAL,
            votos=x["devolvidos"],
        )
        for x in atual.iter_rows(named=True)
    )
    pedidos = LinhaPedidos(
        ano=ANO,
        faixa=TOTAL,
        partido=TOTAL,
        pedidos=emitidos,
        devolvidos=devolvidos,
        pendentes=emitidos - devolvidos,
    )

    avisos = list(AVISOS)
    atrasados = atual.filter(pl.col("dados_ate") < dados_ate)
    if atrasados.height:
        avisos.append(f"{atrasados.height} condados ainda não atualizaram o último dia.")

    return VotoAntecipadoAgregado(
        metadados=Metadados(gerado_em=datetime.now(UTC), fontes=tuple(fontes_)),
        estado=CodigoEstado.AZ,
        ano=ANO,
        dados_ate=dados_ate,
        dias_antes=eleicao.dias_antes(dados_ate),
        granularidade="condado",
        dimensoes=("modalidade", "condado"),
        modalidades=("correio",),
        ciclos=(
            CicloAgregado(
                ano=ANO,
                tipo="intercalar",
                data_eleicao=eleicao.data,
                votos=devolvidos,
                pedidos=emitidos,
                notas=(),
            ),
        ),
        serie=tuple(serie(arquivo, eleicao.data)),
        comparacao=(),
        geografia=geografia,
        pedidos=(pedidos,),
        avisos=tuple(avisos),
    )


def executar(raiz: Path, saida: Path, arquivo: Path, *, descarregar_: bool) -> None:
    caminho = raiz / "data" / "brutos" / "az" / "early-ballots.html"
    obtida_em = datetime.now(UTC)
    if descarregar_:
        descarga = descarregar(fontes.PAGINA, caminho)
        obtida_em = descarga.obtido_em
    retrato = ler_pagina(caminho.read_text(encoding="utf-8"))
    completo = juntar_arquivo(ler_arquivo(arquivo), retrato)
    arquivo.parent.mkdir(parents=True, exist_ok=True)
    completo.write_csv(arquivo)
    fonte = Fonte(
        nome=fontes.NOME_FONTE,
        url=fontes.PAGINA,
        licenca=fontes.LICENCA,
        obtida_em=obtida_em,
        oficial=False,
    )
    publicado = montar(completo, [fonte])
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
