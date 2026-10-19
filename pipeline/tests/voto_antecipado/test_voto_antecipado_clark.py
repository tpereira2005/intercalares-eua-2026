"""Clark County: afluência presencial agregada, usada para conferir o Nevada.

O ficheiro de exemplo é um corte da página real de 18 de outubro de 2026 (três locais de voto,
totais ajustados para baterem certo), só com agregados. Nenhum teste faz pedidos à rede.
"""

import dataclasses
import logging
from datetime import UTC, date, datetime
from pathlib import Path

import pytest

from contratos.estados import CodigoEstado
from contratos.voto_antecipado_agregado import VotoAntecipadoAgregado
from pipeline.comum.descarga import Descarga
from pipeline.connectors.early_vote.clark import fontes as fontes_clark
from pipeline.connectors.early_vote.clark.ler import ErroFormatoClark, ler_afluencia
from pipeline.connectors.early_vote.uf import fontes as fontes_uf
from pipeline.connectors.early_vote.uf.ler import ler_csv
from pipeline.jobs import voto_antecipado_uf as job

DADOS = Path(__file__).parent / "dados"
HTML = (DADOS / "clark_evturnout_exemplo.html").read_text(encoding="utf-8")
CSV_UF = (DADOS / "uf_us_exemplo.csv").read_text(encoding="utf-8")
AVISO = (
    "Conferência oficial: o Clark County (Las Vegas) conta 3\u00a0335 votos presenciais até "
    "18/10, segundo a página oficial do condado."
)
FRASE_ABAIXO = "O total presencial do estado ainda não os inclui todos"


def test_le_o_acumulado_e_so_os_dias_com_valor() -> None:
    afluencia = ler_afluencia(HTML)
    assert afluencia.acumulado == 3_335
    assert afluencia.por_dia == {date(2026, 10, 17): 2_161, date(2026, 10, 18): 1_174}
    assert afluencia.ultimo_dia == date(2026, 10, 18)


def test_aceita_uma_so_semana_e_soma_os_locais_sem_linha_de_totais() -> None:
    segunda = HTML.index('<table id="tblDaily">', HTML.index('<table id="tblDaily">') + 1)
    semana_1 = HTML[:segunda]
    sem_totais = "\n".join(x for x in semana_1.splitlines() if "Daily Totals" not in x)
    afluencia = ler_afluencia(sem_totais + "</td></tr></table></body></html>")
    assert afluencia.por_dia == {date(2026, 10, 17): 2_161, date(2026, 10, 18): 1_174}


@pytest.mark.parametrize(
    ("antigo", "novo", "mensagem"),
    [
        ("Accumulated Total", "Total", "Accumulated Total"),
        ("<b>3,335</b>", "<b>3,336</b>", "acumulado"),
        ("<span>954</span>", "<span>955</span>", "somam"),
        ("<span>513</span>", "<span>5x3</span>", "inteiro"),
        ("<span>10/17</span>", "<span>17 Oct</span>", "cabeçalho"),
        ("<span>Totals</span>", "<span>Soma</span>", "Totals"),
        ("Early Voting Site", "Local", "tabelas semanais"),
    ],
)
def test_html_inesperado_levanta_erro(antigo: str, novo: str, mensagem: str) -> None:
    assert antigo in HTML
    with pytest.raises(ErroFormatoClark, match=mensagem):
        ler_afluencia(HTML.replace(antigo, novo))


def test_pagina_sem_tabelas_levanta_erro() -> None:
    with pytest.raises(ErroFormatoClark):
        ler_afluencia("<html><body>Manutenção</body></html>")


def _simular(monkeypatch: pytest.MonkeyPatch, html: str | Exception) -> list[str]:
    """Substitui a descarga: o UF devolve o CSV de exemplo e Clark ``html`` (ou falha)."""
    pedidos: list[str] = []

    def falsa(url: str, destino: Path, **_: object) -> Descarga:
        pedidos.append(url)
        destino.parent.mkdir(parents=True, exist_ok=True)
        if url == fontes_clark.URL:
            if isinstance(html, Exception):
                raise html
            destino.write_text(html, encoding="utf-8")
        else:
            destino.write_text(CSV_UF, encoding="utf-8")
        return Descarga(url, destino, True, None, None, datetime.now(UTC))

    monkeypatch.setattr(job, "descarregar", falsa)
    return pedidos


