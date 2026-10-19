"""UF Election Lab: ``US.csv`` dos estados que bloqueiam a recolha (fonte não oficial).

O ficheiro de exemplo é um corte do ``US.csv`` real de 16 de outubro de 2026 (cabeçalho e
as linhas de GA, MI, NV, OH, TX e AZ), só com totais agregados por estado. Nenhum teste faz
pedidos à rede.
"""

import csv
import io
from datetime import date
from pathlib import Path

import polars as pl
import pytest

from contratos.estados import CodigoEstado
from contratos.voto_antecipado_agregado import VotoAntecipadoAgregado
from pipeline.comum.erros import ErroFormatoFonte
from pipeline.connectors.early_vote.uf import estados as estados_uf
from pipeline.connectors.early_vote.uf.estados import ESTADOS, OFICIAIS
from pipeline.connectors.early_vote.uf.ler import (
    juntar_arquivo,
    ler_arquivo,
    ler_csv,
    para_arquivo,
)
from pipeline.jobs import voto_antecipado_uf as job

EXEMPLO = Path(__file__).parent / "dados" / "uf_us_exemplo.csv"
ESTADOS_LIDOS = tuple(ESTADOS)


def _texto() -> str:
    return EXEMPLO.read_text(encoding="utf-8")


def _alterar(sigla: str, coluna: str, valor: str, texto: str | None = None) -> str:
    """O mesmo CSV (ou ``texto``) com uma célula alterada."""
    linhas = list(csv.reader(io.StringIO(texto or _texto())))
    indice = linhas[0].index(coluna)
    for linha in linhas[1:]:
        if linha[1] == sigla:
            linha[indice] = valor
    saida = io.StringIO()
    csv.writer(saida, lineterminator="\n").writerows(linhas)
    return saida.getvalue()


def _por_estado(texto: str | None = None) -> dict[str, object]:
    return {r.estado.value: r for r in ler_csv(texto or _texto(), ESTADOS_LIDOS)}


def test_le_os_estados_com_votos_e_salta_o_texas() -> None:
    lidos = _por_estado()
    assert set(lidos) == {"GA", "MI", "NV", "OH"}  # TX sem votos; AZ não é pedido
    ga = lidos["GA"]
    assert (ga.votos, ga.correio, ga.presencial) == (552_096, 23_268, 528_828)  # type: ignore[attr-defined]
    assert (ga.pedidos, ga.devolvidos, ga.dem) == (136_367, 23_268, None)  # type: ignore[attr-defined]
    assert ga.dados_ate == date(2026, 10, 16)  # type: ignore[attr-defined]
    nv = lidos["NV"]
    assert (nv.dem, nv.rep, nv.nao_afiliado) == (11_885, 10_530, 9_101)  # type: ignore[attr-defined]
    assert lidos["MI"].presencial == 0  # type: ignore[attr-defined]


def test_estados_com_fonte_propria_nao_se_publicam_via_uf() -> None:
    assert not (OFICIAIS & ESTADOS.keys())
    assert CodigoEstado.AZ in OFICIAIS
    # O AZ está no ficheiro mas, não sendo pedido, nunca é lido.
    assert "AZ" not in _por_estado()


def test_recusa_colunas_em_falta() -> None:
    with pytest.raises(ErroFormatoFonte, match="colunas"):
        ler_csv(_texto().replace("voted_all", "votos_todos"), ESTADOS_LIDOS)


def test_recusa_estado_em_falta_e_repetido() -> None:
    cabecalho, *linhas = _texto().splitlines(keepends=True)
    sem_ga = "".join([cabecalho, *(x for x in linhas if not x.startswith("Georgia,"))])
    with pytest.raises(ErroFormatoFonte, match="falta o estado GA"):
        ler_csv(sem_ga, ESTADOS_LIDOS)
    duplicado = _texto() + next(x for x in linhas if x.startswith("Ohio,"))
    with pytest.raises(ErroFormatoFonte, match="repetido"):
        ler_csv(duplicado, ESTADOS_LIDOS)


def test_recusa_numero_invalido_e_data_invalida() -> None:
    with pytest.raises(ErroFormatoFonte, match="inteiro"):
        ler_csv(_alterar("OH", "voted_all", "-5"), ESTADOS_LIDOS)
    with pytest.raises(ErroFormatoFonte, match="inteiro"):
        ler_csv(_alterar("OH", "request_all", "NA"), ESTADOS_LIDOS)
    with pytest.raises(ErroFormatoFonte, match="last_update"):
        ler_csv(_alterar("OH", "last_update", "2026-10-16"), ESTADOS_LIDOS)
    with pytest.raises(ErroFormatoFonte, match="não é de 2026"):
        ler_csv(_alterar("OH", "last_update", "10/16/2025"), ESTADOS_LIDOS)


