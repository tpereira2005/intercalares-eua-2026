"""``ensaio_noite --publicar``: recusa a etiqueta de produção e entrega a outra à recolha."""

import json
import shutil
import subprocess
import time
from datetime import date
from pathlib import Path
from typing import Any

import pytest

from contratos.estados import CodigoEstado
from pipeline.connectors.results.registo import CONECTORES
from pipeline.jobs import ensaio_noite, resultados
from pipeline.jobs.ensaio_noite import (
    ETIQUETA_PRODUCAO,
    Plano,
    caminho_espelho,
    main,
    validar_etiqueta,
)


def test_recusa_a_etiqueta_de_producao(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as saida:
        main(["--publicar", "resultados-2026"])
    assert saida.value.code == 2
    assert "Release de produção" in capsys.readouterr().err
    with pytest.raises(ValueError, match="produção"):
        validar_etiqueta(ETIQUETA_PRODUCAO)
    validar_etiqueta(None)
    validar_etiqueta("resultados-ensaio")


def test_executar_recusa_antes_de_preparar_o_espelho(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="produção"):
        ensaio_noite.executar(
            [CodigoEstado.FL],
            date(2024, 11, 5),
            duracao=1,
            intervalo=1,
            saida=tmp_path / "saida",
            raiz=tmp_path / "espelho",
            descarga=False,
            publicar=ETIQUETA_PRODUCAO,
        )
    assert not (tmp_path / "espelho").exists()


def test_a_etiqueta_chega_a_recolha_e_ao_gh(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    recolhas: list[ensaio_noite.RecolhaObservada] = []
    original = ensaio_noite.RecolhaObservada

    def criar(*args: Any, **kwargs: Any) -> ensaio_noite.RecolhaObservada:
        recolha = original(*args, **kwargs)
        recolhas.append(recolha)
        return recolha

    comandos: list[list[str]] = []

    def falso_run(comando: list[str], **_kw: Any) -> subprocess.CompletedProcess[str]:
        comandos.append(comando)
        return subprocess.CompletedProcess(comando, 0, "", "")

    monkeypatch.setattr(ensaio_noite, "RecolhaObservada", criar)
    monkeypatch.setattr(subprocess, "run", falso_run)
    monkeypatch.setattr(ensaio_noite, "preparar_espelho", lambda *_a, **_k: None)
    monkeypatch.setattr(ensaio_noite, "executar_recolha", _um_envio)
    monkeypatch.setattr(time, "sleep", lambda _s: None)
    monkeypatch.setattr(ensaio_noite, "_latencias", lambda *_a, **_k: [])
    monkeypatch.setattr(ensaio_noite, "_fechar", lambda *_a, **_k: [])

    ensaio_noite.executar(
        [CodigoEstado.FL],
        date(2024, 11, 5),
        duracao=1,
        intervalo=1,
        saida=tmp_path / "saida",
        raiz=tmp_path / "espelho",
        descarga=False,
        publicar="resultados-ensaio",
    )
    assert recolhas[0].publicar == "resultados-ensaio"
    assert comandos == [
        ["gh", "release", "upload", "resultados-ensaio", "parciais.json", "--clobber"]
    ]


def _um_envio(recolha: resultados.Recolha, *_a: Any, **_k: Any) -> int:
    recolha.enviar([Path("parciais.json")])
    return 1


def test_parciais_do_ensaio_saem_reconstruidos(tmp_path: Path) -> None:
    dados = Path(__file__).parent / "dados"
    raiz = tmp_path / "espelho"
    data = date(2024, 11, 5)
    conector = CONECTORES[CodigoEstado.FL]
    for p in conector.pedidos(data, lambda _u: ""):
        destino = caminho_espelho(raiz, p.url)
        destino.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(dados / "fl" / p.ficheiro, destino)
    relatorio = ensaio_noite.executar(
        [CodigoEstado.FL],
        data,
        duracao=2.0,
        intervalo=0.5,
        saida=tmp_path / "saida",
        raiz=raiz,
        descarga=False,
        plano=Plano(falhas=(), alteracoes=()),
        latencia_maxima=5.0,
    )
    assert not relatorio.erros_ensaio
    parciais = json.loads((tmp_path / "saida" / "parciais.json").read_text(encoding="utf-8"))
    assert parciais["reconstruido"] is True
