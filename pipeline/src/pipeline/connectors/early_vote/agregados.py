"""Registo dos estados acompanhados com granularidade de boletim mas sem recenseados por grupo.

Cada estado diz onde estão os ficheiros de 2026 e dos anos de referência, como lê-los
para a tabela comum de :mod:`pipeline.transform.early_vote.agregado` e que dimensões e
modalidades a fonte cobre. O resto do caminho (cubos, indicadores, ficheiro publicado) é
igual para todos.
"""

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from email.utils import parsedate_to_datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import httpx
import polars as pl

from contratos.estados import CodigoEstado
from pipeline.comum.calendario import EleicaoGeral, eleicao_geral
from pipeline.comum.descarga import USER_AGENT, Descarga
from pipeline.comum.leitura import RelatorioLeitura
from pipeline.connectors.early_vote.me import fontes as fontes_me
from pipeline.connectors.early_vote.me.ler import ler_boletins as ler_me
from pipeline.connectors.early_vote.pa import codigos as codigos_pa
from pipeline.connectors.early_vote.pa import fontes as fontes_pa
from pipeline.connectors.early_vote.pa.ler import ler_pedidos as ler_pa

FUSO_FONTES = ZoneInfo("America/New_York")
"""Os estados acompanhados aqui publicam na hora da costa leste."""

Leitor = Callable[[Path, EleicaoGeral], tuple[pl.DataFrame, RelatorioLeitura]]


@dataclass(frozen=True, slots=True)
class ConectorAgregado:
    estado: CodigoEstado
    nome_fonte: str
    licenca: str
    ler: Leitor
    url_atual: Callable[[httpx.Client], str]
    urls_base: Mapping[int, str]
    anos_base: tuple[int, ...]
    """Anos de comparação, pela ordem em que aparecem (intercalares primeiro)."""

    dimensoes: tuple[str, ...]
    modalidades: tuple[str, ...]
    nomes_condados: Mapping[str, str] = field(default_factory=dict)
    notas: Mapping[int, tuple[str, ...]] = field(default_factory=dict)
    avisos: tuple[str, ...] = ()

    def eleicao(self, ano: int) -> EleicaoGeral:
        return eleicao_geral(self.estado.value, ano, self.notas.get(ano, ()))

    def pasta(self, raiz: Path, tipo: str) -> Path:
        return raiz / "data" / tipo / self.estado.value.lower()


def _url_pa(_: httpx.Client) -> str:
    return fontes_pa.url_pedidos(2026)


def _url_me(cliente: httpx.Client) -> str:
    resposta = cliente.get(fontes_me.PAGINA_ATUAL, headers={"User-Agent": USER_AGENT})
    resposta.raise_for_status()
    url = fontes_me.url_atual(resposta.text)
    if url is None:
        msg = f"Não encontrei o ficheiro de 2026 em {fontes_me.PAGINA_ATUAL}"
        raise RuntimeError(msg)
    return url


NOTA_2024 = "Eleição presidencial: comparar sobretudo o ritmo, não o nível."
NOTA_2020 = "Pandemia: voto por correspondência excecional; usar sempre com aviso."

CONECTORES: dict[CodigoEstado, ConectorAgregado] = {
    CodigoEstado.PA: ConectorAgregado(
        estado=CodigoEstado.PA,
        nome_fonte=fontes_pa.NOME_FONTE,
        licenca=fontes_pa.LICENCA,
        ler=ler_pa,
        url_atual=_url_pa,
        urls_base={ano: fontes_pa.url_pedidos(ano) for ano in (2022, 2024)},
        anos_base=(2022, 2024),
        dimensoes=("faixa", "partido", "condado", "distrito"),
        modalidades=("correio",),
        nomes_condados=codigos_pa.NOME_CONDADO,
        notas={2024: (NOTA_2024,)},
        avisos=(
            "Na Pensilvânia não há voto antecipado presencial: tudo é voto por "
            "correspondência (incluindo o pedido e entregue no balcão do condado).",
            "Desde 2024 a fonte junta os não filiados e os pequenos partidos; aqui ficam "
            "todos em 'outro'.",
            "Sem ficheiro de eleitores gratuito: compara-se votos com votos, não taxas de "
            "participação.",
        ),
    ),
    CodigoEstado.ME: ConectorAgregado(
        estado=CodigoEstado.ME,
        nome_fonte=fontes_me.NOME_FONTE,
        licenca=fontes_me.LICENCA,
        ler=ler_me,
        url_atual=_url_me,
        urls_base=fontes_me.FINAIS,
        anos_base=(2022, 2018, 2024),
        dimensoes=("partido", "modalidade", "distrito"),
        modalidades=("correio", "presencial"),
        notas={
            2022: (
                "O voto presencial começou a 11 de outubro (feriado a 10), seis dias mais "
                "tarde no ciclo do que em 2026.",
            ),
            2024: (NOTA_2024,),
        },
        avisos=(
            "A fonte não tem a idade dos eleitores.",
            "O ficheiro de 2026 é atualizado algumas vezes por semana, não todos os dias.",
            "Sem ficheiro de eleitores gratuito: compara-se votos com votos, não taxas de "
            "participação.",
        ),
    ),
}


def gerado_em(descarga: Descarga) -> datetime:
    """Momento em que a fonte gerou o ficheiro (Last-Modified), ou o da recolha."""
    if descarga.ultima_modificacao:
        try:
            return parsedate_to_datetime(descarga.ultima_modificacao)
        except (TypeError, ValueError):
            pass
    return descarga.obtido_em


def ultimo_dia_completo(maximo: date | None, gerado: datetime) -> date | None:
    """O ficheiro pode ter receções do próprio dia em que foi gerado: esse dia não conta."""
    if maximo is None:
        return None
    return min(maximo, gerado.astimezone(FUSO_FONTES).date() - timedelta(days=1))
