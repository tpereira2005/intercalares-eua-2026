"""Atualiza o voto antecipado de um estado com boletins mas sem recenseados por grupo.

Uso::

    uv run python -m pipeline.jobs.voto_antecipado_estado --estado PA --saida data/publicado/pa.json

Descarrega o ficheiro de 2026 com pedido condicional, constrói os cubos e compara-os com os
cubos dos anos de referência em ``data/reference/<estado>`` (ver
``pipeline.jobs.referencia_voto_antecipado_estado``).
"""

import argparse
import json
import logging
import sys
from datetime import UTC, date, datetime
from pathlib import Path
from typing import cast

import httpx

from contratos.base import Fonte
from contratos.estados import CodigoEstado
from pipeline.comum.descarga import Descarga, descarregar
from pipeline.comum.erros import ErroDescarga
from pipeline.connectors.early_vote.agregados import (
    CONECTORES,
    ConectorAgregado,
    gerado_em,
    ultimo_dia_completo,
)
from pipeline.transform.early_vote import agregado, persistir

registo = logging.getLogger(__name__)

ANO = 2026


def obter(
    conector: ConectorAgregado, url: str, ano: int, raiz: Path, cliente: httpx.Client | None
) -> Descarga:
    destino = conector.pasta(raiz, "brutos") / f"boletins_{ano}.txt"
    if cliente is None:
        if not destino.exists():
            msg = f"{destino} não existe; corre sem --sem-descarga"
            raise FileNotFoundError(msg)
        return Descarga(url, destino, False, None, None, gerado_em_local(destino))
    descarga = descarregar(url, destino, cliente=cliente)
    registo.info(
        "%s %s: %s", conector.estado, ano, "novo" if descarga.alterado else "sem alterações"
    )
    return descarga


def copia_anterior(conector: ConectorAgregado, ano: int, raiz: Path) -> Descarga | None:
    """A última descarga bem-sucedida (restaurada da cache do Actions), se existir."""
    destino = conector.pasta(raiz, "brutos") / f"boletins_{ano}.txt"
    meta = destino.with_name(destino.name + ".meta.json")
    if not (destino.exists() and meta.exists()):
        return None
    dados = json.loads(meta.read_text(encoding="utf-8"))
    return Descarga(
        str(dados["url"]),
        destino,
        False,
        dados.get("etag"),
        dados.get("last_modified"),
        datetime.fromisoformat(str(dados["obtido_em"])),
    )


def recolher(
    conector: ConectorAgregado, raiz: Path, cliente: httpx.Client
) -> tuple[Descarga, str | None]:
    """Descarrega o ficheiro de 2026. Quando a fonte recusa o pedido ou está em baixo (403,
    5xx, rede, desafio anti-robô), usa a cópia da última recolha e devolve um aviso para o
    ficheiro publicado: os números ficam como estavam, com a data certa, e a recolha não
    insiste nem tenta contornar o bloqueio. Sem cópia anterior, o erro sobe."""
    try:
        url = conector.url_atual(cliente)
        return obter(conector, url, ANO, raiz, cliente), None
    except (httpx.HTTPError, ErroDescarga) as erro:
        anterior = copia_anterior(conector, ANO, raiz)
        if anterior is None:
            raise
        registo.warning("%s: fonte indisponível (%s); uso a última recolha", conector.estado, erro)
        quando = anterior.obtido_em.astimezone(UTC)
        anotacao = (
            f"::warning title=Voto antecipado {conector.estado}::Fonte indisponível ({erro}); "
            f"publicados os números da recolha de {quando:%d/%m %H:%M} UTC."
        )
        # Fica visível no resumo do workflow, sem pôr a execução a vermelho.
        print(anotacao, file=sys.stderr)  # noqa: T201
        aviso = (
            f"A fonte oficial não respondeu ao último pedido; os números são da recolha de "
            f"{quando.day}/{quando.month} às {quando:%H:%M} UTC."
        )
        return anterior, aviso


def gerado_em_local(caminho: Path) -> datetime:
    return datetime.fromtimestamp(caminho.stat().st_mtime, tz=UTC)


def fonte(conector: ConectorAgregado, descarga: Descarga) -> Fonte:
    return Fonte.model_validate(
        {
            "nome": conector.nome_fonte,
            "url": descarga.url,
            "licenca": conector.licenca,
            "obtida_em": descarga.obtido_em,
        }
    )


def executar(estado: CodigoEstado, raiz: Path, saida: Path, *, descarregar_: bool) -> None:
    conector = CONECTORES[estado]
    eleicao = conector.eleicao(ANO)
    aviso_fonte: str | None = None
    if descarregar_:
        with httpx.Client(
            timeout=httpx.Timeout(60.0, read=600.0), follow_redirects=True
        ) as cliente:
            descarga, aviso_fonte = recolher(conector, raiz, cliente)
    else:
        descarga = obter(conector, "https://exemplo.invalid/local", ANO, raiz, None)
    boletins, relatorio = conector.ler(descarga.caminho, eleicao)
    if relatorio.linhas_invalidas:
        registo.warning("%s: %s linhas inválidas ignoradas", estado, relatorio.linhas_invalidas)
    maximo = cast("date | None", boletins["data_devolucao"].max())
    dados_ate = ultimo_dia_completo(maximo, gerado_em(descarga))
    if dados_ate is None:
        msg = f"{estado}: o ficheiro de 2026 ainda não tem boletins devolvidos"
        raise RuntimeError(msg)

    referencia = conector.pasta(raiz, "reference")
    bases = [
        persistir.ler(referencia, conector.eleicao(ano))
        for ano in conector.anos_base
        if persistir.existe(referencia, ano)
    ]
    em_falta = [ano for ano in conector.anos_base if not persistir.existe(referencia, ano)]
    avisos = list(conector.avisos)
    if aviso_fonte:
        avisos.append(aviso_fonte)
    if em_falta:
        avisos.append(
            f"Sem comparação com {', '.join(map(str, em_falta))}: cubos de referência em falta."
        )
    relatorio_publicado = agregado.montar(
        estado=estado,
        atual=agregado.cubos(boletins, eleicao),
        bases=bases,
        dados_ate=dados_ate,
        dimensoes=conector.dimensoes,
        modalidades=conector.modalidades,
        fontes=[fonte(conector, descarga)],
        nomes_condados=conector.nomes_condados,
        avisos=avisos,
    )
    saida.parent.mkdir(parents=True, exist_ok=True)
    saida.write_text(relatorio_publicado.model_dump_json(), encoding="utf-8")
    registo.info(
        "Escrito %s: dados até %s (%s dias antes), %s votos",
        saida,
        dados_ate,
        relatorio_publicado.dias_antes,
        relatorio_publicado.ciclos[0].votos,
    )


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--estado", required=True, choices=[e.value for e in CONECTORES])
    parser.add_argument("--raiz", type=Path, default=Path.cwd(), help="raiz do repositório")
    parser.add_argument("--saida", type=Path, required=True, help="ficheiro JSON a escrever")
    parser.add_argument("--sem-descarga", action="store_true", help="usar só ficheiros locais")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    executar(CodigoEstado(args.estado), args.raiz, args.saida, descarregar_=not args.sem_descarga)


if __name__ == "__main__":
    main()
