"""Conector genérico para os sites de resultados Clarity (Scytl).

Cada eleição tem um identificador (``eid``) e versões sucessivas: ``current_ver.txt`` diz
a versão atual e ``{versão}/reports/detailxml.zip`` traz um XML com todas as corridas,
os votos por candidato, tipo de voto e condado, e as secções apuradas por condado. Um só
pedido por ciclo chega para o estado inteiro.

O ``eid`` da eleição geral só existe quando o estado cria a página (normalmente poucos
dias antes). Até lá, ``pedidos`` falha com uma mensagem clara e a recolha salta o estado.
"""

import re
import zipfile
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from xml.etree import ElementTree as ET

import polars as pl

from contratos.estados import CodigoEstado
from pipeline.comum.condados import chave, fips_por_nome
from pipeline.comum.erros import ErroDescarga, ErroFormatoFonte
from pipeline.connectors.results.comum import (
    ObterTexto,
    Pedido,
    identificar_corrida,
    modalidade,
    partido,
)
from pipeline.transform.resultados.montar import (
    COLUNAS_MODALIDADES,
    COLUNAS_UNIDADES,
    COLUNAS_VOTOS,
    DescricaoCorrida,
    Leitura,
)

FICHEIRO = "detailxml.zip"


@dataclass(frozen=True, slots=True)
class ConectorClarity:
    estado: CodigoEstado
    base: str
    """Ex.: ``https://www.enr-scvotes.org/SC``."""

    eleicoes: Mapping[date, int] = field(default_factory=dict)
    """Data da eleição para o ``eid`` do site."""

    nome_fonte: str = ""
    licenca: str | None = None

    def pedidos(self, data: date, obter: ObterTexto) -> list[Pedido]:
        eid = self.eleicoes.get(data)
        if eid is None:
            msg = f"{self.estado}: ainda não há página Clarity conhecida para {data}"
            raise ErroDescarga(msg)
        versao = obter(f"{self.base}/{eid}/current_ver.txt").strip()
        if not versao.isdigit():
            msg = f"{self.estado}: versão inesperada {versao[:40]!r}"
            raise ErroFormatoFonte(msg)
        return [Pedido(f"{self.base}/{eid}/{versao}/reports/detailxml.zip", FICHEIRO)]

    def ler(self, pasta: Path, data: date) -> Leitura:
        del data
        with zipfile.ZipFile(pasta / FICHEIRO) as z:
            nomes_xml = [n for n in z.namelist() if n.lower().endswith(".xml")]
            if len(nomes_xml) != 1:
                msg = f"{FICHEIRO}: esperava um XML, encontrei {nomes_xml}"
                raise ErroFormatoFonte(msg)
            raiz = ET.fromstring(z.read(nomes_xml[0]))  # noqa: S314 (expat recusa expansões)
        if raiz.tag != "ElectionResult":
            msg = f"{FICHEIRO}: raiz inesperada {raiz.tag}"
            raise ErroFormatoFonte(msg)
        fips = fips_por_nome(self.estado.value)
        corridas: list[DescricaoCorrida] = []
        votos: list[tuple[object, ...]] = []
        unidades: list[tuple[object, ...]] = []
        modalidades: list[tuple[object, ...]] = []
        for contest in raiz.iter("Contest"):
            desc = identificar_corrida(self.estado, contest.get("text", ""))
            if desc is None or contest.get("isQuestion") == "true":
                continue
            corridas.append(desc)
            unidades.append(
                (desc.id, "estado", None, _int(contest, "precinctsReported"),
                 _int(contest, "precinctsParticipating"))
            )  # fmt: skip
            for c in contest.iterfind("ParticipatingCounties/County"):
                unidades.append(
                    (desc.id, "condado", _fips(fips, c.get("name", "")),
                     _int(c, "precinctsReported"), _int(c, "precinctsParticipating"))
                )  # fmt: skip
            for escolha in contest.iterfind("Choice"):
                rotulo = escolha.get("party") or ""
                nome = _nome(escolha.get("text", ""), rotulo)
                cand = escolha.get("key") or nome
                comum = (desc.id, cand, nome, partido(rotulo), rotulo or None)
                votos.append((*comum, "estado", None, _int(escolha, "totalVotes")))
                por_condado: dict[str, int] = {}
                for tipo in escolha.iterfind("VoteType"):
                    m = modalidade(tipo.get("name", ""))
                    modalidades.append((desc.id, cand, "estado", None, m, _int(tipo, "votes")))
                    for c in tipo.iterfind("County"):
                        codigo = _fips(fips, c.get("name", ""))
                        n = _int(c, "votes")
                        por_condado[codigo] = por_condado.get(codigo, 0) + n
                        modalidades.append((desc.id, cand, "condado", codigo, m, n))
                votos.extend((*comum, "condado", k, v) for k, v in por_condado.items())
        return Leitura(
            corridas=tuple({d.id: d for d in corridas}.values()),
            votos=pl.DataFrame(votos, schema=COLUNAS_VOTOS, orient="row"),
            unidades=pl.DataFrame(unidades, schema=COLUNAS_UNIDADES, orient="row"),
            tipo_unidade="seccao",
            modalidades=pl.DataFrame(modalidades, schema=COLUNAS_MODALIDADES, orient="row"),
        )


def _int(elemento: ET.Element, atributo: str) -> int:
    valor = elemento.get(atributo)
    if valor is None or not valor.strip().lstrip("-").isdigit():
        msg = f"Atributo {atributo} inválido em <{elemento.tag}>: {valor!r}"
        raise ErroFormatoFonte(msg)
    return int(valor)


def _fips(tabela: Mapping[str, str], nome: str) -> str:
    codigo = tabela.get(chave(nome))
    if codigo is None:
        msg = f"Condado desconhecido: {nome!r}"
        raise ErroFormatoFonte(msg)
    return codigo


def _nome(texto: str, rotulo: str) -> str:
    """Tira o partido do início do nome (``"REP Tim Scott"``)."""
    if rotulo and texto.upper().startswith(rotulo.upper() + " "):
        texto = texto[len(rotulo) + 1 :]
    return re.sub(r"\s+", " ", texto).strip()


CAROLINA_DO_SUL = ConectorClarity(
    estado=CodigoEstado.SC,
    base="https://www.enr-scvotes.org/SC",
    eleicoes={date(2022, 11, 8): 115412, date(2024, 11, 5): 122436},
    nome_fonte="South Carolina Election Commission, Election Night Reporting",
    licenca="Registo público",
)

IOWA = ConectorClarity(
    estado=CodigoEstado.IA,
    base="https://results.enr.clarityelections.com/IA",
    eleicoes={date(2024, 11, 5): 122322},
    nome_fonte="Iowa Secretary of State, Election Night Reporting",
    licenca="Registo público",
)
