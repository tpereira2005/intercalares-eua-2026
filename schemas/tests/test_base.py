from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from contratos import CodigoEstado, Fonte, Metadados
from contratos.base import VERSAO_ESQUEMA


def _fonte() -> Fonte:
    return Fonte(
        nome="North Carolina State Board of Elections",
        url="https://www.ncsbe.gov/results-data",
        obtida_em=datetime(2026, 10, 13, 12, 0, tzinfo=UTC),
    )


def test_metadados_validos_usam_versao_atual() -> None:
    metadados = Metadados(gerado_em=datetime(2026, 10, 13, tzinfo=UTC), fontes=(_fonte(),))
    assert metadados.versao_esquema == VERSAO_ESQUEMA


def test_rejeita_campos_desconhecidos() -> None:
    with pytest.raises(ValidationError, match="extra_forbidden"):
        Fonte.model_validate(
            {
                "nome": "X",
                "url": "https://exemplo.org",
                "obtida_em": "2026-10-13T12:00:00Z",
                "campo_novo": 1,
            }
        )


def test_rejeita_datas_sem_fuso_horario() -> None:
    with pytest.raises(ValidationError, match="timezone"):
        Fonte.model_validate(
            {"nome": "X", "url": "https://exemplo.org", "obtida_em": "2026-10-13T12:00:00"}
        )


def test_exige_pelo_menos_uma_fonte() -> None:
    with pytest.raises(ValidationError, match="too_short"):
        Metadados(gerado_em=datetime(2026, 10, 13, tzinfo=UTC), fontes=())


def test_contratos_sao_imutaveis() -> None:
    fonte = _fonte()
    with pytest.raises(ValidationError, match="frozen"):
        fonte.nome = "Outra"  # type: ignore[misc]


def test_codigos_de_estado_incluem_dc() -> None:
    assert len(CodigoEstado) == 51
    assert CodigoEstado("NC") is CodigoEstado.NC
