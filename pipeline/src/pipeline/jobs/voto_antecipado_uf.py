"""Atualiza o voto antecipado dos estados que bloqueiam a recolha, via UF Election Lab.

Uso::

    uv run python -m pipeline.jobs.voto_antecipado_uf --pasta data/publicado/voto-antecipado \\
        --arquivo data/publicado/voto-antecipado/historico-uf-2026.csv

Um só pedido ao ``US.csv`` do UF Election Lab (Universidade da Florida) por execução, com o
User-Agent do projeto e cabeçalhos condicionais. Escreve ``<estado>.json`` na pasta para
cada estado de :data:`pipeline.connectors.early_vote.uf.estados.ESTADOS` que já tenha votos;
os outros ficam sem ficheiro. A fonte só publica o retrato do momento: cada execução
acrescenta-o ao ``--arquivo`` (CSV com uma linha por estado e dia), que o workflow guarda na
Release ao lado dos JSON; é desse arquivo que sai a série diária. Fonte não oficial.
"""

import argparse
import logging
from datetime import UTC, date, datetime
from pathlib import Path

import polars as pl

from contratos.base import Fonte, Metadados
from contratos.voto_antecipado_agregado import (
    CicloAgregado,
    DimensaoAgregada,
    LinhaPedidos,
    PontoSerieAgregado,
    VotoAntecipadoAgregado,
)
from pipeline.comum.calendario import eleicao_geral
from pipeline.comum.descarga import descarregar
from pipeline.connectors.early_vote.uf import fontes
from pipeline.connectors.early_vote.uf.estados import ESTADOS, OFICIAIS, EstadoUF
from pipeline.connectors.early_vote.uf.ler import (
    juntar_arquivo,
    ler_arquivo,
    ler_csv,
    para_arquivo,
)
from pipeline.transform.early_vote.indicadores import TOTAL

registo = logging.getLogger(__name__)

ANO = 2026
PARTIDOS = (("dem", "dem"), ("rep", "rep"), ("nao_afiliado", "nao_afiliado"))
AVISOS = (
    "Fonte não oficial: o UF Election Lab (Universidade da Florida, Michael McDonald) "
    "compila os dados que cada estado publica, porque o servidor oficial deste estado "
    "bloqueia pedidos automáticos. Os números podem diferir do relatório oficial.",
    "A fonte dá o retrato do momento e atualiza várias vezes por dia: o último dia pode "
    "estar incompleto. A série diária começa no primeiro retrato que guardámos e não há "
    "comparação com anos anteriores.",
    "A fonte dá a idade em faixas diferentes das do site (18-25, 26-40, 41-65 e mais de 65), "
    "por isso a idade não é publicada.",
)


def serie(arquivo: pl.DataFrame, cfg: EstadoUF, data_eleicao: date) -> list[PontoSerieAgregado]:
    pontos: list[PontoSerieAgregado] = []

    def ponto(dia: date, partido: str, modalidade: str, votos: int) -> PontoSerieAgregado:
        return PontoSerieAgregado(
            ano=ANO,
            dias_antes=(data_eleicao - dia).days,
            faixa=TOTAL,
            partido=partido,
            modalidade=modalidade,
            votos=votos,
        )

    for linha in arquivo.sort("dados_ate").iter_rows(named=True):
        dia = linha["dados_ate"]
        pontos.append(ponto(dia, TOTAL, TOTAL, linha["votos"]))
        for modalidade in cfg.modalidades:
            pontos.append(ponto(dia, TOTAL, modalidade, linha[modalidade]))
        for coluna, partido in PARTIDOS:
            if linha[coluna] is not None:
                pontos.append(ponto(dia, partido, TOTAL, linha[coluna]))
    return pontos


