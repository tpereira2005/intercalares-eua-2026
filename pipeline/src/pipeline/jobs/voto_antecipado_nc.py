"""Atualiza o rastreador de voto antecipado da Carolina do Norte.

Uso::

    uv run python -m pipeline.jobs.voto_antecipado_nc --saida data/publicado/nc.json

Descarrega (com pedidos condicionais) o ficheiro de boletins de 2026, o ficheiro de
eleitores e o histórico de voto, constrói os cubos de 2026 e compara-os com os cubos dos
anos de referência guardados em ``data/reference/nc`` (ver
``pipeline.jobs.referencia_voto_antecipado_nc``).
"""

import argparse
import logging
from pathlib import Path

import httpx
import polars as pl

from contratos.estados import CodigoEstado
from pipeline.comum.calendario import eleicao_nc
from pipeline.connectors.early_vote.nc import codigos, recolha
from pipeline.connectors.early_vote.nc.fontes import URL_ELEITORES, URL_HISTORICO
from pipeline.connectors.early_vote.nc.processar import (
    caminho_cubo,
    guardar_cubos,
    ler_cubos,
    processar_ano,
)
from pipeline.transform.early_vote.relatorio import CubosAno, montar

registo = logging.getLogger(__name__)

ANO = 2026
ANOS_BASE = (2022, 2018, 2024, 2016)
"""Intercalares primeiro (as comparações principais), depois as presidenciais de referência."""


def avisos_automaticos(
    *, dias_antes: int, ano: int, sem_recenseamento: int, bases_em_falta: list[int]
) -> list[str]:
    eleicao = eleicao_nc(ano)
    avisos: list[str] = []
    janela = eleicao.janela_presencial_dias_antes()
    if janela and dias_antes > janela[0]:
        avisos.append(
            f"O voto antecipado presencial só começa a {eleicao.inicio_presencial:%d/%m}: "
            "até lá, todos os votos são por correspondência, onde os mais velhos pesam mais."
        )
    if sem_recenseamento:
        avisos.append(
            f"{sem_recenseamento} votantes ainda não constam do ficheiro de eleitores "
            "(sobretudo recenseamento no próprio dia); usam-se os dados do boletim."
        )
    if bases_em_falta:
        anos = ", ".join(str(a) for a in bases_em_falta)
        avisos.append(f"Sem comparação com {anos}: cubos de referência em falta.")
    return avisos


def executar(raiz: Path, saida: Path, *, descarregar: bool, guardar_cubos_em: Path | None) -> None:
    pastas = recolha.Pastas.omissao(raiz)
    with httpx.Client(timeout=httpx.Timeout(60.0, read=300.0), follow_redirects=True) as cliente:
        d_boletins = recolha.obter(
            recolha.url_boletins(ANO), pastas, cliente, descarregar_=descarregar
        )
        d_eleitores = recolha.obter(URL_ELEITORES, pastas, cliente, descarregar_=descarregar)
        d_historico = recolha.obter(URL_HISTORICO, pastas, cliente, descarregar_=descarregar)

    registados = recolha.recenseamento_atual(d_eleitores.caminho, pastas, ANO)
    historico = recolha.historico(d_historico.caminho, pastas)
    distritos = registados.select("ncid", pl.col("distrito").alias("distrito_atual"))
    atual = processar_ano(
        ANO,
        caminho_boletins=d_boletins.caminho,
        registados=registados,
        historico=historico,
        distrito_atual=distritos,
    )
    if atual.dados_ate is None:
        msg = "O ficheiro de boletins de 2026 ainda não tem votos devolvidos"
        raise RuntimeError(msg)
    if guardar_cubos_em is not None:
        guardar_cubos(atual.cubos, guardar_cubos_em)

    bases: list[CubosAno] = []
    em_falta: list[int] = []
    for ano in ANOS_BASE:
        if caminho_cubo(pastas.referencia, "demografico", ano).exists():
            bases.append(ler_cubos(pastas.referencia, ano))
        else:
            em_falta.append(ano)
    dias = eleicao_nc(ANO).dias_antes(atual.dados_ate)
    relatorio = montar(
        estado=CodigoEstado.NC,
        atual=atual.cubos,
        bases=bases,
        dados_ate=atual.dados_ate,
        fontes=[recolha.fonte(d) for d in (d_boletins, d_eleitores, d_historico)],
        nomes_condados=codigos.NOME_CONDADO,
        avisos=avisos_automaticos(
            dias_antes=dias,
            ano=ANO,
            sem_recenseamento=atual.votantes_sem_recenseamento,
            bases_em_falta=em_falta,
        ),
    )
    saida.parent.mkdir(parents=True, exist_ok=True)
    saida.write_text(relatorio.model_dump_json(), encoding="utf-8")
    registo.info(
        "Escrito %s: dados até %s (%s dias antes), %s votos",
        saida,
        atual.dados_ate,
        dias,
        relatorio.ciclos[0].votos_antecipados,
    )


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--raiz", type=Path, default=Path.cwd(), help="raiz do repositório")
    parser.add_argument("--saida", type=Path, required=True, help="ficheiro JSON a escrever")
    parser.add_argument("--sem-descarga", action="store_true", help="usar só ficheiros locais")
    parser.add_argument(
        "--cubos", type=Path, default=None, help="pasta onde guardar os cubos de 2026"
    )
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    executar(args.raiz, args.saida, descarregar=not args.sem_descarga, guardar_cubos_em=args.cubos)


if __name__ == "__main__":
    main()
