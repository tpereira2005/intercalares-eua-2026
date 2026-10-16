"""Conector de resultados do estado de Washington.

O Secretary of State publica, para cada eleição, ficheiros CSV em
``results.vote.wa.gov/results/<AAAAMMDD>/export/``. Interessa ``<AAAAMMDD>_congressional.csv``,
com uma linha por candidato e as colunas ``Race``, ``Candidate``, ``Party``, ``Votes``,
``PercentageOfTotalVotes`` e ``JurisdictionName``. O caminho e o nome do ficheiro são em
minúsculas (com maiúsculas o servidor responde com um redirecionamento).

A fonte só publica o total de cada distrito: não traz as secções apuradas nem separa os votos
por tipo, e os ficheiros por condado (``<AAAAMMDD>_<condado>.csv``, ``allcounties``) repartem
cada distrito por vários condados sem dar o total, por isso não se leem. Sem secções, a corrida
não tem percentagem de apuramento. O mesmo caminho existe para as eleições passadas (2022 e
2024), pelo que o ensaio geral com dados reais é possível. Os ficheiros trazem também outras
corridas (presidente e Senado nos anos em que as há); só se lê a Câmara. Não há Senado nem
governador em Washington em 2026.

Washington tem primárias "top two": na eleição geral podem aparecer dois candidatos do mesmo
partido (em 2024, dois Democratas no 9.º distrito e dois Republicanos no 4.º). Não há nada a
tratar à parte: cada candidato é lido com o seu partido, como na Califórnia. O rótulo da fonte
é a preferência declarada pelo candidato (``(Prefers Democratic Party)``, ``(Prefers GOP
Party)``), não a filiação; uma designação livre, como ``(Prefers MAGA Republican Party)``,
conta pelo partido que nomeia. Um candidato sem partido (``WRITE-IN``, com o campo em branco)
conta como ``outro``.
"""

import csv
import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import polars as pl

from contratos.estados import CodigoEstado
from pipeline.comum.erros import ErroFormatoFonte
from pipeline.connectors.results.comum import (
    ObterTexto,
    Pedido,
    identificar_corrida,
    partido,
)
from pipeline.transform.resultados.montar import (
    COLUNAS_UNIDADES,
    COLUNAS_VOTOS,
    DescricaoCorrida,
    Leitura,
)

BASE = "https://results.vote.wa.gov/results/{data}/export/{data}_congressional.csv"
FICHEIRO = "congressional.csv"
CAMPOS = frozenset({"Race", "Candidate", "Party", "Votes"})
"""``PercentageOfTotalVotes`` e ``JurisdictionName`` não se usam: a percentagem calcula-se."""
_PREFERENCIA = re.compile(r"\bPREFERS\b|[()]", re.IGNORECASE)


def rotulo_partido(texto: str) -> str:
    """Normaliza o rótulo de partido da fonte para ``dem``, ``rep`` ou ``outro``.

    Tira os parênteses e o "Prefers" e reconhece o partido mesmo que o candidato tenha
    escrito uma designação própria (``MAGA Republican``).
    """
    limpo = " ".join(_PREFERENCIA.sub(" ", texto).split())
    normalizado = partido(limpo)
    if normalizado != "outro":
        return normalizado
    palavras = set(re.findall(r"[A-Z]+", limpo.upper()))
    if palavras & {"DEMOCRATIC", "DEMOCRAT"}:
        return "dem"
    if palavras & {"REPUBLICAN", "GOP"}:
        return "rep"
    return "outro"


def _corrida(nome: str) -> DescricaoCorrida | None:
    desc = identificar_corrida(CodigoEstado.WA, nome)
    if desc is None or desc.cargo != "camara":
        return None
    return DescricaoCorrida(desc.id, " ".join(nome.split()), "camara", desc.distrito)


@dataclass(frozen=True, slots=True)
class ConectorWA:
    estado: CodigoEstado = CodigoEstado.WA
    nome_fonte: str = "Washington Secretary of State, Election Results"
    licenca: str | None = "Registo público (Public Records Act, RCW 42.56)"

    def pedidos(self, data: date, obter: ObterTexto) -> list[Pedido]:
        del obter
        return [Pedido(BASE.format(data=data.strftime("%Y%m%d")), FICHEIRO)]

    def ler(self, pasta: Path, data: date) -> Leitura:
        del data
        caminho = pasta / FICHEIRO
        corridas: dict[str, DescricaoCorrida] = {}
        votos: list[tuple[object, ...]] = []
        vistos: set[tuple[str, str]] = set()
        with caminho.open(encoding="utf-8-sig", newline="") as f:
            leitor = csv.DictReader(f)
            if not set(leitor.fieldnames or ()) >= CAMPOS:
                msg = f"{caminho.name}: colunas inesperadas {leitor.fieldnames}"
                raise ErroFormatoFonte(msg)
            for linha in leitor:
                desc = _corrida(linha["Race"] or "")
                if desc is None:
                    continue
                nome = " ".join((linha["Candidate"] or "").split())
                if not nome:
                    msg = f"Washington, {desc.id}: candidato sem nome"
                    raise ErroFormatoFonte(msg)
                if (desc.id, nome) in vistos:
                    msg = f"Washington, {desc.id}: candidato repetido {nome!r}"
                    raise ErroFormatoFonte(msg)
                vistos.add((desc.id, nome))
                texto = (linha["Votes"] or "").replace(",", "").strip()
                if not texto.isdigit():
                    msg = f"Washington, {desc.id} {nome}: votos inválidos {linha['Votes']!r}"
                    raise ErroFormatoFonte(msg)
                rotulo = (linha["Party"] or "").strip()
                corridas[desc.id] = desc
                votos.append(
                    (desc.id, nome, nome, rotulo_partido(rotulo), rotulo or None, "estado", None,
                     int(texto))
                )  # fmt: skip
        if not corridas:
            msg = "Washington: nenhuma corrida da Câmara no ficheiro"
            raise ErroFormatoFonte(msg)
        return Leitura(
            corridas=tuple(sorted(corridas.values(), key=lambda c: c.id)),
            votos=pl.DataFrame(votos, schema=COLUNAS_VOTOS, orient="row"),
            unidades=pl.DataFrame(schema=COLUNAS_UNIDADES),
            tipo_unidade=None,
        )
