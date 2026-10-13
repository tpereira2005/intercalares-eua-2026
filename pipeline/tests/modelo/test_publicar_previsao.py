"""O ficheiro publicado valida o contrato e os backtests comparam com os resultados."""

from datetime import UTC, datetime

from contratos.base import Fonte
from contratos.previsao import PrevisaoCongresso
from pipeline.modelo.previsao import Dados, prever
from pipeline.modelo.publicar import avaliar, montar


def test_montar_valida_o_contrato(dados_sinteticos: Dados) -> None:
    previsao = prever(dados_sinteticos, 2018)
    agora = datetime(2018, 11, 4, tzinfo=UTC)
    fonte = Fonte(nome="Sintética", url="https://example.org/", obtida_em=agora)
    ficheiro = montar(
        previsao,
        fontes=[fonte],
        gerado_em=agora,
        agregadores=[("Agregador", 1.5)],
        backtests=avaliar(previsao, dados_sinteticos),
    )
    copia = PrevisaoCongresso.model_validate_json(ficheiro.model_dump_json())
    assert copia == ficheiro
    assert ficheiro.congelada
    assert ficheiro.peso_voto_antecipado == 0.0
    assert len(ficheiro.corridas) == len(previsao.camara.corridas) + len(previsao.senado.corridas)
    for resumo in (ficheiro.camara, ficheiro.senado):
        assert abs(sum(p.probabilidade for p in resumo.distribuicao) - 1.0) < 1e-9
        assert resumo.lugares_d_p10 <= resumo.lugares_d_mediana <= resumo.lugares_d_p90
    assert ficheiro.senado.lugares_fora_de_jogo_d + ficheiro.senado.lugares_fora_de_jogo_r == 70
    assert {b.camara for b in ficheiro.backtests} == {"camara", "senado"}


def test_backtest_conta_os_lugares_reais(dados_sinteticos: Dados) -> None:
    previsao = prever(dados_sinteticos, 2018)
    camara = next(b for b in avaliar(previsao, dados_sinteticos) if b.camara == "camara")
    reais = 0
    for c in dados_sinteticos.corridas[2018]:
        d, r = (x.percentagem or 0.0 for x in c.candidatos)
        reais += c.camara == "camara" and d > r
    assert camara.lugares_d_reais == reais
    assert 0.0 <= camara.cobertura_80 <= 1.0
