"""Ajustes da análise de sensibilidade: neutros por omissão, simétricos e no sentido certo."""

from datetime import date

import pytest

from pipeline.jobs.sensibilidade_previsao import TRACO, VARIANTES, markdown
from pipeline.modelo.previsao import (
    AJUSTES_PUBLICADOS,
    Ajustes,
    Dados,
    desvio_incumbentes,
    erro_nacional,
    prever,
    vies_voto_generico,
)


def test_ajustes_por_omissao_sao_o_modelo_publicado(dados_sinteticos: Dados) -> None:
    publicado = prever(dados_sinteticos, 2018)
    explicito = prever(dados_sinteticos, 2018, ajustes=Ajustes())
    assert explicito.camara.prob_controlo_d == publicado.camara.prob_controlo_d
    assert explicito.senado.prob_controlo_d == publicado.senado.prob_controlo_d
    assert (explicito.camara.lugares_d == publicado.camara.lugares_d).all()


def test_desvio_do_ambiente_e_simetrico(dados_sinteticos: Dados, dados_espelhados: Dados) -> None:
    mais = prever(dados_sinteticos, 2018, ajustes=Ajustes(desvio_ambiente=2.0))
    espelho = prever(dados_espelhados, 2018, ajustes=Ajustes(desvio_ambiente=-2.0))
    assert espelho.ambiente.margem == pytest.approx(-mais.ambiente.margem, abs=1e-9)
    assert espelho.camara.prob_controlo_d == pytest.approx(mais.camara.prob_controlo_r, abs=0.02)
    assert espelho.senado.prob_controlo_d == pytest.approx(mais.senado.prob_controlo_r, abs=0.02)


def test_ambiente_melhor_para_um_lado_aumenta_a_sua_probabilidade(dados_sinteticos: Dados) -> None:
    menos = prever(dados_sinteticos, 2018, ajustes=Ajustes(desvio_ambiente=-2.0))
    mais = prever(dados_sinteticos, 2018, ajustes=Ajustes(desvio_ambiente=2.0))
    assert mais.camara.prob_controlo_d > menos.camara.prob_controlo_d
    assert mais.senado.prob_controlo_d >= menos.senado.prob_controlo_d


def test_mais_erro_nacional_alarga_os_lugares(dados_sinteticos: Dados) -> None:
    base = prever(dados_sinteticos, 2018)
    largo = prever(dados_sinteticos, 2018, ajustes=Ajustes(fator_sd_nacional=1.5))
    assert largo.ambiente.sd == pytest.approx(1.5 * base.ambiente.sd)
    assert largo.camara.lugares_d.std() > base.camara.lugares_d.std()


def test_sem_sondagens_do_senado_so_mexe_no_senado(dados_sinteticos: Dados) -> None:
    base = prever(dados_sinteticos, 2018)
    sem = prever(dados_sinteticos, 2018, ajustes=Ajustes(sem_sondagens_senado=True))
    assert sem.ambiente == base.ambiente
    assert all(c.sondagens is None for c in sem.senado.corridas)
    assert any(c.sondagens is not None for c in base.senado.corridas)


def test_correcao_dos_incumbentes_e_simetrica(
    dados_sinteticos: Dados, dados_espelhados: Dados
) -> None:
    assert desvio_incumbentes(dados_espelhados, 2018) == pytest.approx(
        desvio_incumbentes(dados_sinteticos, 2018), abs=1e-9
    )
    ajustes = Ajustes(incumbentes_sondagens=True)
    normal = prever(dados_sinteticos, 2018, ajustes=ajustes)
    espelho = prever(dados_espelhados, 2018, ajustes=ajustes)
    assert espelho.camara.prob_controlo_d == pytest.approx(normal.camara.prob_controlo_r, abs=0.02)
    assert espelho.senado.prob_controlo_d == pytest.approx(normal.senado.prob_controlo_r, abs=0.02)


def test_vies_do_voto_generico_encolhe_e_troca_de_sinal() -> None:
    erros = {2014: 3.0, 2016: 1.0, 2018: -1.0}
    assert vies_voto_generico(erros) == pytest.approx(3.0 / 5)
    assert vies_voto_generico({a: -e for a, e in erros.items()}) == pytest.approx(-3.0 / 5)
    assert vies_voto_generico({}) == 0.0


def test_correcao_do_vies_e_simetrica(dados_sinteticos: Dados, dados_espelhados: Dados) -> None:
    ajustes = Ajustes(vies_generico=True)
    normal = prever(dados_sinteticos, 2018, ajustes=ajustes)
    espelho = prever(dados_espelhados, 2018, ajustes=ajustes)
    assert espelho.ambiente.margem == pytest.approx(-normal.ambiente.margem, abs=1e-9)
    assert espelho.senado.prob_controlo_d == pytest.approx(normal.senado.prob_controlo_r, abs=0.02)


def test_erro_do_ambiente_mede_se_a_mesma_distancia(dados_sinteticos: Dados) -> None:
    final, _ = erro_nacional(dados_sinteticos, 2018)
    explicito, _ = erro_nacional(dados_sinteticos, 2018, dias_antes=2)
    assert explicito == final
    cedo = prever(dados_sinteticos, 2018, corte=date(2018, 10, 25))
    longe, _ = erro_nacional(dados_sinteticos, 2018, dias_antes=12)
    assert cedo.ambiente.sd == pytest.approx(longe)
    assert longe != final


def test_variantes_do_ambiente_vem_aos_pares() -> None:
    desvios = sorted(v.ajustes.desvio_ambiente for v in VARIANTES if v.ajustes.desvio_ambiente)
    assert desvios == sorted(-d for d in desvios)
    assert VARIANTES[0].ajustes == AJUSTES_PUBLICADOS


def test_tabela_em_portugues() -> None:
    linha: dict[str, object] = {
        "variante": "Modelo publicado",
        "camara": {
            "prob_controlo_d": 0.9675,
            "lugares_d_mediana": 242,
            "lugares_d_p10": 225,
            "lugares_d_p90": 263,
        },
        "senado": {
            "prob_controlo_d": 0.7254,
            "lugares_d_mediana": 52,
            "lugares_d_p10": 48,
            "lugares_d_p90": 56,
        },
        "backtests": {
            "camara": {"brier": 0.0304, "cobertura_80": 0.9},
            "senado": {"brier": 0.038, "cobertura_80": 0.88},
        },
    }
    tabela = markdown([linha])
    assert f"| Modelo publicado | 97% | 242 (225{TRACO}263) | 73% | 52 (48{TRACO}56) |" in tabela
    assert "0,030 | 0,038 | 90% | 88% |" in tabela
