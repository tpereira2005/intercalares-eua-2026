"""Sondagens dos distritos da Câmara (só para o site), lidas da página de cada estado."""

from datetime import UTC, date, datetime

from contratos.base import Fonte
from pipeline.modelo.dados import LinhaModelo
from pipeline.modelo.fontes.sondagens import ler_pagina_corrida, seccao_distrito
from pipeline.modelo.previsao import Dados
from pipeline.modelo.publicar_sondagens import montar

TABELA = """{| class="wikitable"
! Poll source
! Date(s) administered
! Sample size
! Margin of error
! Ana Silva (D)
! Rui Costa (R)
|-
| Alfa Research
| September 10\u201314, 2026
| 600 (LV)
| ± 4.0%
| 47%
| 44%
|}"""

PRIMARIA = """{| class="wikitable"
! Poll source
! Date(s) administered
! Sample size
! Margin of error
! Ana Silva
! Outro Nome
|-
| Beta Polls
| June 1\u20133, 2026
| 400 (LV)
| ± 5.0%
| 30%
| 25%
|}"""

PAGINA = f"""Introdução.
==District 1==
===Democratic primary===
====Polling====
{PRIMARIA}
===General election===
====Polling====
{TABELA}
==District 2==
===General election===
====Polling====
{TABELA.replace("47%", "40%")}
"""


def _linha(id_: str) -> LinhaModelo:
    return LinhaModelo(
        ano=2026, camara="camara", id=id_, estado=id_[:2], regiao="nordeste", pvi=0.0,
        incumbente=0, margem=None, certo=None, lado_d="Ana Silva", lado_r="Rui Costa",
        lado_d_independente=False,
    )  # fmt: skip


def test_seccao_do_distrito_so_tem_a_eleicao_geral() -> None:
    seccao = seccao_distrito(PAGINA, 1)
    assert seccao is not None
    lidas = ler_pagina_corrida(seccao, "PA-01", 2026, "Silva", "Costa")
    assert [(s.instituto, s.margem) for s in lidas] == [("Alfa Research", 3.0)]
    assert lidas[0].fim == date(2026, 9, 14)
    dois = seccao_distrito(PAGINA, 2)
    assert dois is not None
    assert [s.margem for s in ler_pagina_corrida(dois, "PA-02", 2026, "Silva", "Costa")] == [-4.0]
    assert seccao_distrito(PAGINA, 3) is None


def test_distritos_entram_no_ficheiro_sem_entrar_no_modelo() -> None:
    agora = datetime(2026, 10, 13, tzinfo=UTC)
    dados = Dados(
        corridas={}, nacional={}, sondagens=[], resultados_senado={}, composicao={},
        redesenhos={},
    )  # fmt: skip
    seccao = seccao_distrito(PAGINA, 1)
    assert seccao is not None
    lidas = ler_pagina_corrida(seccao, "PA-01", 2026, "Silva", "Costa")
    ficheiro = montar(
        dados,
        2026,
        date(2026, 10, 13),
        [],
        [],
        anterior=None,
        fontes=[Fonte(nome="Sintética", url="https://example.org/", obtida_em=agora)],
        gerado_em=agora,
        linhas_camara=[_linha("PA-01"), _linha("PA-02")],
        sondagens_camara={"PA-01": lidas, "PA-02": []},
    )
    assert [(c.id, c.camara) for c in ficheiro.corridas] == [("PA-01", "camara")]
    assert ficheiro.corridas[0].media is not None
    # As sondagens da Câmara não passam para os dados do modelo.
    assert dados.sondagens == []
