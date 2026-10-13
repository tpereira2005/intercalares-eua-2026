"""Histórico diário: uma entrada por data de corte, por ordem, substituída se repetida."""

from datetime import UTC, date, datetime

import pytest

from contratos.base import Fonte
from contratos.previsao import PrevisaoCongresso
from pipeline.modelo.historico import acrescentar
from pipeline.modelo.previsao import Dados, prever
from pipeline.modelo.publicar import montar

AGORA = datetime(2018, 11, 1, tzinfo=UTC)
FONTE = Fonte(nome="Sintética", url="https://example.org/", obtida_em=AGORA)


def test_acrescenta_por_ordem_e_substitui_o_mesmo_dia(dados_sinteticos: Dados) -> None:
    def publicada(dia: date, semente: int = 2026) -> PrevisaoCongresso:
        return montar(
            prever(dados_sinteticos, 2018, corte=dia, semente=semente),
            fontes=[FONTE],
            gerado_em=AGORA,
        )

    h = acrescentar(None, publicada(date(2018, 10, 30)))
    h = acrescentar(h, publicada(date(2018, 10, 25)))
    h = acrescentar(h, publicada(date(2018, 10, 30), semente=1))
    assert [d.corte for d in h.dias] == [date(2018, 10, 25), date(2018, 10, 30)]
    assert len(h.dias[0].corridas) == len(dados_sinteticos.corridas[2018])
    assert not h.dias[-1].congelada
    with pytest.raises(ValueError, match="Histórico"):
        acrescentar(h.model_copy(update={"ano": 2016}), publicada(date(2018, 10, 31)))