def test_recusa_somas_que_nao_batem() -> None:
    with pytest.raises(ErroFormatoFonte, match="não somam"):
        ler_csv(_alterar("OH", "voted_all", "460000"), ESTADOS_LIDOS)
    with pytest.raises(ErroFormatoFonte, match="superam"):
        ler_csv(_alterar("OH", "request_all", "1000"), ESTADOS_LIDOS)
    with pytest.raises(ErroFormatoFonte, match="partidos somam"):
        ler_csv(_alterar("NV", "voted_dem", "11886"), ESTADOS_LIDOS)


def test_arquivo_acumula_e_nao_duplica_o_dia(tmp_path: Path) -> None:
    primeiro = para_arquivo(ler_csv(_texto(), ESTADOS_LIDOS))
    arquivo = juntar_arquivo(None, primeiro)
    assert arquivo.height == 4
    assert juntar_arquivo(arquivo, primeiro).height == 4  # o mesmo retrato não duplica
    seguinte = para_arquivo(
        ler_csv(_alterar("OH", "last_update", "10/17/2026"), ESTADOS_LIDOS)
    ).filter(pl.col("estado") == "OH")
    arquivo = juntar_arquivo(arquivo, seguinte)
    assert arquivo.filter(pl.col("estado") == "OH")["dados_ate"].to_list() == [
        date(2026, 10, 16),
        date(2026, 10, 17),
    ]
    caminho = tmp_path / "historico.csv"
    assert ler_arquivo(caminho) is None
    arquivo.write_csv(caminho)
    assert ler_arquivo(caminho).equals(arquivo)  # type: ignore[union-attr]


def _preparar(tmp_path: Path, texto: str) -> Path:
    pasta = tmp_path / "data" / "brutos" / "uf"
    pasta.mkdir(parents=True, exist_ok=True)
    (pasta / "US.csv").write_text(texto, encoding="utf-8")
    return tmp_path


def test_publica_um_json_por_estado_com_dados_e_marca_fonte_nao_oficial(tmp_path: Path) -> None:
    raiz = _preparar(tmp_path, _texto())
    pasta, arquivo = tmp_path / "publicado", tmp_path / "historico-uf-2026.csv"
    job.executar(raiz, pasta, arquivo, descarregar_=False)
    totais = job.executar(raiz, pasta, arquivo, descarregar_=False)  # repetir não duplica

    assert totais == {"GA": 552_096, "MI": 630_001, "NV": 31_516, "OH": 452_069}
    assert sorted(p.name for p in pasta.glob("*.json")) == [
        "ga.json",
        "mi.json",
        "nv.json",
        "oh.json",
    ]
    assert ler_arquivo(arquivo).height == 4  # type: ignore[union-attr]

    ga = VotoAntecipadoAgregado.model_validate_json((pasta / "ga.json").read_text("utf-8"))
    assert ga.estado is CodigoEstado.GA
    assert [f.oficial for f in ga.metadados.fontes] == [False]
    assert (ga.metadados.fontes[0].licenca or "").startswith("Reutilização com atribuição")
    assert "16/10/2026" in (ga.metadados.fontes[0].licenca or "")
    assert ga.dados_ate == date(2026, 10, 16)
    assert ga.dias_antes == 18
    assert ga.modalidades == ("correio", "presencial")
    assert ga.dimensoes == ("modalidade",)
    assert (ga.ciclos[0].votos, ga.ciclos[0].pedidos) == (552_096, 136_367)
    assert ga.pedidos[0].pendentes == 136_367 - 23_268
    assert ga.geografia == ()
    assert ga.comparacao == ()
    assert any("não oficial" in a for a in ga.avisos)
    assert any("idade" in a for a in ga.avisos)
    modalidades = {(p.modalidade, p.votos) for p in ga.serie}
    assert modalidades == {("total", 552_096), ("correio", 23_268), ("presencial", 528_828)}


def test_nevada_tem_partido_e_michigan_so_correio(tmp_path: Path) -> None:
    raiz = _preparar(tmp_path, _texto())
    pasta = tmp_path / "publicado"
    job.executar(raiz, pasta, tmp_path / "h.csv", descarregar_=False)
    nv = VotoAntecipadoAgregado.model_validate_json((pasta / "nv.json").read_text("utf-8"))
    assert nv.dimensoes == ("modalidade", "partido")
    por_partido = {p.partido: p.votos for p in nv.serie if p.modalidade == "total"}
    assert por_partido == {"total": 31_516, "dem": 11_885, "rep": 10_530, "nao_afiliado": 9_101}
    mi = VotoAntecipadoAgregado.model_validate_json((pasta / "mi.json").read_text("utf-8"))
    assert mi.modalidades == ("correio",)
    assert mi.dimensoes == ("modalidade",)
    assert {p.partido for p in mi.serie} == {"total"}
    assert {(p.modalidade) for p in mi.serie} == {"total", "correio"}


