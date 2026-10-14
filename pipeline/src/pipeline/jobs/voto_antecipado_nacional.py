"""Junta os ficheiros publicados de cada estado no resumo nacional.

Uso::

    uv run python -m pipeline.jobs.voto_antecipado_nacional --pasta data/publicado/voto-antecipado

Lê todos os ``<estado>.json`` da pasta, valida-os contra o contrato do estado e escreve
``nacional.json`` na mesma pasta. Um ficheiro inválido falha a execução: nunca se publica
um resumo construído a partir de dados que não passaram na validação.
"""

import argparse
import csv
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
MARGENS = Path("data/reference/modelo/presidencial_condados_2024.csv")
"""Margem presidencial de 2024 (D-R) por condado, a referência do Modelo C."""


def ler_margens(caminho: Path) -> dict[str, float]:
    if not caminho.exists():
        registo.warning("Sem %s: o resumo sai sem o sinal por condado", caminho)
        return {}
    with caminho.open(encoding="utf-8") as f:
        return {linha["fips"]: float(linha["margem"]) for linha in csv.DictReader(f)}


def executar(pasta: Path, margens_csv: Path = MARGENS) -> Path:
    margens = ler_margens(margens_csv)
    linhas: list[LinhaEstadoNacional] = []
    fontes: list[Fonte] = []
    for caminho in sorted(pasta.glob("*.json")):
        if caminho.name == NOME:
            continue
        dados = json.loads(caminho.read_text(encoding="utf-8"))
        if "granularidade" in dados:
            agregado = VotoAntecipadoAgregado.model_validate(dados)
            linhas.append(nacional.linha_agregado(agregado, caminho.name, margens))
            fontes.extend(agregado.metadados.fontes)
        else:
            completo = VotoAntecipadoEstado.model_validate(dados)
            linhas.append(nacional.linha_completo(completo, caminho.name, margens))
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
    parser.add_argument("--margens", type=Path, default=MARGENS)
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    executar(args.pasta, args.margens)


if __name__ == "__main__":
    main()
