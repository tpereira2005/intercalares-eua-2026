"""Condado de Maricopa (Arizona): ficheiro oficial de resultados do Maricopa County Elections.

A página ``elections.maricopa.gov/results-and-data/election-results.html`` lista, em
"Election Results Files", o ficheiro de resultados da eleição geral
(``2026 November General Election Results.txt``, cerca de 30 MB). O endereço do ficheiro é
um ``/asset/jcr:<uuid>/<nome>.txt`` que muda quando o condado o substitui, por isso lê-se a
ligação na página em cada ciclo. Usa-se **só** este site: o de resultados ao vivo
(``results.maricopa.vote``) tem um desafio anti-robô do Cloudflare e não o contornamos.

O ficheiro é de texto separado por tabulações, com cabeçalho e uma linha por candidato e
por secção eleitoral (``PrecinctId``). Além delas, cada corrida tem uma linha de total do
condado (``PrecinctId`` vazio) com os votos de cada candidato (``Votes``) e por tipo
(``Votes_Early Vote``, ``Votes_Election Day``, ``Votes_Early A.R.S. 16-579`` e
``Votes_Provisional``). As aspas não têm significado (``FEELY IV, THOMAS "JAY"``).

Entram o governador e os distritos da Câmara que cobrem parte do condado (``US Rep Dist
CD-1``, ...). Não há corrida ao Senado dos EUA no Arizona em 2026. Os totais são só os de
Maricopa, por isso a cobertura é parcial (ver ``condados.conector``).

Tipos de voto: ``Early Vote`` são os boletins antecipados (a quase totalidade chega pelo
correio ou é entregue em mão) e ``Early A.R.S. 16-579`` os boletins antecipados entregues
nos locais de voto no dia da eleição; ambos contam como ``correio``. O ficheiro não separa o
voto antecipado presencial.

O significado de ``PrecinctStatus`` não está publicado (o PDF de descrição dos ficheiros
também está atrás do desafio do Cloudflare). No ficheiro a zero de 2026 todas as secções
têm ``0`` e a linha de total ``1``; assumimos que ``1`` é "secção com resultados".

Não encontrámos ficheiros de 2022 e 2024 ligados a partir da página (o arquivo é montado por
JavaScript, e o código que o monta recebeu o desafio do Cloudflare), por isso não há ensaio
geral com este condado.
"""

import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Final
from urllib.parse import urljoin

import polars as pl

from contratos.estados import CodigoEstado
from pipeline.comum.erros import ErroDescarga, ErroFormatoFonte
from pipeline.connectors.results.comum import ObterTexto, Pedido, identificar_corrida, partido
from pipeline.transform.resultados.montar import (
    COLUNAS_MODALIDADES,
    COLUNAS_UNIDADES,
    COLUNAS_VOTOS,
    DescricaoCorrida,
    Leitura,
)

PAGINA = "https://elections.maricopa.gov/results-and-data/election-results.html"
FICHEIRO = "resultados.txt"
MODALIDADES: Final = {
    "Early Vote": "correio",
    "Early A.R.S. 16-579": "correio",
    "Election Day": "dia_eleicao",
    "Provisional": "provisorio",
}
"""Tipo de voto da coluna ``Votes_<tipo>`` e o nome normalizado."""
COLUNAS: Final = frozenset(
    {"ContestName", "PrecinctId", "PrecinctStatus", "CandidateName", "CandidateType",
     "CandidateAffiliation", "Votes", *(f"Votes_{t}" for t in MODALIDADES)}
)  # fmt: skip
_LIGACAO = re.compile(
    r'<a\s[^>]*?href="(?P<url>[^"]+\.txt)"[^>]*>(?P<nome>[^<]+)</a>', re.IGNORECASE
)
_CAMARA = re.compile(r"^US Rep Dist CD-(\d{1,2})$", re.IGNORECASE)
_SEM_QUALIFICACAO = "*NOT QUALIFIED*"


def procurar_ficheiro(pagina: str, ano: int) -> str:
    """Endereço do ficheiro de resultados da eleição geral do ``ano`` na página do condado."""
    padrao = re.compile(rf"^{ano}\b.*\bGeneral Election Results\.txt$", re.IGNORECASE)
    for m in _LIGACAO.finditer(pagina):
        if padrao.match(" ".join(m["nome"].split())):
            return urljoin(PAGINA, str(m["url"]).replace("&amp;", "&"))
    msg = f"Maricopa: a página não lista o ficheiro de resultados da eleição geral de {ano}"
    raise ErroDescarga(msg)


def _corrida(nome: str) -> DescricaoCorrida | None:
    if m := _CAMARA.match(nome.strip()):
        distrito = int(m.group(1))
        return DescricaoCorrida(f"AZ-{distrito:02d}", nome.strip(), "camara", distrito)
    desc = identificar_corrida(CodigoEstado.AZ, nome)
    if desc is None or desc.cargo not in {"senado", "governador"}:
        return None
    return desc


def _nome(texto: str) -> str:
    """``HOBBS, KATIE R`` passa a ``KATIE R HOBBS``; as aspas e os espaços duplos saem."""
    limpo = " ".join(texto.replace('"', "").split())
    apelido, virgula, resto = limpo.partition(", ")
    return f"{resto} {apelido}" if virgula else limpo


