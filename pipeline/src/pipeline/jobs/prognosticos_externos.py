"""Recolhe as classificações de outros prognosticadores para o Senado e a Câmara.

Uso::

    uv run python -m pipeline.jobs.prognosticos_externos --saida prognosticos-2026.json

Lê as tabelas de classificações da Wikipedia (Cook, Inside Elections, Sabato, The
Economist...) e publica um ``PrognosticosExternos``. A partir do dia do congelamento da
previsão (``corte_final``), o ficheiro sai marcado como congelado: é essa versão que se
compara com os resultados.
"""

import argparse
import logging
from datetime import datetime
from pathlib import Path
from urllib.parse import quote

import httpx

from contratos.base import Fonte, Metadados
from contratos.prognosticos import Prognosticador, PrognosticosExternos
from pipeline.connectors.prognosticos import (
    PAGINA_CAMARA,
    PAGINA_SENADO,
    Tabela,
    agora_utc,
    ler_camara,
    ler_senado,
)
from pipeline.modelo import carregar as carga
from pipeline.modelo.fontes import wikipedia
from pipeline.modelo.previsao import corte_final

registo = logging.getLogger(__name__)

ANO = 2026


def _url(titulo: str) -> str:
    return f"https://en.wikipedia.org/wiki/{quote(titulo.replace(' ', '_'))}"


def _prognosticadores(tabela: Tabela) -> tuple[Prognosticador, ...]:
    return tuple(
        Prognosticador.model_validate(
            {"chave": c.chave, "nome": c.nome, "data": c.data, "url": c.url}
        )
        for c in tabela.colunas
    )


def construir(senado: str, camara: str, agora: datetime) -> PrognosticosExternos:
    """Monta o ficheiro a partir do wikitexto das duas páginas."""
    tabela_senado = ler_senado(senado)
    tabela_camara = ler_camara(camara)
    fontes = tuple(
        Fonte.model_validate(
            {
                "nome": f"Wikipedia, {titulo}",
                "url": _url(titulo),
                "licenca": "CC BY-SA 4.0",
                "obtida_em": agora,
            }
        )
        for titulo in (PAGINA_SENADO, PAGINA_CAMARA)
    )
    return PrognosticosExternos(
        metadados=Metadados(gerado_em=agora, fontes=fontes),
        ano=ANO,
        recolhido_em=agora,
        congelado=agora.date() >= corte_final(ANO),
        prognosticadores_senado=_prognosticadores(tabela_senado),
        prognosticadores_camara=_prognosticadores(tabela_camara),
        senado=tabela_senado.corridas,
        camara=tabela_camara.corridas,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    parser.add_argument("--saida", type=Path, required=True)
    parser.add_argument("--sem-descarga", action="store_true", help="usa só a cache local")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    with httpx.Client(
        headers={"User-Agent": wikipedia.USER_AGENT}, timeout=60.0, follow_redirects=True
    ) as cliente:
        textos = [
            wikipedia.obter(titulo, carga.CACHE, atualizar=not args.sem_descarga, cliente=cliente)
            for titulo in (PAGINA_SENADO, PAGINA_CAMARA)
        ]
    dados = construir(textos[0], textos[1], agora_utc())
    registo.info(
        "%d corridas do Senado e %d distritos da Câmara%s",
        len(dados.senado),
        len(dados.camara),
        " (congelado)" if dados.congelado else "",
    )
    args.saida.parent.mkdir(parents=True, exist_ok=True)
    args.saida.write_text(dados.model_dump_json() + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
