"""Ensaio de ponta a ponta, em versão curta, contra o espelho local com falhas injetadas.

Usa os ficheiros pequenos de ``dados/`` (Florida, Geórgia e Alasca, 2024), sem rede. A
Florida nunca falha; a Geórgia e o Alasca recebem todos os tipos de falha em janelas
curtas. Todos os invariantes têm de passar, incluindo os de tempo: os estados correm em
paralelo, por isso a fonte lenta e o 429 só atrasam o próprio estado.
"""

import shutil
from datetime import date
from pathlib import Path

import httpx

from contratos.estados import CodigoEstado
from pipeline.connectors.results.registo import CONECTORES
from pipeline.jobs.ensaio_noite import (
    Alteracao,
    Falha,
    Plano,
    caminho_espelho,
    executar,
    para_markdown,
)

DADOS = Path(__file__).parent / "dados"
DATA = date(2024, 11, 5)
ESTADOS = [CodigoEstado.FL, CodigoEstado.GA, CodigoEstado.AK]
FL = "flelectionfiles.floridados.gov"
GA = "results.sos.ga.gov"
AK = "www.elections.alaska.gov"
INTERVALO = 0.5


def _espelho(raiz: Path) -> None:
    for estado in ESTADOS:
        conector = CONECTORES[estado]
        for p in conector.pedidos(DATA, lambda _u: ""):
            destino = caminho_espelho(raiz, p.url)
            destino.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(DADOS / estado.value.lower() / p.ficheiro, destino)


PLANO = Plano(
    falhas=(
        Falha(AK, 0.5, 4.2, "ausente"),
        Falha(GA, 0.8, 1.6, "corrompido"),
        Falha(GA, 1.6, 2.4, "vazio"),
        Falha(AK, 4.4, 4.9, "bloqueio"),
        Falha(GA, 5.6, 6.2, "erro_servidor"),
        Falha(AK, 4.9, 5.6, "limite"),
        Falha(GA, 7.4, 8.4, "lento"),
    ),
    alteracoes=(
        Alteracao(FL, 2.0),
        Alteracao(FL, 9.0),
        Alteracao(GA, 4.0),
        Alteracao(AK, 6.5),
    ),
)


def test_ensaio_curto_com_todas_as_falhas(tmp_path: Path) -> None:
    raiz = tmp_path / "espelho"
    _espelho(raiz)
    cliente = httpx.Client(timeout=httpx.Timeout(0.4))
    relatorio = executar(
        ESTADOS,
        DATA,
        duracao=12.0,
        intervalo=INTERVALO,
        saida=tmp_path / "saida",
        raiz=raiz,
        descarga=False,
        plano=PLANO,
        cliente=cliente,
        lento_s=1.0,
        retry_after=1,
        latencia_maxima=5.0,
    )
    cliente.close()
    assert not relatorio.erros_ensaio
    assert relatorio.falhados() == [], para_markdown(relatorio)
    # Todos os tipos de falha foram servidos e o Alasca chegou a alerta e recuperou.
    assert {p.falha for p in relatorio.pedidos if p.falha} == {
        "ausente", "corrompido", "vazio", "erro_servidor", "bloqueio", "lento", "limite",
    }  # fmt: skip
    assert relatorio.max_falhas["AK"] >= 6
    # A Florida, sempre saudável, nunca falhou e todas as alterações chegaram a parciais.json.
    assert relatorio.max_falhas["FL"] == 0
    assert len(relatorio.latencias) == 4
    assert all(x.escrita_s is not None for x in relatorio.latencias)
    assert "Resultado" in para_markdown(relatorio)
