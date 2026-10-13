"""Tabelas de referência do modelo, versionadas em ``data/reference/modelo/``.

As páginas da Wikipedia mudam; para que os backtests sejam reprodutíveis, guardamos o que
lemos de cada ano já terminado (corridas e sondagens) em ficheiros pequenos e legíveis.
Só o ano corrente (2026) é lido de novo a cada execução.
"""

import csv
import json
from dataclasses import asdict
from datetime import date
from pathlib import Path

from pipeline.modelo.fontes.corridas import Candidato, Corrida
from pipeline.modelo.fontes.sondagens import Sondagem

PASTA = Path("data/reference/modelo")
CAMPOS_SONDAGEM = (
    "corrida", "ano", "instituto", "fim", "amostra", "populacao", "partidaria", "dem", "rep",
    "candidato_d", "candidato_r",
)  # fmt: skip


def gravar_corridas(corridas: list[Corrida], caminho: Path) -> None:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    dados = [
        {
            "ano": c.ano,
            "camara": c.camara,
            "estado": c.estado,
            "distrito": c.distrito,
            "pvi": c.pvi,
            "incumbentes": [list(i) for i in c.incumbentes],
            "candidatos": [asdict(k) for k in c.candidatos],
            "estado_texto": c.estado_texto,
        }
        for c in sorted(corridas, key=lambda c: (c.camara, c.estado, c.distrito))
    ]
    caminho.write_text(json.dumps(dados, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


def ler_corridas(caminho: Path) -> list[Corrida]:
    dados = json.loads(caminho.read_text(encoding="utf-8"))
    return [
        Corrida(
            ano=d["ano"],
            camara=d["camara"],
            estado=d["estado"],
            distrito=d["distrito"],
            pvi=d["pvi"],
            incumbentes=[(i[0], i[1]) for i in d["incumbentes"]],
            candidatos=[Candidato(**k) for k in d["candidatos"]],
            estado_texto=d["estado_texto"],
        )
        for d in dados
    ]


def gravar_sondagens(sondagens: list[Sondagem], caminho: Path) -> None:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    ordenadas = sorted(sondagens, key=lambda s: (s.ano, s.corrida, s.fim, s.instituto))
    with caminho.open("w", encoding="utf-8", newline="") as f:
        escritor = csv.writer(f, lineterminator="\n")
        escritor.writerow(CAMPOS_SONDAGEM)
        for s in ordenadas:
            escritor.writerow(
                [
                    s.corrida, s.ano, s.instituto, s.fim.isoformat(), s.amostra or "",
                    s.populacao, int(s.partidaria), f"{s.dem:g}", f"{s.rep:g}",
                    s.candidato_d, s.candidato_r,
                ]
            )  # fmt: skip


def ler_sondagens(caminho: Path) -> list[Sondagem]:
    with caminho.open(encoding="utf-8", newline="") as f:
        return [
            Sondagem(
                corrida=r["corrida"],
                ano=int(r["ano"]),
                instituto=r["instituto"],
                fim=date.fromisoformat(r["fim"]),
                amostra=int(r["amostra"]) if r["amostra"] else None,
                populacao=r["populacao"],
                partidaria=r["partidaria"] == "1",
                dem=float(r["dem"]),
                rep=float(r["rep"]),
                candidato_d=r["candidato_d"],
                candidato_r=r["candidato_r"],
            )
            for r in csv.DictReader(f)
        ]


def gravar_tabela(linhas: list[dict[str, object]], caminho: Path) -> None:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    with caminho.open("w", encoding="utf-8", newline="") as f:
        escritor = csv.DictWriter(f, fieldnames=list(linhas[0]), lineterminator="\n")
        escritor.writeheader()
        escritor.writerows(linhas)


def ler_tabela(caminho: Path) -> list[dict[str, str]]:
    with caminho.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))
