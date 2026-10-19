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

O Nevada é conferido com a página agregada de afluência presencial do Clark County (Las Vegas,
fonte oficial, só totais por dia): se estiver acessível, o ``nv.json`` ganha essa fonte e um
aviso com a contagem oficial; se falhar, publica-se como antes, só com um aviso no registo.
"""

import argparse
import logging
import sys
from datetime import UTC, date, datetime
from pathlib import Path

import polars as pl

from contratos.base import Fonte, Metadados
from contratos.estados import CodigoEstado
from contratos.voto_antecipado_agregado import (
    CicloAgregado,
    DimensaoAgregada,
    LinhaPedidos,
    PontoSerieAgregado,
    VotoAntecipadoAgregado,
)
from pipeline.comum.calendario import eleicao_geral
from pipeline.comum.descarga import descarregar
from pipeline.comum.erros import ErroFormatoFonte
from pipeline.connectors.early_vote.clark import fontes as fontes_clark
from pipeline.connectors.early_vote.clark.ler import ler_afluencia
from pipeline.connectors.early_vote.uf import fontes
from pipeline.connectors.early_vote.uf.estados import ESTADOS, OFICIAIS, EstadoUF
from pipeline.connectors.early_vote.uf.ler import (
    Retrato,
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
    arquivo: pl.DataFrame,
    cfg: EstadoUF,
    origem: str,
    fontes_: list[Fonte],
    avisos_extra: tuple[str, ...] = (),
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
    soma = atual["correio"] + atual["presencial"]
    if soma != atual["votos"]:
        avisos.append(
            f"A fonte dá {_milhares(atual['votos'])} votos no total, mas o correio e o "
            f"presencial somam {_milhares(soma)}; mostramos os números tal como vêm."
        )
    if origem:
        avisos.append(f"Origem indicada pela fonte: {origem}.")
    avisos.extend(avisos_extra)
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


def _milhares(valor: int) -> str:
    """Milhares com espaço sem quebra, como o ``Intl`` em ``pt-PT`` (23 183)."""
    return f"{valor:,}".replace(",", "\u00a0")


def conferir_nevada(
    raiz: Path, nevada: Retrato, *, descarregar_: bool
) -> tuple[Fonte, tuple[str, ...]] | None:
    """Fonte oficial e avisos do Nevada a partir da página agregada de Clark County.

    Nunca levanta: se a descarga ou a leitura falhar, regista um aviso e devolve ``None``
    (sem descarga, lê a cópia local se existir). Só se leem totais agregados.
    """
    caminho = raiz / "data" / "brutos" / "clark" / "evturnout.html"
    obtida_em = datetime.now(UTC)
    try:
        if descarregar_:
            obtida_em = descarregar(fontes_clark.URL, caminho).obtido_em
        elif not caminho.exists():
            return None
        afluencia = ler_afluencia(caminho.read_text(encoding="utf-8"))
    except Exception as erro:  # a conferência nunca pode travar o job
        registo.warning("Clark County: conferência do Nevada indisponível (%s)", erro)
        return None
    dia = afluencia.ultimo_dia
    aviso = (
        f"Conferência oficial: o Clark County (Las Vegas) conta {_milhares(afluencia.acumulado)} "
        f"votos presenciais até {dia.day}/{dia.month}, segundo a página oficial do condado."
    )
    if afluencia.acumulado > nevada.presencial:
        aviso += (
            " O total presencial do estado ainda não os inclui todos, por isso fica abaixo do real."
        )
    fonte = Fonte(
        nome=fontes_clark.NOME_FONTE,
        url=fontes_clark.URL,
        licenca=fontes_clark.LICENCA,
        obtida_em=obtida_em,
        oficial=True,
    )
    return fonte, (aviso,)


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
    texto = caminho.read_text(encoding="utf-8")
    retratos: list[Retrato] = []
    erros: list[ErroFormatoFonte] = []
    # Cada estado valida-se sozinho: um estado que falha fica com o último ficheiro publicado
    # e não impede os outros. Se todos falharem, o formato mudou e nada se publica.
    for estado in sorted(ESTADOS, key=lambda e: e.value):
        try:
            retratos.extend(ler_csv(texto, [estado], ANO))
        except ErroFormatoFonte as erro:
            erros.append(erro)
            aviso = f"::warning::{erro}; {estado.value} fica com o último ficheiro publicado"
            print(aviso, file=sys.stderr)  # noqa: T201
    if erros and len(erros) == len(ESTADOS):
        raise erros[0]
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
        fontes_estado = [fonte]
        avisos_extra: tuple[str, ...] = ()
        if retrato.estado is CodigoEstado.NV:
            conferencia = conferir_nevada(raiz, retrato, descarregar_=descarregar_)
            if conferencia is not None:
                fontes_estado.append(conferencia[0])
                avisos_extra = conferencia[1]
        publicado = montar(
            do_estado, ESTADOS[retrato.estado], retrato.origem, fontes_estado, avisos_extra
        )
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
