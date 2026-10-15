"""Leitura das tabelas de classificações de outros prognosticadores (Wikipedia)."""

from datetime import UTC, date, datetime

import pytest

from pipeline.comum.erros import ErroFormatoFonte
from pipeline.connectors.prognosticos import ler_camara, ler_senado
from pipeline.jobs.prognosticos_externos import construir

SENADO = """
== Retirements ==
{| class="wikitable"
! State !! Senator
|-
! [[2026 United States Senate election in Alabama|Alabama]]
| {{USRaceRating|Solid|R}}
|}

== Predictions ==
{| class="wikitable sortable"
|-
! colspan=2 | Constituency
! colspan=3 | Ratings
|-
! State
! [[Cook Partisan Voting Index|PVI]]
! ''[[The Cook Political Report|Cook]]''<br />{{small|Oct 6,<br />2026}}
! [[Sabato's Crystal Ball|Sabato]]<br />{{small|Oct. 14,<br>2026}}
! [[Split Ticket (website)|ST]]<br />{{Small|Oct 14,<br />2026}}
|-
! [[2026 United States Senate election in Alaska|Alaska]]
| {{Shading PVI|R|6}}
<!--Cook-->   | {{USRaceRating|Tossup}}
<!--Sabato--> | {{USRaceRating|Lean|D|flip}}
<!--ST-->     | {{USRaceRating|Tilt|D|flip}}
|-
! [[2026 United States Senate special election in Florida|Florida]]<br />{{small|(special)}}
| {{Shading PVI|R|8}}
<!--Cook-->   | {{USRaceRating|Likely|R}}
<!--Sabato--> | {{USRaceRating|Safe|R}}
<!--ST-->     | {{USRaceRating|Solid|R}}
|}
"""

CAMARA = """
{| class="wikitable sortable"
! District
! [[Cook Partisan Voting Index|CPVI]]
! [[Cook Political Report|Cook]]<br />{{small|Oct 9,<br />2026}}
! [[Stuart Rothenberg|IE]]<br />{{small|Oct 1,<br />2026}}
! [[Silver Bulletin|Silver]]<br />{{small|Sep. 10, 2026}}
|-
!{{ushr|AL|2|X}}
| D+5 || {{USRaceRating|Likely|D}} || {{USRaceRating|Lean|D}} || {{USRaceRating|Likely|D}}
|-
!{{ushr|AK|AL|X}}
| R+6 || {{USRaceRating|Tossup}} || {{USRaceRating|Tilt|R}} || {{USRaceRating|Lean|R}}
|}
"""


def test_senado_le_a_tabela_das_previsoes_e_nao_a_primeira() -> None:
    tabela = ler_senado(SENADO)
    assert [c.chave for c in tabela.colunas] == ["cook", "sabato", "split-ticket"]
    assert [c.data for c in tabela.colunas] == [
        date(2026, 10, 6),
        date(2026, 10, 14),
        date(2026, 10, 14),
    ]
    assert [c.id for c in tabela.corridas] == ["AK-S", "FL-S-especial"]
    alasca = tabela.corridas[0].classificacoes
    assert [(c.prognosticador, c.categoria, c.partido) for c in alasca] == [
        ("cook", "empate", None),
        ("sabato", "inclinado", "D"),
        ("split-ticket", "ligeiro", "D"),
    ]
    assert {c.categoria for c in tabela.corridas[1].classificacoes} == {"provavel", "seguro"}


def test_camara_le_distritos_na_mesma_linha_e_at_large() -> None:
    tabela = ler_camara(CAMARA)
    assert [c.chave for c in tabela.colunas] == ["cook", "ie", "silver"]
    assert tabela.colunas[2].data == date(2026, 9, 10)
    assert [c.id for c in tabela.corridas] == ["AL-02", "AK-00"]
    assert [c.categoria for c in tabela.corridas[1].classificacoes] == [
        "empate",
        "ligeiro",
        "inclinado",
    ]


def test_categoria_desconhecida_falha() -> None:
    with pytest.raises(ErroFormatoFonte, match="classificação desconhecida"):
        ler_camara(CAMARA.replace("{{USRaceRating|Tossup}}", "{{USRaceRating|Toss|R}}"))


def test_corrida_repetida_falha() -> None:
    with pytest.raises(ErroFormatoFonte, match="repetida"):
        ler_camara(CAMARA.replace("{{ushr|AK|AL|X}}", "{{ushr|AL|2|X}}"))


def test_linha_sem_todas_as_colunas_falha() -> None:
    curta = CAMARA.replace(" || {{USRaceRating|Lean|R}}", "")
    with pytest.raises(ErroFormatoFonte, match="faltam colunas"):
        ler_camara(curta)


def test_senado_sem_seccao_das_previsoes_falha() -> None:
    with pytest.raises(ErroFormatoFonte, match="Predictions"):
        ler_senado(SENADO.replace("== Predictions ==", "== Outra =="))


@pytest.mark.parametrize(
    ("momento", "congelado"),
    [
        (datetime(2026, 10, 31, 23, 0, tzinfo=UTC), False),
        (datetime(2026, 11, 1, 6, 0, tzinfo=UTC), True),
    ],
)
def test_construir_congela_no_dia_do_corte(momento: datetime, congelado: bool) -> None:
    dados = construir(SENADO, CAMARA, momento)
    assert dados.congelado is congelado
    assert dados.ano == 2026
    assert [f.licenca for f in dados.metadados.fontes] == ["CC BY-SA 4.0"] * 2
    assert [p.chave for p in dados.prognosticadores_camara] == ["cook", "ie", "silver"]
