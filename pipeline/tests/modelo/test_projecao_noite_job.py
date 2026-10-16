"""Job da noite eleitoral: histórico, verificações e ciclo de publicação."""

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from contratos.base import Fonte, Metadados
from contratos.noite import HistoricoNoite, ProjecaoNoite
from contratos.previsao import PrevisaoCongresso
from contratos.resultados import ResultadosParciais, UnidadeContagem
from pipeline.comum.erros import ErroDescarga
from pipeline.jobs.projecao_noite import (
    Noite,
    ProjecaoIncoerente,
    ano_referencia,
    executar,
    main,
    verificar,
)
from pipeline.modelo.noite.historico import HistoricoIncompativel, acrescentar, ponto
from pipeline.modelo.previsao import Dados, prever
from pipeline.modelo.publicar import montar

AGORA = datetime(2018, 11, 6, 20, tzinfo=UTC)
FONTE = Fonte(nome="Sintética", url="https://example.org/", obtida_em=AGORA)
SIMULACOES = 2000


@pytest.fixture(scope="module")
def previsao(dados_sinteticos: Dados) -> PrevisaoCongresso:
    previsao = montar(prever(dados_sinteticos, 2018), fontes=[FONTE], gerado_em=AGORA)
    lugares = sum(c.camara == "camara" for c in previsao.corridas)
    camara = previsao.camara.model_copy(
        update={"lugares_total": lugares, "maioria": lugares // 2 + 1}
    )
    return previsao.model_copy(update={"camara": camara})


def _disputada(previsao: PrevisaoCongresso, camara: str) -> str:
    return next(c.id for c in previsao.corridas if c.camara == camara and c.decidida is None)


def _parciais(
    previsao: PrevisaoCongresso, instante: datetime, fracao: float, *, reconstruido: bool = False
) -> ResultadosParciais:
    unidades = tuple(
        UnidadeContagem(
            corrida=_disputada(previsao, camara),
            unidade="total",
            votos_d=int(50_000 * fracao),
            votos_r=int(48_000 * fracao),
            votos_outros=int(2_000 * fracao),
            percentagem_contada=fracao,
        )
        for camara in ("camara", "senado")
        if fracao > 0
    )
    return ResultadosParciais(
        metadados=Metadados(gerado_em=instante, fontes=(FONTE,)),
        ano=previsao.ano,
        instante=instante,
        reconstruido=reconstruido,
        unidades=unidades,
    )


def _noite(previsao: PrevisaoCongresso, saida: Path) -> Noite:
    return Noite(
        previsao=previsao,
        referencia={},
        fontes=(FONTE,),
        saida=saida,
        desempate="R",
        simulacoes=SIMULACOES,
    )


def test_ano_de_referencia_e_a_presidencial_anterior() -> None:
    assert ano_referencia(2026) == 2024
    assert ano_referencia(2024) == 2020
    assert ano_referencia(2022) == 2020


def test_processar_escreve_e_ignora_instantes_repetidos(
    previsao: PrevisaoCongresso, tmp_path: Path
) -> None:
    noite = _noite(previsao, tmp_path)
    escritos = noite.processar(_parciais(previsao, AGORA, 0.3))
    assert [p.name for p in escritos] == ["projecao-noite-2018.json", "historico-noite-2018.json"]
    projecao = ProjecaoNoite.model_validate_json(escritos[0].read_text(encoding="utf-8"))
    historico = HistoricoNoite.model_validate_json(escritos[1].read_text(encoding="utf-8"))
    assert projecao.instante == AGORA
    assert projecao.metadados.fontes == (FONTE,)
    assert {c.id for c in historico.pontos[-1].corridas} == {
        _disputada(previsao, "camara"),
        _disputada(previsao, "senado"),
    }
    assert noite.processar(_parciais(previsao, AGORA, 0.4)) == []
    assert noite.processar(_parciais(previsao, AGORA - timedelta(minutes=1), 0.4)) == []
    assert len(noite.processar(_parciais(previsao, AGORA + timedelta(minutes=1), 0.5))) == 2


def test_reconstrucao_fica_marcada(previsao: PrevisaoCongresso, tmp_path: Path) -> None:
    noite = _noite(previsao, tmp_path)
    noite.processar(_parciais(previsao, AGORA, 0.3, reconstruido=True))
    assert noite.historico is not None
    assert noite.historico.reconstruido
    projecao_json, _ = noite.caminhos
    assert ProjecaoNoite.model_validate_json(projecao_json.read_bytes()).reconstruido


def test_resultados_de_outro_ano_sao_rejeitados(
    previsao: PrevisaoCongresso, tmp_path: Path
) -> None:
    parciais = _parciais(previsao, AGORA, 0.3).model_copy(update={"ano": 2026})
    with pytest.raises(ProjecaoIncoerente):
        _noite(previsao, tmp_path).processar(parciais)


def test_verificar_rejeita_corridas_em_falta(previsao: PrevisaoCongresso, tmp_path: Path) -> None:
    noite = _noite(previsao, tmp_path)
    noite.processar(_parciais(previsao, AGORA, 0.3))
    projecao_json, _ = noite.caminhos
    projecao = ProjecaoNoite.model_validate_json(projecao_json.read_bytes())
    verificar(projecao, previsao)
    incompleta = projecao.model_copy(update={"corridas": projecao.corridas[1:]})
    with pytest.raises(ProjecaoIncoerente, match="corridas"):
        verificar(incompleta, previsao)


def test_historico_espaca_pontos_e_guarda_sempre_o_ultimo(
    previsao: PrevisaoCongresso, tmp_path: Path
) -> None:
    noite = _noite(previsao, tmp_path)
    minutos = [0, 1, 2, 6, 7, 8, 13]
    for i, m in enumerate(minutos):
        noite.processar(_parciais(previsao, AGORA + timedelta(minutes=m), 0.1 + 0.1 * i))
    assert noite.historico is not None
    guardados = [(p.instante - AGORA) / timedelta(minutes=1) for p in noite.historico.pontos]
    assert guardados == [0, 6, 13]
    assert noite.historico.intervalo_minutos == 5


def test_historico_nao_mistura_previsoes(previsao: PrevisaoCongresso, tmp_path: Path) -> None:
    noite = _noite(previsao, tmp_path)
    noite.processar(_parciais(previsao, AGORA, 0.3))
    assert noite.historico is not None
    projecao_json, _ = noite.caminhos
    projecao = ProjecaoNoite.model_validate_json(projecao_json.read_bytes())
    outra = projecao.model_copy(update={"corte_prior": projecao.corte_prior - timedelta(days=1)})
    with pytest.raises(HistoricoIncompativel):
        acrescentar(noite.historico, outra)
    assert ponto(projecao) == noite.historico.pontos[-1]


def test_ciclo_que_falha_nao_apaga_o_ultimo_ficheiro(
    previsao: PrevisaoCongresso, tmp_path: Path
) -> None:
    noite = _noite(previsao, tmp_path)
    respostas: list[ResultadosParciais | Exception] = [
        _parciais(previsao, AGORA, 0.3),
        ErroDescarga("fonte em baixo"),
        _parciais(previsao, AGORA, 0.3),
    ]

    def obter() -> ResultadosParciais | None:
        resposta = respostas.pop(0)
        if isinstance(resposta, Exception):
            raise resposta
        return resposta

    publicados = 0
    for _ in range(3):
        publicados += executar(noite, obter, intervalo=0.0, duracao=None)
    assert publicados == 1
    projecao_json, historico_json = noite.caminhos
    assert projecao_json.exists()
    assert len(HistoricoNoite.model_validate_json(historico_json.read_bytes()).pontos) == 1


@pytest.mark.parametrize(
    "argumentos",
    [
        ["--parciais", "parciais.json"],
        ["--parciais", "parciais.json", "--backtest", "2024", "--previsao", "p.json"],
        ["--parciais", "parciais.json", "--backtest", "2026"],
    ],
)
def test_parciais_exigem_uma_so_previsao_de_partida(argumentos: list[str]) -> None:
    with pytest.raises(SystemExit):
        main(argumentos)
