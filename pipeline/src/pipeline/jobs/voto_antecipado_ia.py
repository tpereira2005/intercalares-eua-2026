"""Atualiza o voto antecipado do Iowa (relatórios diários do Secretary of State).

Uso::

    uv run python -m pipeline.jobs.voto_antecipado_ia --saida data/publicado/voto-antecipado/ia.json
    uv run python -m pipeline.jobs.voto_antecipado_ia --referencia 2022 2024

A fonte publica, para cada eleição, PDF cumulativos com um relatório por dia (ver
``pipeline.connectors.early_vote.ia``). O PDF por distrito do Congresso dá a série, a
comparação e a geografia por distrito; o PDF por condado, só o mapa do último dia. Os
anos de referência ficam em ``data/reference/ia/retratos_<ano>.csv`` (totais por dia,
distrito, partido e tipo), lidos dos PDF finais de 2022 e 2024.

Enquanto o PDF de 2026 não existir, o job avisa e termina sem escrever nada.
"""

import argparse
import logging
from datetime import UTC, date, datetime
from pathlib import Path

import httpx
import polars as pl

from contratos.base import Fonte
from contratos.estados import CodigoEstado
from contratos.voto_antecipado_agregado import LinhaGeografiaAgregada, VotoAntecipadoAgregado
from pipeline.comum.calendario import EleicaoGeral, eleicao_geral
from pipeline.comum.condados import nomes
from pipeline.comum.descarga import Descarga, descarregar
from pipeline.comum.erros import ErroDescarga, ErroFormatoFonte
from pipeline.connectors.early_vote.ia import fontes
from pipeline.connectors.early_vote.ia.fontes import Nivel
from pipeline.connectors.early_vote.ia.ler import ler_relatorios
from pipeline.transform.early_vote import agregado
from pipeline.transform.early_vote.indicadores import com_total

registo = logging.getLogger(__name__)

ANO = 2026
ANOS_BASE = (2022, 2024)
NOTAS = {2024: ("Eleição presidencial: comparar sobretudo o ritmo, não o nível.",)}
ESQUEMA_REFERENCIA = {
    "dados_ate": pl.Date,
    "distrito": pl.Int8,
    "partido": pl.String,
    "tipo": pl.String,
    "n": pl.Int64,
}
AVISOS = (
    "O Iowa publica totais por distrito, condado e partido de registo, sem idade.",
    "Os pedidos incluem quem pede e vota logo no balcão do condado; os pendentes são "
    "boletins emitidos e ainda não recebidos.",
    "Presencial: balcão do auditor do condado e locais satélite. Correio: correio, caixas "
    "de depósito, lares e hospitais, e boletins enviados por e-mail ou fax.",
)


def eleicao(ano: int) -> EleicaoGeral:
    return eleicao_geral("IA", ano, NOTAS.get(ano, ()))


def pasta(raiz: Path, tipo: str) -> Path:
    return raiz / "data" / tipo / "ia"


def obter(nivel: Nivel, ano: int, raiz: Path, cliente: httpx.Client | None) -> Descarga:
    url = fontes.url(ano, nivel)
    destino = pasta(raiz, "brutos") / url.rsplit("/", 1)[-1]
    if cliente is None:
        if not destino.exists():
            msg = f"{destino} não existe; corre sem --sem-descarga"
            raise FileNotFoundError(msg)
        obtido = datetime.fromtimestamp(destino.stat().st_mtime, tz=UTC)
        return Descarga(url, destino, False, None, None, obtido)
    return descarregar(url, destino, cliente=cliente)


def distritos(retratos: pl.DataFrame) -> pl.DataFrame:
    """Retratos do PDF por distrito no esquema de referência (distrito como número)."""
    return retratos.select(
        "dados_ate", pl.col("unidade").cast(pl.Int8).alias("distrito"), "partido", "tipo", "n"
    )


def referencia(raiz: Path, anos: list[int], *, descarregar_: bool) -> None:
    destino = pasta(raiz, "reference")
    destino.mkdir(parents=True, exist_ok=True)
    with httpx.Client(timeout=httpx.Timeout(60.0, read=600.0), follow_redirects=True) as cliente:
        for ano in anos:
            d = obter("distrito", ano, raiz, cliente if descarregar_ else None)
            tabela = distritos(ler_relatorios(d.caminho, "distrito"))
            caminho = destino / f"retratos_{ano}.csv"
            tabela.write_csv(caminho)
            registo.info("Escrito %s: %s relatórios", caminho, tabela["dados_ate"].n_unique())


def ler_referencia(raiz: Path, ano: int) -> pl.DataFrame | None:
    caminho = pasta(raiz, "reference") / f"retratos_{ano}.csv"
    if not caminho.exists():
        return None
    return pl.read_csv(caminho, schema=ESQUEMA_REFERENCIA)


