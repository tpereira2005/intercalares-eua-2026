"""Junta os ficheiros publicados de cada estado no resumo nacional.

Uso::

    uv run python -m pipeline.jobs.voto_antecipado_nacional --pasta data/publicado/voto-antecipado

Lê todos os ``<estado>.json`` da pasta, valida-os contra o contrato do estado e escreve
``nacional.json`` na mesma pasta. Um ficheiro inválido falha a execução: nunca se publica
um resumo construído a partir de dados que não passaram na validação.
"""

import argparse
import json
import logging
from pathlib import Path

from contratos.base import Fonte
from contratos.voto_antecipado import VotoAntecipadoEstado
from contratos.voto_antecipado_agregado import LinhaEstadoNacional, VotoAntecipadoAgregado
from pipeline.transform.early_vote import nacional

registo = logging.getLogger(__name__)

NOME = "nacional.json"
ANO = 2026


def executar(pasta: Path) -> Path:
    linhas: list[LinhaEstadoNacional] = []
    fontes: list[Fonte] = []
    for caminho in sorted(pasta.glob("*.json")):
        if caminho.name == NOME:
            continue
        dados = json.loads(caminho.read_text(encoding="utf-8"))
        if "granularidade" in dados:
            agregado = VotoAntecipadoAgregado.model_validate(dados)
            linhas.append(nacional.linha_agregado(agregado, caminho.name))
            fontes.extend(agregado.metadados.fontes)
        else:
            completo = VotoAntecipadoEstado.model_validate(dados)
            linhas.append(nacional.linha_completo(completo, caminho.name))
            fontes.extend(completo.metadados.fontes)
    if not linhas:
        msg = f"Nenhum ficheiro de estado em {pasta}"
        raise RuntimeError(msg)
    resumo = nacional.montar(linhas, fontes, ano=ANO)
    saida = pasta / NOME
    saida.write_text(resumo.model_dump_json(), encoding="utf-8")
    registo.info("Escrito %s: %s estados, %s votos", saida, len(linhas), resumo.votos)
    return saida


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--pasta", type=Path, required=True)
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    executar(args.pasta)


if __name__ == "__main__":
    main()