def _inteiro(valor: str, campo: str) -> int:
    try:
        n = int(valor or 0)
    except ValueError as erro:
        msg = f"Maricopa: {campo} inválido {valor!r}"
        raise ErroFormatoFonte(msg) from erro
    if n < 0:
        msg = f"Maricopa: {campo} negativo {valor!r}"
        raise ErroFormatoFonte(msg)
    return n


def _candidato(
    campos: list[str], col: dict[str, int], corrida: str, fips: str
) -> tuple[tuple[object, ...], list[tuple[object, ...]]] | None:
    """Linha de total do condado de um candidato: os votos e os votos por tipo."""
    nome_fonte = campos[col["CandidateName"]]
    if nome_fonte.startswith(_SEM_QUALIFICACAO):
        return None
    tipo = campos[col["CandidateType"]]
    nome = "Write-in" if tipo == "W" else _nome(nome_fonte)
    rotulo = campos[col["CandidateAffiliation"]]
    # Os candidatos de inscrição manual qualificados (``Q``) não têm partido no boletim:
    # contam como ``outro`` mesmo com a sigla de um partido.
    grupo = "outro" if tipo != "R" else partido(rotulo)
    total = _inteiro(campos[col["Votes"]], f"{corrida} {nome}")
    por_tipo: dict[str, int] = {}
    for origem, destino in MODALIDADES.items():
        n = _inteiro(campos[col[f"Votes_{origem}"]], f"{corrida} {nome} {origem}")
        por_tipo[destino] = por_tipo.get(destino, 0) + n
    resto = total - sum(por_tipo.values())
    if resto < 0:
        msg = f"Maricopa, {corrida}: os tipos de voto excedem o total de {nome}"
        raise ErroFormatoFonte(msg)
    por_tipo["outro"] = resto
    voto = (corrida, nome, nome, grupo, rotulo or None, "condado", fips, total)
    return voto, [(corrida, nome, "condado", fips, m, n) for m, n in por_tipo.items()]


@dataclass(frozen=True, slots=True)
class FonteMaricopa:
    fips: str = "04013"
    nome_fonte: str = "Maricopa County Elections Department, Election Results Files"

    def pedidos(self, data: date, obter: ObterTexto) -> list[Pedido]:
        return [Pedido(procurar_ficheiro(obter(PAGINA), data.year), FICHEIRO)]

    def ler(self, pasta: Path, data: date) -> Leitura:
        del data
        caminho = pasta / FICHEIRO
        corridas: dict[str, DescricaoCorrida] = {}
        votos: list[tuple[object, ...]] = []
        modalidades: list[tuple[object, ...]] = []
        secoes: dict[str, dict[str, bool]] = {}
        vistas: set[tuple[str, str]] = set()
        with caminho.open(encoding="utf-8-sig", newline="") as f:
            # Sem ``csv``: as aspas do ficheiro fazem parte dos nomes.
            cabecalho = f.readline().rstrip("\r\n").split("\t")
            if not set(cabecalho) >= COLUNAS:
                msg = f"Maricopa, {caminho.name}: colunas inesperadas {cabecalho[:12]}"
                raise ErroFormatoFonte(msg)
            col = {nome: i for i, nome in enumerate(cabecalho)}
            for linha in f:
                campos = linha.rstrip("\r\n").split("\t")
                if len(campos) < len(cabecalho):
                    continue
                desc = _corrida(campos[col["ContestName"]])
                if desc is None:
                    continue
                corridas[desc.id] = desc
                secao = campos[col["PrecinctId"]]
                if secao:
                    # A ordem das secções vem repetida por candidato: conta-se uma vez.
                    estado = secoes.setdefault(desc.id, {})
                    estado[secao] = estado.get(secao, False) or campos[col["PrecinctStatus"]] == "1"
                    continue
                candidato = _candidato(campos, col, desc.id, self.fips)
                if candidato is None:
                    continue
                voto, por_tipo = candidato
                if (desc.id, voto[1]) in vistas:
                    msg = f"Maricopa, {desc.id}: candidato repetido {voto[1]}"
                    raise ErroFormatoFonte(msg)
                vistas.add((desc.id, str(voto[1])))
                votos.append(voto)
                modalidades.extend(por_tipo)
        if not corridas:
            msg = f"Maricopa, {caminho.name}: nenhuma corrida federal ou de governador"
            raise ErroFormatoFonte(msg)
        sem_total = sorted(corridas.keys() - {v[0] for v in votos})
        if sem_total:
            msg = f"Maricopa: corridas sem linha de total do condado: {sem_total}"
            raise ErroFormatoFonte(msg)
        unidades = [
            (c, "condado", self.fips, sum(s.values()), len(s)) for c, s in sorted(secoes.items())
        ]
        return Leitura(
            corridas=tuple(corridas.values()),
            votos=pl.DataFrame(votos, schema=COLUNAS_VOTOS, orient="row"),
            unidades=pl.DataFrame(unidades, schema=COLUNAS_UNIDADES, orient="row"),
            tipo_unidade="seccao",
            modalidades=pl.DataFrame(modalidades, schema=COLUNAS_MODALIDADES, orient="row"),
        )
