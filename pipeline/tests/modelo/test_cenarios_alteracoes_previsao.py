"""Grelha de cenários e registo de alterações do método publicados ao lado da previsão."""

import json
from datetime import UTC, date, datetime
from pathlib import Path

import pytest

from contratos.base import Fonte
from contratos.previsao import CenariosPrevisao
from pipeline.comum.erros import ErroFormatoFonte
from pipeline.jobs.previsao import codigo_commit
from pipeline.modelo import alteracoes, cenarios
from pipeline.modelo.previsao import Dados, corte_final, prever
from pipeline.modelo.publicar import montar

AGORA = datetime(2026, 10, 14, tzinfo=UTC)
FONTES = [Fonte(nome="Teste", url="https://example.org", obtida_em=AGORA)]


def _grelha(dados: Dados) -> CenariosPrevisao:
    return cenarios.calcular(
        dados,
        2018,
        corte_final(2018),
        None,
        fontes=FONTES,
        gerado_em=AGORA,
        desvios=(-2.0, 0.0, 2.0),
        fatores=(1.0, 1.5),
    )


def test_cenario_de_base_e_a_previsao_publicada(dados_sinteticos: Dados) -> None:
    grelha = _grelha(dados_sinteticos)
    publicada = prever(dados_sinteticos, 2018)
    base = next(
        c for c in grelha.cenarios if c.desvio_ambiente == 0 and c.fator_erro_sondagens == 1
    )
    assert base.camara.prob_controlo_d == publicada.camara.prob_controlo_d
    assert base.senado.prob_controlo_d == publicada.senado.prob_controlo_d
    assert {c.id: c.prob_d for c in base.corridas_senado} == {
        c.linha.id: c.prob_d for c in publicada.senado.corridas
    }
    assert grelha.ambiente_base == publicada.ambiente.margem
    assert len(grelha.cenarios) == 6


def test_cenarios_deslocam_o_ambiente_no_sentido_certo(dados_sinteticos: Dados) -> None:
    grelha = _grelha(dados_sinteticos)
    por_desvio = {c.desvio_ambiente: c for c in grelha.cenarios if c.fator_erro_sondagens == 1}
    assert por_desvio[2.0].ambiente == pytest.approx(grelha.ambiente_base + 2.0)
    assert por_desvio[2.0].camara.prob_controlo_d > por_desvio[-2.0].camara.prob_controlo_d
    assert por_desvio[2.0].camara.lugares_d_mediana >= por_desvio[-2.0].camara.lugares_d_mediana


def test_cenarios_simetricos(dados_sinteticos: Dados, dados_espelhados: Dados) -> None:
    grelha = _grelha(dados_sinteticos)
    espelho = _grelha(dados_espelhados)
    for c in grelha.cenarios:
        e = next(
            x
            for x in espelho.cenarios
            if x.desvio_ambiente == -c.desvio_ambiente
            and x.fator_erro_sondagens == c.fator_erro_sondagens
        )
        assert e.camara.prob_controlo_d == pytest.approx(c.camara.prob_controlo_r, abs=0.02)
        assert e.senado.prob_controlo_d == pytest.approx(c.senado.prob_controlo_r, abs=0.02)


def test_grelha_sem_o_modelo_publicado_falha(dados_sinteticos: Dados) -> None:
    with pytest.raises(ValueError, match="modelo publicado"):
        cenarios.calcular(
            dados_sinteticos,
            2018,
            corte_final(2018),
            None,
            fontes=FONTES,
            gerado_em=AGORA,
            desvios=(1.0,),
            fatores=(1.0,),
        )


def test_registo_de_alteracoes_versionado_e_valido() -> None:
    raiz = Path(__file__).resolve().parents[3]
    registo = alteracoes.montar(
        2026, fontes=FONTES, gerado_em=AGORA, caminho=raiz / alteracoes.REGISTO
    )
    assert registo.alteracoes
    assert registo.alteracoes[0].camara.antes is None
    assert all(a.camara.antes is not None for a in registo.alteracoes[1:])
    datas = [a.data for a in registo.alteracoes]
    assert datas == sorted(datas)
    assert datas[0] >= date(2026, 10, 13)


def test_registo_fora_de_ordem_falha(tmp_path: Path) -> None:
    entrada = {
        "descricao": "x",
        "pr_url": "https://github.com/tpereira2005/intercalares-eua-2026/pull/1",
        "camara": {"antes": 0.5, "depois": 0.6},
        "senado": {"antes": 0.5, "depois": 0.5},
    }
    caminho = tmp_path / "alteracoes.json"
    caminho.write_text(
        json.dumps([{**entrada, "data": "2026-10-14"}, {**entrada, "data": "2026-10-13"}]),
        encoding="utf-8",
    )
    with pytest.raises(ErroFormatoFonte, match="cronológica"):
        alteracoes.ler(caminho)


@pytest.mark.parametrize(
    ("valor", "esperado"),
    [("ABC1234DEF", "abc1234def"), ("", None), ("não-é-um-sha", None)],
)
def test_codigo_commit(monkeypatch: pytest.MonkeyPatch, valor: str, esperado: str | None) -> None:
    monkeypatch.setenv("GITHUB_SHA", valor)
    assert codigo_commit() == esperado


def test_previsao_leva_o_commit(dados_sinteticos: Dados) -> None:
    ficheiro = montar(
        prever(dados_sinteticos, 2018), fontes=FONTES, gerado_em=AGORA, codigo_commit="abc1234"
    )
    assert ficheiro.codigo_commit == "abc1234"
    assert (
        montar(prever(dados_sinteticos, 2018), fontes=FONTES, gerado_em=AGORA).codigo_commit is None
    )
