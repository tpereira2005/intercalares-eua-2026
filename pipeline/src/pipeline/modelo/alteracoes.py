"""Registo público das alterações do método da previsão.

O registo é mantido à mão em ``data/reference/modelo/alteracoes_metodo_2026.json``: cada
PR que muda o modelo ou a leitura dos dados de entrada acrescenta uma entrada, com a
probabilidade de controlo de cada câmara antes e depois, calculada com a mesma data de
corte e os mesmos dados. O job da previsão valida o ficheiro e publica-o com metadados.
"""

from collections.abc import Sequence
from datetime import datetime
from pathlib import Path

from pydantic import TypeAdapter

from contratos.base import Fonte, Metadados
from contratos.previsao import AlteracaoMetodo, AlteracoesPrevisao
from pipeline.comum.erros import ErroFormatoFonte

REGISTO = Path("data/reference/modelo/alteracoes_metodo_2026.json")
_LISTA = TypeAdapter(tuple[AlteracaoMetodo, ...])


def ler(caminho: Path = REGISTO) -> tuple[AlteracaoMetodo, ...]:
    alteracoes = _LISTA.validate_json(caminho.read_bytes())
    datas = [a.data for a in alteracoes]
    if datas != sorted(datas):
        raise ErroFormatoFonte(f"{caminho}: as alterações têm de estar por ordem cronológica")
    return alteracoes


def montar(
    ano: int, *, fontes: Sequence[Fonte], gerado_em: datetime, caminho: Path = REGISTO
) -> AlteracoesPrevisao:
    return AlteracoesPrevisao(
        metadados=Metadados(gerado_em=gerado_em, fontes=tuple(fontes)),
        ano=ano,
        alteracoes=ler(caminho),
    )
