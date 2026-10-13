"""Conversão de uma corrida em linha do modelo: lados, corridas decididas e incumbência."""

import pytest

from pipeline.modelo.dados import linha_modelo
from pipeline.modelo.fontes.corridas import Candidato, Corrida


def _corrida(
    candidatos: list[Candidato], incumbentes: list[tuple[str, str]] | None = None
) -> Corrida:
    return Corrida(2022, "senado", "ME", "S", 3.0, incumbentes or [], candidatos)


def test_margem_e_incumbencia() -> None:
    linha = linha_modelo(
        _corrida(
            [Candidato("Ana Silva", "D", 52.0), Candidato("Rui Costa", "R", 46.0)],
            [("Rui Costa", "R")],
        )
    )
    assert linha is not None
    assert linha.margem == pytest.approx(6.0)
    assert linha.incumbente == -1
    assert linha.pvi == 6.0
    assert linha.vencedor == "D"


def test_sem_pvi_nao_ha_linha() -> None:
    assert linha_modelo(Corrida(2022, "camara", "ME", "01", None)) is None


def test_sem_adversario_fica_decidida() -> None:
    linha = linha_modelo(_corrida([Candidato("Ana Silva", "D", None)]))
    assert linha is not None
    assert linha.certo == "D"


@pytest.mark.parametrize(("lado", "outro"), [("D", "R"), ("R", "D")])
def test_independente_ocupa_o_lado_vazio_dos_dois_lados(lado: str, outro: str) -> None:
    linha = linha_modelo(
        _corrida([Candidato("Rui Costa", outro, 55.0), Candidato("Eva Lopes", "O", 42.0)])
    )
    assert linha is not None
    assert linha.certo is None
    if lado == "D":
        assert linha.lado_d_independente
        assert linha.lado_d == "Eva Lopes"
        assert linha.margem == pytest.approx(-13.0)
    else:
        assert linha.lado_r_independente
        assert linha.lado_r == "Eva Lopes"
        assert linha.margem == pytest.approx(13.0)


def test_independentes_conhecidos_em_cada_lado() -> None:
    corrida = _corrida(
        [
            Candidato("Eva Lopes", "O", 49.0),
            Candidato("Ana Silva", "D", 3.0),
            Candidato("Rui Costa", "R", 48.0),
        ],
        [("Eva Lopes", "I")],
    )
    linha = linha_modelo(corrida, independentes_d=frozenset({"Eva Lopes"}))
    assert linha is not None
    assert linha.lado_d == "Eva Lopes"
    assert linha.lado_d_independente
    assert linha.incumbente == 1
    assert linha.margem == pytest.approx(1.0)


def test_voto_preferencial_usa_a_primeira_volta_e_vencedor_da_ultima() -> None:
    linha = linha_modelo(
        _corrida(
            [
                Candidato("Rui Costa", "R", 46.3),
                Candidato("Ana Silva", "D", 45.6),
                Candidato("Eva Lopes", "O", 8.1),
                Candidato("Ana Silva", "D", 50.6),
                Candidato("Rui Costa", "R", 49.4),
            ]
        )
    )
    assert linha is not None
    assert linha.margem == pytest.approx(-0.7)
    assert linha.vencedor == "D"


def test_disputa_interna_nao_entra_na_margem() -> None:
    linha = linha_modelo(
        _corrida(
            [
                Candidato("Ana Silva", "D", 48.0),
                Candidato("Rui Costa", "R", 26.0),
                Candidato("Rita Neves", "R", 24.0),
            ]
        )
    )
    assert linha is not None
    assert linha.margem is None
    assert linha.vencedor == "D"


@pytest.mark.parametrize("partido", ["D", "R"])
def test_antes_da_eleicao_escolhe_o_incumbente_e_nao_um_homonimo(partido: str) -> None:
    """Alasca 2026: a lista traz o incumbente, um homónimo e um candidato menor."""
    outro = "R" if partido == "D" else "D"
    linha = linha_modelo(
        _corrida(
            [
                Candidato("Gerald Heikes", partido, None),
                Candidato("Mary Peltola", outro, None, notavel=True),
                Candidato("Dan J. Sullivan", partido, None),
                Candidato("Dan S. Sullivan", partido, None, notavel=True),
            ],
            [("Dan Sullivan", partido)],
        )
    )
    assert linha is not None
    escolhido = linha.lado_d if partido == "D" else linha.lado_r
    assert escolhido == "Dan S. Sullivan"
    assert linha.incumbente == (1 if partido == "D" else -1)


def test_incumbente_que_nao_e_o_candidato_nao_conta() -> None:
    """Um homónimo do incumbente noutro partido não herda a vantagem (PA-12 em 2022)."""
    linha = linha_modelo(
        _corrida(
            [Candidato("Summer Lee", "D", 56.2), Candidato("Mike Doyle", "R", 43.8)],
            [("Mike Doyle", "D")],
        )
    )
    assert linha is not None
    assert linha.incumbente == 0