def test_serie_diaria_cresce_com_o_arquivo(tmp_path: Path) -> None:
    pasta, arquivo = tmp_path / "publicado", tmp_path / "h.csv"
    job.executar(_preparar(tmp_path, _texto()), pasta, arquivo, descarregar_=False)
    novo = _alterar("OH", "last_update", "10/17/2026")
    novo = _alterar("OH", "voted_all", "500000", novo)
    novo = _alterar("OH", "inperson_all", "360240", novo)  # 139760 + 360240
    job.executar(_preparar(tmp_path, novo), pasta, arquivo, descarregar_=False)
    oh = VotoAntecipadoAgregado.model_validate_json((pasta / "oh.json").read_text("utf-8"))
    assert oh.dados_ate == date(2026, 10, 17)
    assert oh.ciclos[0].votos == 500_000
    totais = sorted((p.dias_antes, p.votos) for p in oh.serie if p.modalidade == "total")
    assert totais == [(17, 500_000), (18, 452_069)]


def test_sem_votos_em_nenhum_estado_nao_publica_nada(tmp_path: Path) -> None:
    texto = _texto()
    for sigla in ("GA", "MI", "NV", "OH"):
        texto = _alterar_texto(texto, sigla)
    raiz = _preparar(tmp_path, texto)
    pasta = tmp_path / "publicado"
    assert job.executar(raiz, pasta, tmp_path / "h.csv", descarregar_=False) == {}
    assert not pasta.exists()


def _alterar_texto(texto: str, sigla: str) -> str:
    """Zera todas as contagens de um estado (como o Texas no ficheiro real)."""
    linhas = list(csv.reader(io.StringIO(texto)))
    for linha in linhas[1:]:
        if linha[1] == sigla:
            linha[6:] = ["0"] * (len(linha) - 6)
    saida = io.StringIO()
    csv.writer(saida, lineterminator="\n").writerows(linhas)
    return saida.getvalue()


def test_recusa_publicar_estado_com_fonte_propria(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setitem(
        ESTADOS, CodigoEstado.AZ, estados_uf.EstadoUF(CodigoEstado.AZ, ("correio",))
    )
    with pytest.raises(RuntimeError, match="fonte própria"):
        job.executar(
            _preparar(tmp_path, _texto()), tmp_path / "p", tmp_path / "h.csv", descarregar_=False
        )


def test_formato_que_muda_nao_publica_nada(tmp_path: Path) -> None:
    raiz = _preparar(tmp_path, _texto().replace("voted_all", "votos_todos"))
    pasta = tmp_path / "publicado"
    with pytest.raises(ErroFormatoFonte):
        job.executar(raiz, pasta, tmp_path / "h.csv", descarregar_=False)
    assert not pasta.exists()
    assert not (tmp_path / "h.csv").exists()


def test_estado_que_falha_nao_impede_os_outros(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    raiz = _preparar(tmp_path, _alterar("GA", "voted_all", "600000"))
    pasta = tmp_path / "publicado"
    totais = job.executar(raiz, pasta, tmp_path / "h.csv", descarregar_=False)
    assert sorted(totais) == ["MI", "NV", "OH"]
    assert not (pasta / "ga.json").exists()
    assert "::warning::UF Election Lab, GA" in capsys.readouterr().err


def test_modalidades_com_pequena_diferenca_publicam_com_aviso(tmp_path: Path) -> None:
    # Como a Geórgia a 18/10/2026: correio e presencial somam 293 votos a mais do que o total.
    raiz = _preparar(tmp_path, _alterar("GA", "voted_all", "551803"))
    pasta = tmp_path / "publicado"
    job.executar(raiz, pasta, tmp_path / "h.csv", descarregar_=False)
    ga = VotoAntecipadoAgregado.model_validate_json((pasta / "ga.json").read_text("utf-8"))
    assert ga.ciclos[0].votos == 551_803
    assert any("somam 552\u00a0096" in a for a in ga.avisos)
    oh = VotoAntecipadoAgregado.model_validate_json((pasta / "oh.json").read_text("utf-8"))
    assert not any("somam" in a for a in oh.avisos)
