"""Leitura das tabelas anuais e das tabelas de sondagens da Wikipédia (excertos sintéticos
com a mesma marcação das páginas reais, sem dados de eleitores)."""

from datetime import date

import pytest

from pipeline.modelo.fontes.corridas import ler_pagina
from pipeline.modelo.fontes.sondagens import data_final, ler_pagina_corrida
from pipeline.modelo.fontes.wikitexto import celulas, grelha, pvi, texto_simples

CAMARA = """
{| class="wikitable"
|-
! {{ushr|Alabama|7|X}}
| {{shading PVI|D|value=12}}
| {{sortname|Ana|Silva}}
| {{party shading/Democratic}} | Democratic
| 2010
| Incumbent re-elected.
|nowrap |{{plainlist}}
*{{Party stripe|Republican Party (US)}}Rui Costa (Republican)
*{{Party stripe|Democratic Party (US)}}[[Ana Silva]] (Democratic)
{{endplainlist}}
|}
{| class="wikitable"
|-
! {{ushr|TN|4|X}}
| {{shading PVI|R|20}}
| {{sortname|Rita|Neves}}
| style="background-color:#FFB6B6" | Republican
| 2010
| Incumbent renominated
|nowrap |{{plainlist}}
*{{Party stripe|Independent (US)}}Eva Lopes (Independent)
*{{Party stripe|Republican Party (US)}}[[Rita Neves]] (Republican)
{{Party stripe|Democratic Party (US)}}Paulo Reis (Democratic){{endplainlist}}
|-
! {{ushr|TN|5|X}}
| {{shading PVI|EVEN}}
| {{sortname|Joana|Matos}}
| style="background-color:#B0CEFF" | Democratic
| 2018
| Incumbent re-elected.
| nowrap | {{Plainlist |*{{Party stripe|Republican Party (US)}}Hugo Pinto (Republican) 48.0%
*{{Party stripe|Democratic Party (US)}}Joana Matos (Democratic) 51.5%
}}{{collapsible list|title={{nobold|Others}}
| {{Party stripe|Green Party (US)}}Lia Moura (Green) 0.5%
|}}
|}
"""

SONDAGENS = """
== General election ==
=== Polling ===
{| class="wikitable"
! Poll source
! Date(s) administered
! Sample size
! Margin of error
! Ana Silva (D)
! Rui Costa (R)
|-
| Instituto Alfa (R)
| rowspan="2" | October 20\u201324, 2026
| 800 (LV)
| ± 3.5%
| 47%
| 46%
|-
| Instituto Beta
| 1,000 (RV)
| ± 3.1%
| 45%
| 44%
|}
"""


def test_celulas_respeitam_predefinicoes() -> None:
    assert celulas("| {{a|b}} || [[c|d]]\n! e !! f") == [" {{a|b}} ", " [[c|d]]", " e ", " f"]


@pytest.mark.parametrize(
    ("texto", "valor"),
    [
        ("{{shading PVI|R|15}}", -15.0),
        ("{{shading PVI|D|value=1}}", 1.0),
        ("{{sort|115|R+15}}", -15.0),
        ("| D+5", 5.0),
        ("{{shading PVI|EVEN}}", 0.0),
        ("Democratic", None),
    ],
)
def test_pvi(texto: str, valor: float | None) -> None:
    assert pvi(texto) == valor


def test_texto_simples() -> None:
    assert (
        texto_simples("'''[[Ana Silva|Ana]]''' {{sortname|Rui|Costa}}<br/>x") == "Ana Rui Costa x"
    )


def test_grelha_expande_rowspan() -> None:
    linhas = grelha('|-\n| a\n| rowspan="2" | b\n| c\n|-\n| d\n| e')
    assert [len(x) for x in linhas] == [3, 3]
    assert "b" in linhas[1][1]


def test_le_candidatos_em_todos_os_formatos() -> None:
    corridas = {c.id: c for c in ler_pagina(CAMARA, 2026, "camara")}
    al = corridas["AL-07"]
    assert al.pvi == 12.0
    assert [(c.nome, c.partido) for c in al.candidatos] == [("Rui Costa", "R"), ("Ana Silva", "D")]
    assert al.incumbentes == [("Ana Silva", "D")]
    tn4 = corridas["TN-04"]
    assert [c.partido for c in tn4.candidatos] == ["O", "R", "D"]
    tn5 = corridas["TN-05"]
    assert tn5.pvi == 0.0
    assert [(c.nome, c.percentagem) for c in tn5.candidatos] == [
        ("Hugo Pinto", 48.0),
        ("Joana Matos", 51.5),
    ]


def test_data_final() -> None:
    assert data_final("October 20\u201324, 2026") == date(2026, 10, 24)
    assert data_final("Sep 28 \u2013 Oct 2, 2026") == date(2026, 10, 2)


def test_le_sondagens_da_corrida() -> None:
    sondagens = ler_pagina_corrida(SONDAGENS, "AL-S", 2026, "Silva", "Costa")
    assert [(s.instituto, s.partidaria, s.populacao, s.margem) for s in sondagens] == [
        ("Instituto Alfa", True, "lv", 1.0),
        ("Instituto Beta", False, "rv", 1.0),
    ]
    assert all(s.fim == date(2026, 10, 24) for s in sondagens)
    assert sondagens[0].candidato_d == "Ana Silva"
