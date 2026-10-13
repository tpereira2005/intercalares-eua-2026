"""Ficheiro das sondagens para o site: o mesmo método e as mesmas sondagens do modelo."""

from datetime import UTC, date, datetime, timedelta

import pytest

from contratos.base import Fonte
from contratos.sondagens import PontoVotoGenerico, SondagensCongresso, ValorAgregador
from pipeline.modelo import media as metodo
from pipeline.modelo.dados import LinhaModelo
from pipeline.modelo.fontes.sondagens import Sondagem
from pipeline.modelo.previsao import Dados
from pipeline.modelo.publicar_sondagens import corrida, montar, voto_generico

CORTE = date(2026, 10, 13)
AGORA = datetime(2026, 10, 13, 7, tzinfo=UTC)
FONTE = Fonte(nome="Sintética", url="https://example.org/", obtida_em=AGORA)


def _linha(id_: str = "NC-S", lado_d: str = "Ana Silva", lado_r: str = "Rui Costa") -> LinhaModelo:
    return LinhaModelo(
        ano=2026, camara="senado", id=id_, estado=id_[:2], regiao="sul", pvi=0.0,
        incumbente=0, margem=None, certo=None, lado_d=lado_d, lado_r=lado_r,
        lado_d_independente=False,
    )  # fmt: skip


def _sondagem(
    dias: int,
    instituto: str,
    dem: float,
    rep: float,
    *,
    populacao: str = "lv",
    amostra: int | None = 800,
    partidaria: bool = False,
    candidatos: tuple[str, str] = ("Silva", "Costa"),
) -> Sondagem:
    return Sondagem(
        corrida="NC-S", ano=2026, instituto=instituto, fim=CORTE - timedelta(days=dias),
        amostra=amostra, populacao=populacao, partidaria=partidaria, dem=dem, rep=rep,
        candidato_d=candidatos[0], candidato_r=candidatos[1],
    )  # fmt: skip


SONDAGENS = [
    _sondagem(3, "Alfa", 48, 45),
    _sondagem(3, "Alfa", 47, 44, populacao="rv"),  # a mesma sondagem, população pior
    _sondagem(10, "Beta", 44, 47, amostra=None),
    _sondagem(20, "Alfa", 46, 46, partidaria=True),
    _sondagem(90, "Gama", 40, 50),  # fora da janela de 60 dias
]


def test_pesos_dao_a_mesma_media_do_modelo() -> None:
    pesadas = metodo.pesos(SONDAGENS, CORTE)
    m = metodo.media(SONDAGENS, CORTE)
    assert m is not None
    total = sum(p for _, p in pesadas)
    assert sum(p * s.margem for s, p in pesadas) / total == pytest.approx(m.margem, abs=1e-12)
    assert len(pesadas) == m.sondagens == 3
    assert m.institutos == 2


def test_corrida_publica_a_media_os_pesos_e_a_serie() -> None:
    c = corrida(_linha(), SONDAGENS, CORTE)
    m = metodo.media(SONDAGENS, CORTE)
    assert c.media is not None
    assert m is not None
    assert c.media.margem == pytest.approx(m.margem)
    assert c.media.data == CORTE
    assert sum(s.peso for s in c.sondagens) == pytest.approx(1.0)
    fora = [s for s in c.sondagens if s.instituto == "Gama" or s.populacao == "rv"]
    assert [s.peso for s in fora] == [0.0, 0.0]
    assert [s.fim for s in c.sondagens] == sorted((s.fim for s in c.sondagens), reverse=True)
    assert c.serie[-1] == c.media
    assert all(p.data <= CORTE for p in c.serie)
    # A série só tem dias com sondagens na janela e acompanha o método dia a dia.
    dia = CORTE - timedelta(days=15)
    ponto = next(p for p in c.serie if p.data == dia)
    esperado = metodo.media(SONDAGENS, dia)
    assert esperado is not None
    assert ponto.margem == pytest.approx(esperado.margem)


def test_voto_generico_acumula_e_substitui_o_dia() -> None:
    ontem = PontoVotoGenerico(
        data=CORTE - timedelta(days=1),
        margem=7.0,
        agregadores=(ValorAgregador(nome="A", margem=7.0),),
    )
    repetido = ontem.model_copy(update={"data": CORTE, "margem": 1.0})
    serie = voto_generico([ontem, repetido], CORTE, [("A", 8.0), ("B", 9.0)])
    assert [p.data for p in serie] == [CORTE - timedelta(days=1), CORTE]
    assert serie[-1].margem == pytest.approx(8.5)
    assert voto_generico([ontem], CORTE, []) == (ontem,)


def test_montar_usa_so_perguntas_com_os_candidatos_reais() -> None:
    outra = _sondagem(5, "Delta", 30, 60, candidatos=("Outro", "Costa"))
    dados = Dados(
        corridas={}, nacional={}, sondagens=[*SONDAGENS, outra], resultados_senado={},
        composicao={}, redesenhos={},
    )  # fmt: skip
    ficheiro = montar(
        dados,
        2026,
        CORTE,
        [_linha(), _linha("ME-S")],
        [("A", 8.0)],
        anterior=None,
        fontes=[FONTE],
        gerado_em=AGORA,
    )
    SondagensCongresso.model_validate_json(ficheiro.model_dump_json())
    assert [c.id for c in ficheiro.corridas] == ["NC-S"]
    assert all(s.instituto != "Delta" for s in ficheiro.corridas[0].sondagens)
    assert ficheiro.metodo.meia_vida_dias == metodo.MEIA_VIDA_DIAS
    assert len(ficheiro.voto_generico) == 1
