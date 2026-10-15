"""Publicação da sensibilidade: contrato válido, base igual à previsão, sem backtests."""

from datetime import UTC, date, datetime

import pytest

from contratos.base import Fonte
from contratos.sensibilidade import SensibilidadePrevisao
from pipeline.jobs import sensibilidade_previsao as sens
from pipeline.modelo.previsao import AJUSTES_PUBLICADOS, Ajustes, Dados, corte_final, prever

ANO = 2018
AGORA = datetime(2018, 10, 20, 6, 41, tzinfo=UTC)
FONTES = [Fonte(nome="Fonte de teste", url="https://exemplo.pt/", obtida_em=AGORA)]
VARIANTES = (
    sens.Variante("Modelo publicado", AJUSTES_PUBLICADOS, "A previsão publicada."),
    sens.Variante(
        "Ambiente +2 pontos", Ajustes(desvio_ambiente=2.0), "Desloca o ambiente.", backtest=False
    ),
)


@pytest.fixture(scope="module")
def linhas(dados_sinteticos: Dados) -> list[dict[str, object]]:
    return sens.analisar(
        dados_sinteticos, corte_final(ANO), None, VARIANTES, backtests=False, ano=ANO
    )


def test_todas_as_variantes_tem_descricao() -> None:
    assert all(v.descricao.strip() for v in sens.VARIANTES)
    adotadas = [v for v in sens.VARIANTES if "não adotada" in v.descricao]
    assert {v.nome for v in adotadas} == {"Incumbentes corrigidos face às sondagens"}


def test_contrato_valida(linhas: list[dict[str, object]]) -> None:
    ficheiro = sens.contrato(
        linhas,
        ano=ANO,
        corte=corte_final(ANO),
        fontes=FONTES,
        gerado_em=AGORA,
        codigo_commit="abc1234",
    )
    lido = SensibilidadePrevisao.model_validate_json(ficheiro.model_dump_json())
    assert [v.nome for v in lido.variantes] == ["Modelo publicado", "Ambiente +2 pontos"]
    assert lido.codigo_commit == "abc1234"
    assert lido.metadados.fontes
    assert lido.variantes[1].descricao == "Desloca o ambiente."


def test_variante_publicada_coincide_com_a_previsao(
    dados_sinteticos: Dados, linhas: list[dict[str, object]]
) -> None:
    ficheiro = sens.contrato(
        linhas, ano=ANO, corte=corte_final(ANO), fontes=FONTES, gerado_em=AGORA, codigo_commit=None
    )
    previsao = prever(dados_sinteticos, ANO, corte=corte_final(ANO))
    base = ficheiro.variantes[0]
    assert base.camara.prob_controlo_d == previsao.camara.prob_controlo_d
    assert base.senado.prob_controlo_d == previsao.senado.prob_controlo_d
    assert base.ambiente == previsao.ambiente.margem
    assert linhas[0]["backtests"] is None
    assert isinstance(corte_final(ANO), date)


def test_sem_backtests_nao_corre_avaliar(
    dados_sinteticos: Dados, monkeypatch: pytest.MonkeyPatch
) -> None:
    def proibido(*_: object, **__: object) -> None:
        raise AssertionError("os backtests não deviam correr")

    monkeypatch.setattr(sens, "avaliar", proibido)
    resultado = sens.analisar(
        dados_sinteticos, corte_final(ANO), None, VARIANTES, backtests=False, ano=ANO
    )
    assert len(resultado) == 2
