"""Acrescenta, substitui ou apaga uma corrida em ``manual.json`` (resultados à mão).

Uso (o workflow **Resultado manual** faz isto a partir do formulário do GitHub)::

    uv run python -m pipeline.jobs.resultado_manual --ficheiro manual.json --corrida PA-S \\
        --candidatos "Bob Casey (D): 1.234.567; Dave McCormick (R): 1.200.000; Outros: 30.000" \\
        --apuramento 87% --fonte https://www.electionreturns.pa.gov/

``--candidatos``: ``Nome (D|R|O): votos``, separados por ``;``. Os votos aceitam pontos,
vírgulas ou espaços como separadores de milhares. ``Outros`` sem partido conta como
``outro``. ``--apuramento``: ``87%`` (percentagem da página) ou ``1234/2000`` (secções).

Valida tudo antes de escrever: um erro deixa o ficheiro como estava. Recusa estados com
fonte estadual automática, onde os números vêm da fonte aberta; no Texas e no Arizona
(só alguns condados automáticos) a entrada manual substitui esses condados na corrida.
"""

import argparse
import re
import sys
from datetime import UTC, datetime
from pathlib import Path

from pydantic import ValidationError

from contratos.estados import CodigoEstado
from pipeline.connectors.results.manual import (
    ESCALA_PERCENTAGEM,
    CandidatoManual,
    EntradaManual,
    FicheiroManual,
    aceita_manual,
    ler_ficheiro,
)
from pipeline.connectors.results.registo import CONECTORES

_CANDIDATO = re.compile(
    r"^\s*(?P<nome>.+?)\s*(?:\((?P<partido>[A-Za-z]+)\))?\s*:\s*(?P<votos>[\d.,\s]+)$"
)
_PERCENTAGEM = re.compile(r"^\s*(\d+(?:[.,]\d+)?)\s*%\s*$")
_SECCOES = re.compile(r"^\s*(\d+)\s*/\s*(\d+)\s*$")
PARTIDOS = {"D": "dem", "DEM": "dem", "R": "rep", "REP": "rep"}


class ErroEntrada(ValueError):  # noqa: N818 (nome em português)
    """Valor do formulário que não se consegue interpretar."""


def candidatos(texto: str) -> tuple[CandidatoManual, ...]:
    lista = []
    for parte in filter(str.strip, texto.split(";")):
        m = _CANDIDATO.match(parte)
        if m is None:
            msg = f"Candidato ilegível: {parte.strip()!r} (formato: Nome (D): 123456)"
            raise ErroEntrada(msg)
        partido = PARTIDOS.get((m["partido"] or "").upper(), "outro")
        votos = int(re.sub(r"\D", "", m["votos"]))
        lista.append(CandidatoManual(nome=m["nome"], partido=partido, votos=votos))
    if not lista:
        msg = "Sem candidatos"
        raise ErroEntrada(msg)
    return tuple(lista)


def apuramento(texto: str) -> tuple[int, int, bool]:
    if m := _SECCOES.match(texto):
        return int(m[1]), int(m[2]), True
    if m := _PERCENTAGEM.match(texto):
        valor = float(m[1].replace(",", "."))
        if not 0 <= valor <= 100:
            msg = f"Percentagem fora de 0-100: {texto!r}"
            raise ErroEntrada(msg)
        return round(valor * ESCALA_PERCENTAGEM / 100), ESCALA_PERCENTAGEM, False
    msg = f"Apuramento ilegível: {texto!r} (use 87% ou 1234/2000)"
    raise ErroEntrada(msg)


def atualizar(
    ficheiro: FicheiroManual,
    corrida: str,
    *,
    texto_candidatos: str | None,
    texto_apuramento: str | None,
    fonte: str | None,
    apagar: bool,
    agora: datetime,
) -> tuple[FicheiroManual, list[str]]:
    """Devolve o ficheiro novo e os avisos (ex.: um total que desceu)."""
    corrida = corrida.strip().upper()
    estado = CodigoEstado(corrida[:2])
    if not aceita_manual(CONECTORES.get(estado)):
        msg = f"{estado.value} tem fonte automática; a entrada manual não é usada lá"
        raise ErroEntrada(msg)
    restantes = tuple(e for e in ficheiro.entradas if e.corrida != corrida)
    anterior = next((e for e in ficheiro.entradas if e.corrida == corrida), None)
    if apagar:
        if anterior is None:
            msg = f"{corrida} não está no ficheiro"
            raise ErroEntrada(msg)
        return FicheiroManual(entradas=restantes), []
    if not (texto_candidatos and texto_apuramento and fonte):
        msg = "Faltam candidatos, apuramento ou fonte"
        raise ErroEntrada(msg)
    reportadas, totais, seccoes = apuramento(texto_apuramento)
    nova = EntradaManual(
        corrida=corrida,
        candidatos=candidatos(texto_candidatos),
        reportadas=reportadas,
        totais=totais,
        seccoes=seccoes,
        fonte=fonte,
        introduzido_em=agora,
    )
    avisos = []
    if anterior is not None:
        antes = sum(c.votos for c in anterior.candidatos)
        depois = sum(c.votos for c in nova.candidatos)
        if depois < antes:
            avisos.append(f"{corrida}: o total desceu de {antes} para {depois} (correção?)")
    entradas = tuple(sorted((*restantes, nova), key=lambda e: e.corrida))
    return FicheiroManual(entradas=entradas), avisos


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--ficheiro", type=Path, required=True)
    parser.add_argument("--corrida", required=True, help="ex.: PA-S, MI-G, PA-07")
    parser.add_argument("--candidatos")
    parser.add_argument("--apuramento")
    parser.add_argument("--fonte", help="página oficial de onde se copiaram os números")
    parser.add_argument("--apagar", action="store_true")
    args = parser.parse_args(argv)
    try:
        atual = ler_ficheiro(args.ficheiro) if args.ficheiro.exists() else FicheiroManual()
        novo, avisos = atualizar(
            atual,
            args.corrida,
            texto_candidatos=args.candidatos,
            texto_apuramento=args.apuramento,
            fonte=args.fonte,
            apagar=args.apagar,
            agora=datetime.now(UTC),
        )
    except (ErroEntrada, ValidationError, ValueError) as erro:
        print(f"::error::{erro}", file=sys.stderr)  # noqa: T201
        return 1
    for aviso in avisos:
        print(f"::warning::{aviso}", file=sys.stderr)  # noqa: T201
    temporario = args.ficheiro.with_name(args.ficheiro.name + ".parcial")
    temporario.write_text(novo.model_dump_json(indent=2), encoding="utf-8")
    temporario.replace(args.ficheiro)
    for e in novo.entradas:
        total = sum(c.votos for c in e.candidatos)
        print(f"{e.corrida}: {total} votos, {e.reportadas}/{e.totais}")  # noqa: T201
    return 0


if __name__ == "__main__":
    sys.exit(main())
