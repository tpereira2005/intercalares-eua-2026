"""As verificações de coerência apanham leituras erradas como a do Alasca em 2026."""

from datetime import UTC, datetime

import pytest

from contratos.base import Fonte
from contratos.previsao import PrevisaoCongresso, PrevisaoCorrida
from pipeline.modelo.fontes.corridas import Candidato, Corrida
from pipeline.modelo.previsao import Dados, prever
from pipeline.modelo.publicar import montar
from pipeline.modelo.verificacoes import PrevisaoIncoerente, exigir_coerencia, verificar

AGORA = datetime(2018, 11, 4, tzinfo=UTC)


@pytest.fixture(scope="module")
def previsao(dados_sinteticos: Dados) -> PrevisaoCongresso:
    fonte = Fonte(nome="Sintética", url="https://example.org/", obtida_em=AGORA)
    return montar(prever(dados_sinteticos, 2018), fontes=[fonte], gerado_em=AGORA)


def _com(previsao: PrevisaoCongresso, corrida: PrevisaoCorrida) -> PrevisaoCongresso:
    corridas = tuple(corrida if c.id == corrida.id else c for c in previsao.corridas)
    return previsao.model_copy(update={"corridas": corridas})


def _senado(previsao: PrevisaoCongresso) -> PrevisaoCorrida:
    return next(c for c in previsao.corridas if c.camara == "senado" and c.decidida is None)


def test_previsao_sintetica_nao_tem_erros(previsao: PrevisaoCongresso) -> None:
    assert [p for p in verificar(previsao) if p.gravidade == "erro"] == []
    exigir_coerencia(previsao)


@pytest.mark.parametrize("sinal", [1.0, -1.0])
def test_sondagens_implausiveis_e_probabilidade_extrema(
    previsao: PrevisaoCongresso, sinal: float
) -> None:
    """O caso do Alasca: sondagens D+45 contra fundamentos R+6, e P(D) = 1 (e o espelho)."""
    c = _senado(previsao).model_copy(
        update={
            "margem_fundamentos": -5.7 * sinal,
            "margem_sondagens": 44.7 * sinal,
            "prob_d": 1.0 if sinal > 0 else 0.0,
            "institutos": 3,
        }
    )
    problemas = verificar(_com(previsao, c))
    assert {p.descricao.split()[0] for p in problemas if p.corrida == c.id} == {
        "sondagens",
        "probabilidade",
    }
    with pytest.raises(PrevisaoIncoerente):
        exigir_coerencia(_com(previsao, c))


def test_incumbente_ignorado(previsao: PrevisaoCongresso) -> None:
    c = _senado(previsao).model_copy(update={"candidato_r": "Gerald Heikes"})
    corrida = Corrida(
        2018,
        "senado",
        c.estado,
        "S",
        -6.0,
        [("Dan Sullivan", "R")],
        [
            Candidato("Gerald Heikes", "R", None),
            Candidato(c.candidato_d or "Ana", "D", None),
            Candidato("Dan S. Sullivan", "R", None, notavel=True),
        ],
    )
    problemas = verificar(_com(previsao, c), [corrida])
    assert any(p.gravidade == "erro" and "incumbente" in p.descricao for p in problemas)
