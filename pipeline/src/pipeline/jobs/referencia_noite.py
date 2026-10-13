"""Grava a eleição de referência por condado usada pelo Modelo C (noite eleitoral).

Uso::

    uv run python -m pipeline.jobs.referencia_noite

Lê os resultados presidenciais por condado de 2020 e 2024 compilados por Tony McGovern
(github.com/tonmcg/US_County_Level_Election_Results_08-24, licença MIT) e grava em
``data/reference/modelo/presidencial_condados_<ano>.csv`` uma linha por condado com o
estado, o FIPS, os votos totais e a margem D-R em pontos. A noite de 2026 usa 2024; as
repetições de 2022 e 2024 usam 2020 (a presidencial anterior a cada uma).
"""

import csv
import io
import logging
from pathlib import Path

import httpx

from pipeline.comum.condados import estado_do_fips
from pipeline.comum.descarga import USER_AGENT
from pipeline.comum.erros import ErroFormatoFonte

registo = logging.getLogger(__name__)

URL = (
    "https://raw.githubusercontent.com/tonmcg/US_County_Level_Election_Results_08-24/"
    "master/{ano}_US_County_Level_Presidential_Results.csv"
)
PASTA = Path("data/reference/modelo")
ANOS = (2020, 2024)


def converter(texto: str) -> list[dict[str, str]]:
    linhas: list[dict[str, str]] = []
    for r in csv.DictReader(io.StringIO(texto)):
        fips = r["county_fips"].strip().zfill(5)
        total = int(float(r["total_votes"]))
        if total <= 0:
            continue
        estado = estado_do_fips(fips)
        if estado is None:
            raise ErroFormatoFonte(f"FIPS desconhecido: {fips}")
        margem = 100.0 * (float(r["votes_dem"]) - float(r["votes_gop"])) / total
        linhas.append(
            {"estado": estado, "fips": fips, "votos": str(total), "margem": f"{margem:.2f}"}
        )
    if len(linhas) < 3000:
        raise ErroFormatoFonte(f"Só {len(linhas)} condados")
    return sorted(linhas, key=lambda r: r["fips"])


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    with httpx.Client(headers={"User-Agent": USER_AGENT}, timeout=60.0) as cliente:
        for ano in ANOS:
            resposta = cliente.get(URL.format(ano=ano))
            resposta.raise_for_status()
            linhas = converter(resposta.text)
            destino = PASTA / f"presidencial_condados_{ano}.csv"
            with destino.open("w", encoding="utf-8", newline="") as ficheiro:
                escritor = csv.DictWriter(
                    ficheiro, fieldnames=["estado", "fips", "votos", "margem"], lineterminator="\n"
                )
                escritor.writeheader()
                escritor.writerows(linhas)
            registo.info("%d condados gravados em %s", len(linhas), destino)


if __name__ == "__main__":
    main()