def montar(
    arquivo: pl.DataFrame, cfg: EstadoUF, origem: str, fontes_: list[Fonte]
) -> VotoAntecipadoAgregado:
    """Ficheiro publicado de um estado a partir do seu arquivo de retratos (não vazio)."""
    eleicao = eleicao_geral(cfg.estado.value, ANO)
    atual = arquivo.sort("dados_ate").row(arquivo.height - 1, named=True)
    dados_ate: date = atual["dados_ate"]
    pedidos = atual["pedidos"]
    com_pedidos = pedidos > 0
    dimensoes: list[DimensaoAgregada] = ["modalidade"]
    if atual["dem"] is not None:
        dimensoes.append("partido")

    avisos = list(AVISOS) + list(cfg.avisos)
    if origem:
        avisos.append(f"Origem indicada pela fonte: {origem}.")
    return VotoAntecipadoAgregado(
        metadados=Metadados(gerado_em=datetime.now(UTC), fontes=tuple(fontes_)),
        estado=cfg.estado,
        ano=ANO,
        dados_ate=dados_ate,
        dias_antes=eleicao.dias_antes(dados_ate),
        granularidade="condado",
        dimensoes=tuple(dimensoes),
        modalidades=tuple(cfg.modalidades),
        ciclos=(
            CicloAgregado(
                ano=ANO,
                tipo="intercalar",
                data_eleicao=eleicao.data,
                votos=atual["votos"],
                pedidos=pedidos if com_pedidos else None,
                notas=(),
            ),
        ),
        serie=tuple(serie(arquivo, cfg, eleicao.data)),
        comparacao=(),
        geografia=(),
        pedidos=(
            (
                LinhaPedidos(
                    ano=ANO,
                    faixa=TOTAL,
                    partido=TOTAL,
                    pedidos=pedidos,
                    devolvidos=atual["devolvidos"],
                    pendentes=pedidos - atual["devolvidos"],
                ),
            )
            if com_pedidos
            else ()
        ),
        avisos=tuple(avisos),
    )


def executar(raiz: Path, pasta: Path, arquivo: Path, *, descarregar_: bool) -> dict[str, int]:
    """Escreve ``<estado>.json`` para cada estado com votos e devolve os votos de cada um."""
    sobrepostos = OFICIAIS & ESTADOS.keys()
    if sobrepostos:
        msg = f"Estados com fonte própria não se publicam via UF: {sorted(sobrepostos)}"
        raise RuntimeError(msg)
    caminho = raiz / "data" / "brutos" / "uf" / "US.csv"
    obtida_em = datetime.now(UTC)
    if descarregar_:
        descarga = descarregar(fontes.CSV, caminho)
        obtida_em = descarga.obtido_em
    retratos = ler_csv(caminho.read_text(encoding="utf-8"), ESTADOS.keys(), ANO)
    if not retratos:
        registo.warning("Nenhum estado com votos no ficheiro do UF Election Lab")
        return {}
    completo = juntar_arquivo(ler_arquivo(arquivo), para_arquivo(retratos))
    arquivo.parent.mkdir(parents=True, exist_ok=True)
    completo.write_csv(arquivo)
    fonte = Fonte(
        nome=fontes.NOME_FONTE,
        url=fontes.CSV,
        licenca=fontes.LICENCA,
        obtida_em=obtida_em,
        oficial=False,
    )
    pasta.mkdir(parents=True, exist_ok=True)
    totais: dict[str, int] = {}
    for retrato in retratos:
        do_estado = completo.filter(pl.col("estado") == retrato.estado.value)
        publicado = montar(do_estado, ESTADOS[retrato.estado], retrato.origem, [fonte])
        saida = pasta / f"{retrato.estado.value.lower()}.json"
        saida.write_text(publicado.model_dump_json(), encoding="utf-8")
        totais[retrato.estado.value] = publicado.ciclos[0].votos
        registo.info(
            "Escrito %s: dados até %s, %s votos, arquivo com %s dias",
            saida,
            publicado.dados_ate,
            publicado.ciclos[0].votos,
            do_estado.height,
        )
    return totais


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--raiz", type=Path, default=Path.cwd())
    parser.add_argument("--pasta", type=Path, required=True, help="onde escrever <estado>.json")
    parser.add_argument("--arquivo", type=Path, required=True, help="CSV com os retratos diários")
    parser.add_argument("--sem-descarga", action="store_true")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    executar(args.raiz, args.pasta, args.arquivo, descarregar_=not args.sem_descarga)


if __name__ == "__main__":
    main()
