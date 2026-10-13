"""Verificações de coerência da previsão antes de publicar.

Apanham leituras erradas das fontes (o candidato errado de um lado, uma tabela de
sondagens de outra disputa) que o contrato não consegue ver, porque os valores estão
dentro dos limites. Um ``erro`` impede a publicação; um ``aviso`` fica no registo para
revisão. As regras são simétricas: olham para distâncias e sinais, nunca para o partido.
"""

import logging
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Literal

from contratos.previsao import PrevisaoCongresso
from pipeline.comum.erros import ErroPipeline
from pipeline.modelo.dados import normalizar_nome
from pipeline.modelo.fontes.corridas import Corrida

registo = logging.getLogger(__name__)

DISTANCIA_ERRO = 25.0
"""Diferença (pontos) entre a média de sondagens e os fundamentos que não é plausível."""

DISTANCIA_AVISO = 15.0
PROB_EXTREMA = 0.99
FUNDAMENTOS_CONTRARIOS = 3.0
"""Uma probabilidade extrema contra fundamentos que favorecem o outro lado por mais do
que isto só é aceitável com muita informação, e merece sempre revisão."""

INSTITUTOS_SUFICIENTES = 4
"""Abaixo disto, uma probabilidade extrema contra os fundamentos é um erro."""

POUCOS_INSTITUTOS = 2
PESO_ALTO = 0.7


@dataclass(frozen=True, slots=True)
class Problema:
    corrida: str
    gravidade: Literal["erro", "aviso"]
    descricao: str


class PrevisaoIncoerente(ErroPipeline):
    """A previsão falhou uma verificação de coerência e não deve ser publicada."""


def _incumbente_ignorado(corrida: Corrida, lado_d: str, lado_r: str) -> Problema | None:
    escolhidos = {"D": lado_d, "R": lado_r}
    for nome, partido in corrida.incumbentes:
        if partido not in escolhidos:
            continue
        apelido = normalizar_nome(nome)
        concorre = any(
            c.partido == partido and normalizar_nome(c.nome) == apelido for c in corrida.candidatos
        )
        if concorre and normalizar_nome(escolhidos[partido]) != apelido:
            return Problema(
                corrida.id,
                "erro",
                f"o incumbente {nome} concorre mas o candidato escolhido é "
                f"{escolhidos[partido] or 'nenhum'}",
            )
    return None


def verificar(previsao: PrevisaoCongresso, corridas: Iterable[Corrida] = ()) -> list[Problema]:
    """Problemas encontrados na previsão (e nas corridas lidas, se forem dadas)."""
    problemas: list[Problema] = []
    por_id = {c.id: c for c in previsao.corridas}
    for corrida in corridas:
        prevista = por_id.get(corrida.id)
        if prevista is None or prevista.decidida is not None:
            continue
        problema = _incumbente_ignorado(
            corrida, prevista.candidato_d or "", prevista.candidato_r or ""
        )
        if problema is not None:
            problemas.append(problema)

    for c in previsao.corridas:
        if c.decidida is not None:
            continue
        if c.margem_sondagens is not None:
            distancia = abs(c.margem_sondagens - c.margem_fundamentos)
            if distancia > DISTANCIA_AVISO:
                problemas.append(
                    Problema(
                        c.id,
                        "erro" if distancia > DISTANCIA_ERRO else "aviso",
                        f"sondagens {c.margem_sondagens:+.1f} e fundamentos "
                        f"{c.margem_fundamentos:+.1f} afastados {distancia:.1f} pontos",
                    )
                )
            if c.institutos <= POUCOS_INSTITUTOS and c.peso_sondagens > PESO_ALTO:
                problemas.append(
                    Problema(
                        c.id,
                        "aviso",
                        f"{c.institutos} institutos com peso {c.peso_sondagens:.2f}",
                    )
                )
        favorito_d = c.prob_d >= PROB_EXTREMA
        favorito_r = c.prob_d <= 1 - PROB_EXTREMA
        if (favorito_d and c.margem_fundamentos < -FUNDAMENTOS_CONTRARIOS) or (
            favorito_r and c.margem_fundamentos > FUNDAMENTOS_CONTRARIOS
        ):
            problemas.append(
                Problema(
                    c.id,
                    "erro" if c.institutos < INSTITUTOS_SUFICIENTES else "aviso",
                    f"probabilidade {c.prob_d:.3f} contra fundamentos {c.margem_fundamentos:+.1f}",
                )
            )
    return problemas


def exigir_coerencia(previsao: PrevisaoCongresso, corridas: Iterable[Corrida] = ()) -> None:
    """Regista os avisos e falha se houver erros."""
    problemas = verificar(previsao, corridas)
    for p in problemas:
        nivel = logging.ERROR if p.gravidade == "erro" else logging.WARNING
        registo.log(nivel, "%s: %s", p.corrida, p.descricao)
    erros = [p for p in problemas if p.gravidade == "erro"]
    if erros:
        lista = "; ".join(f"{p.corrida}: {p.descricao}" for p in erros)
        raise PrevisaoIncoerente(f"{len(erros)} incoerências na previsão: {lista}")