def _nv(pasta: Path) -> VotoAntecipadoAgregado:
    return VotoAntecipadoAgregado.model_validate_json((pasta / "nv.json").read_text("utf-8"))


def test_job_com_clark_acrescenta_fonte_oficial_e_aviso(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pedidos = _simular(monkeypatch, HTML)
    pasta = tmp_path / "publicado"
    job.executar(tmp_path, pasta, tmp_path / "h.csv", descarregar_=True)
    assert pedidos.count(fontes_clark.URL) == 1  # só a página agregada, uma vez
    assert (tmp_path / "data" / "brutos" / "clark" / "evturnout.html").exists()
    nv = _nv(pasta)
    assert [(str(f.url), f.oficial) for f in nv.metadados.fontes] == [
        (fontes_uf.CSV, False),
        (fontes_clark.URL, True),
    ]
    assert nv.metadados.fontes[1].licenca == fontes_clark.LICENCA
    assert any(a.startswith(AVISO) and FRASE_ABAIXO in a for a in nv.avisos)
    # Só os avisos e as fontes mudam: o total do UF fica como estava.
    assert nv.ciclos[0].votos == 31_516
    # Os outros estados não levam a conferência.
    ga = VotoAntecipadoAgregado.model_validate_json((pasta / "ga.json").read_text("utf-8"))
    assert len(ga.metadados.fontes) == 1
    assert not any("Clark" in a for a in ga.avisos)


@pytest.mark.parametrize(
    "falha",
    [
        OSError("sem rede"),
        "<html><body>Manutenção</body></html>",
        HTML.replace("<b>3,335</b>", "<b>9,999</b>"),
    ],
)
def test_job_com_clark_a_falhar_publica_o_nevada_como_hoje(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    falha: str | Exception,
) -> None:
    _simular(monkeypatch, falha)
    pasta = tmp_path / "publicado"
    with caplog.at_level(logging.WARNING):
        totais = job.executar(tmp_path, pasta, tmp_path / "h.csv", descarregar_=True)
    assert totais["NV"] == 31_516
    nv = _nv(pasta)
    assert [f.oficial for f in nv.metadados.fontes] == [False]
    assert not any("Clark" in a for a in nv.avisos)
    assert any("Clark County" in r.message and r.levelname == "WARNING" for r in caplog.records)


def test_sem_descarga_e_sem_copia_local_nao_ha_conferencia(tmp_path: Path) -> None:
    pasta_uf = tmp_path / "data" / "brutos" / "uf"
    pasta_uf.mkdir(parents=True)
    (pasta_uf / "US.csv").write_text(CSV_UF, encoding="utf-8")
    job.executar(tmp_path, tmp_path / "p", tmp_path / "h.csv", descarregar_=False)
    assert len(_nv(tmp_path / "p").metadados.fontes) == 1


def test_frase_do_total_do_estado_so_quando_clark_tem_mais(tmp_path: Path) -> None:
    caminho = tmp_path / "data" / "brutos" / "clark" / "evturnout.html"
    caminho.parent.mkdir(parents=True)
    caminho.write_text(HTML, encoding="utf-8")
    nevada = next(r for r in ler_csv(CSV_UF, [CodigoEstado.NV]) if r.estado.value == "NV")
    menos = job.conferir_nevada(tmp_path, nevada, descarregar_=False)
    mais = job.conferir_nevada(
        tmp_path, dataclasses.replace(nevada, presencial=3_335), descarregar_=False
    )
    assert menos is not None
    assert mais is not None
    assert FRASE_ABAIXO in menos[1][0]
    assert mais[1] == (AVISO,)