def geografia_condados(retratos: pl.DataFrame, dados_ate: date) -> list[LinhaGeografiaAgregada]:
    """Votos recebidos por condado e partido no último relatório até ``dados_ate``."""
    dia = retratos.filter(pl.col("dados_ate") <= dados_ate)["dados_ate"].max()
    votos = (
        retratos.filter(
            (pl.col("dados_ate") == dia) & pl.col("tipo").is_in(["correio", "presencial"])
        )
        .group_by("unidade", "partido")
        .agg(pl.col("n").sum().alias("votos"))
    )
    nomes_ = nomes("IA")
    return [
        LinhaGeografiaAgregada(
            ano=ANO,
            nivel="condado",
            codigo=x["unidade"],
            nome=nomes_[x["unidade"]],
            partido=x["partido"],
            votos=x["votos"],
        )
        for x in com_total(votos, "partido", ("votos",))
        .sort("unidade", "partido")
        .iter_rows(named=True)
    ]


def montar(
    atual: pl.DataFrame,
    bases: dict[int, pl.DataFrame],
    condados: pl.DataFrame | None,
    fontes_: list[Fonte],
) -> VotoAntecipadoAgregado:
    eleicao_atual = eleicao(ANO)
    dados_ate: date = atual["dados_ate"].max()  # type: ignore[assignment]
    avisos = list(AVISOS)
    em_falta = [a for a in ANOS_BASE if a not in bases]
    if em_falta:
        avisos.append(
            f"Sem comparação com {', '.join(map(str, em_falta))}: retratos de referência em falta."
        )
    publicado = agregado.montar(
        estado=CodigoEstado.IA,
        atual=agregado.cubos_de_retratos(atual, eleicao_atual),
        bases=[agregado.cubos_de_retratos(bases[a], eleicao(a)) for a in ANOS_BASE if a in bases],
        dados_ate=dados_ate,
        dimensoes=("partido", "modalidade", "distrito", "condado"),
        modalidades=("correio", "presencial"),
        fontes=fontes_,
        nomes_condados={},
        avisos=avisos,
        granularidade="condado",
    )
    geo = [g for g in publicado.geografia if g.nivel != "condado"]
    if condados is not None and condados.height:
        geo += geografia_condados(condados, dados_ate)
    return publicado.model_copy(update={"geografia": tuple(geo)})


def _fonte(d: Descarga) -> Fonte:
    return Fonte(nome=fontes.NOME_FONTE, url=d.url, licenca=fontes.LICENCA, obtida_em=d.obtido_em)


def executar(raiz: Path, saida: Path, *, descarregar_: bool) -> bool:
    """Escreve ``saida``; devolve ``False`` (sem escrever) se o PDF de 2026 ainda não existe."""
    bases = {a: t for a in ANOS_BASE if (t := ler_referencia(raiz, a)) is not None}
    # Sem seguir redirecionamentos: um PDF ainda não publicado redireciona para uma página
    # de erro, e o 302 diz isso mesmo.
    with httpx.Client(timeout=httpx.Timeout(60.0, read=600.0)) as cliente:
        try:
            d_distritos = obter("distrito", ANO, raiz, cliente if descarregar_ else None)
            atual = distritos(ler_relatorios(d_distritos.caminho, "distrito"))
        except (ErroDescarga, ErroFormatoFonte, FileNotFoundError) as erro:
            # Antes do primeiro relatório, o endereço redireciona para uma página de erro.
            registo.warning("Iowa: ainda sem relatórios de %s (%s)", ANO, erro)
            return False
        descargas = [d_distritos]
        condados: pl.DataFrame | None = None
        try:
            d_condados = obter("condado", ANO, raiz, cliente if descarregar_ else None)
            condados = ler_relatorios(d_condados.caminho, "condado")
            descargas.append(d_condados)
        except (ErroDescarga, ErroFormatoFonte, FileNotFoundError) as erro:
            registo.warning("Iowa: sem o PDF por condado (%s); o mapa fica de fora", erro)
    publicado = montar(atual, bases, condados, [_fonte(d) for d in descargas])
    saida.parent.mkdir(parents=True, exist_ok=True)
    saida.write_text(publicado.model_dump_json(), encoding="utf-8")
    registo.info(
        "Escrito %s: dados até %s (%s dias antes), %s votos",
        saida,
        publicado.dados_ate,
        publicado.dias_antes,
        publicado.ciclos[0].votos,
    )
    return True


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--raiz", type=Path, default=Path.cwd(), help="raiz do repositório")
    parser.add_argument("--saida", type=Path, help="ficheiro JSON a escrever")
    parser.add_argument(
        "--referencia", type=int, nargs="+", help="reconstruir os retratos destes anos"
    )
    parser.add_argument("--sem-descarga", action="store_true", help="usar só ficheiros locais")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    if args.referencia:
        referencia(args.raiz, args.referencia, descarregar_=not args.sem_descarga)
    if args.saida:
        executar(args.raiz, args.saida, descarregar_=not args.sem_descarga)


if __name__ == "__main__":
    main()
