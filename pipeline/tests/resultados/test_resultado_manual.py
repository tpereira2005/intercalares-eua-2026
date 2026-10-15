"""Entrada manual de resultados (estados que recusam pedidos automáticos)."""

from datetime import UTC, date, datetime
from pathlib import Path

import httpx
import pytest

from contratos.estados import CodigoEstado
from contratos.resultados import ResultadosEstado, ResultadosNacional, ResultadosParciais
from pipeline.connectors.results.condados.conector import ConectorCondados
from pipeline.connectors.results.condados.harris import FonteHarris
from pipeline.connectors.results.fl.conector import ConectorFL
from pipeline.connectors.results.manual import ConectorManual, FicheiroManual
from pipeline.jobs import resultado_manual
from pipeline.jobs.resultado_manual import ErroEntrada, apuramento, atualizar, candidatos
from pipeline.jobs.resultados import Recolha

DADOS = Path(__file__).parent / "dados"
AGORA = datetime(2026, 11, 4, 3, 0, tzinfo=UTC)
URL = "https://github.com/exemplo/repo/releases/download/resultados-2026/manual.json"
PA_S = "Candidata A (D): 1.234.567; Candidato B (R): 1,200,000; Outros: 30 000"


TX_S = "Colin Allred (D): 5.031.249; Ted Cruz (R): 5.990.741; Outros: 214 000"


def _ficheiro(*corridas: str) -> FicheiroManual:
    f = FicheiroManual()
    for c in corridas:
        f, _ = atualizar(
            f,
            c,
            texto_candidatos=TX_S if c.startswith("TX") else PA_S,
            texto_apuramento="87%",
            fonte="https://www.electionreturns.pa.gov/",
            apagar=False,
            agora=AGORA,
        )
    return f


def test_candidatos_e_apuramento() -> None:
    lista = candidatos(PA_S)
    assert [(c.nome, c.partido, c.votos) for c in lista] == [
        ("Candidata A", "dem", 1_234_567),
        ("Candidato B", "rep", 1_200_000),
        ("Outros", "outro", 30_000),
    ]
    assert apuramento("87%") == (870, 1000, False)
    assert apuramento("87,5 %") == (875, 1000, False)
    assert apuramento("1234/2000") == (1234, 2000, True)
    with pytest.raises(ErroEntrada):
        apuramento("quase tudo")
    with pytest.raises(ErroEntrada):
        candidatos("Candidata A 123")


def test_recusa_estados_com_fonte_automatica_e_valida_tudo() -> None:
    with pytest.raises(ErroEntrada, match="fonte automática"):
        _ficheiro("NC-S")
    with pytest.raises(ValueError, match="mais unidades"):
        atualizar(
            FicheiroManual(),
            "PA-S",
            texto_candidatos=PA_S,
            texto_apuramento="2001/2000",
            fonte="https://www.electionreturns.pa.gov/",
            apagar=False,
            agora=AGORA,
        )


def test_substituir_avisar_descida_e_apagar() -> None:
    f = _ficheiro("PA-S", "MI-G")
    f, avisos = atualizar(
        f,
        "pa-s",
        texto_candidatos="Candidata A (D): 100; Candidato B (R): 90",
        texto_apuramento="10%",
        fonte="https://www.electionreturns.pa.gov/",
        apagar=False,
        agora=AGORA,
    )
    assert [e.corrida for e in f.entradas] == ["MI-G", "PA-S"]
    assert len(avisos) == 1
    assert "desceu" in avisos[0]
    f, _ = atualizar(
        f,
        "MI-G",
        texto_candidatos=None,
        texto_apuramento=None,
        fonte=None,
        apagar=True,
        agora=AGORA,
    )
    assert [e.corrida for e in f.entradas] == ["PA-S"]


def test_cli_nao_escreve_quando_a_entrada_e_invalida(tmp_path: Path) -> None:
    ficheiro = tmp_path / "manual.json"
    base = ["--ficheiro", str(ficheiro), "--corrida", "PA-S", "--fonte", "https://x.gov/"]
    assert resultado_manual.main([*base, "--candidatos", PA_S, "--apuramento", "87%"]) == 0
    antes = ficheiro.read_text(encoding="utf-8")
    assert resultado_manual.main([*base, "--candidatos", PA_S, "--apuramento", "?"]) == 1
    assert ficheiro.read_text(encoding="utf-8") == antes


def test_recolha_publica_as_corridas_manuais_com_o_selo(tmp_path: Path) -> None:
    conteudo = _ficheiro("PA-S", "PA-07", "MI-G").model_dump_json().encode()
    fl = (DADOS / "fl" / "resultados.txt").read_bytes()

    def fontes(pedido: httpx.Request) -> httpx.Response:
        if pedido.url.host == "github.com":
            return httpx.Response(200, content=conteudo, headers={"ETag": '"m1"'})
        return httpx.Response(200, content=fl)

    recolha = Recolha(
        date(2024, 11, 5),
        tmp_path / "pub",
        tmp_path / "brutos",
        manual=URL,
        cliente=httpx.Client(transport=httpx.MockTransport(fontes)),
    )
    alterados = {p.name for p in recolha.ciclo([ConectorFL()])}
    assert {"fl.json", "pa.json", "mi.json", "nacional.json", "parciais.json"} <= alterados
    pa = ResultadosEstado.model_validate_json((tmp_path / "pub" / "pa.json").read_bytes())
    assert {c.id for c in pa.corridas} == {"PA-S", "PA-07"}
    assert all(c.manual for c in pa.corridas)
    senado = next(c for c in pa.corridas if c.id == "PA-S")
    assert senado.total == 2_464_567
    assert senado.unidades_reportadas == 870
    assert senado.tipo_unidade is None
    assert "electionreturns.pa.gov" in senado.notas[0]
    nacional = ResultadosNacional.model_validate_json(
        (tmp_path / "pub" / "nacional.json").read_bytes()
    )
    linhas = {c.id: c for c in nacional.corridas}
    assert linhas["PA-S"].manual
    assert linhas["PA-S"].apuramento == 0.87
    assert not any(c.manual for c in nacional.corridas if c.estado == CodigoEstado.FL)


def test_sem_manual_json_a_recolha_segue(tmp_path: Path) -> None:
    fl = (DADOS / "fl" / "resultados.txt").read_bytes()

    def fontes(pedido: httpx.Request) -> httpx.Response:
        if pedido.url.host == "github.com":
            return httpx.Response(404)
        return httpx.Response(200, content=fl)

    recolha = Recolha(
        date(2024, 11, 5),
        tmp_path / "pub",
        tmp_path / "brutos",
        manual=URL,
        cliente=httpx.Client(transport=httpx.MockTransport(fontes)),
    )
    assert "fl.json" in {p.name for p in recolha.ciclo([ConectorFL()])}
    assert set(recolha.estados) == {CodigoEstado.FL}


def test_conector_manual_le_so_o_seu_estado(tmp_path: Path) -> None:
    (tmp_path / "manual.json").write_text(_ficheiro("PA-S", "MI-G").model_dump_json())
    leitura = ConectorManual(CodigoEstado.MI, URL).ler(tmp_path, date(2026, 11, 3))
    assert [c.id for c in leitura.corridas] == ["MI-G"]
    assert leitura.manual


def test_no_texas_a_entrada_manual_substitui_os_condados_da_corrida(tmp_path: Path) -> None:
    """Harris continua a dar o distrito 7; o Senado passa a ter o total do estado."""
    conteudo = _ficheiro("TX-S").model_dump_json().encode()
    harris = (DADOS / "harris" / "resultsbyballot.json").read_bytes()

    def fontes(pedido: httpx.Request) -> httpx.Response:
        if pedido.url.host == "github.com":
            return httpx.Response(200, content=conteudo)
        return httpx.Response(200, content=harris)

    recolha = Recolha(
        date(2024, 11, 5),
        tmp_path / "pub",
        tmp_path / "brutos",
        manual=URL,
        cliente=httpx.Client(transport=httpx.MockTransport(fontes)),
    )
    texas = ConectorCondados(CodigoEstado.TX, (FonteHarris(),))
    alterados = {p.name for p in recolha.ciclo([texas])}
    assert {"tx.json", "tx-manual.json", "nacional.json", "parciais.json"} <= alterados
    assert set(recolha.sobrepostos) == {CodigoEstado.TX}
    assert "TX-manual" in recolha.saude()["estados"]  # type: ignore[operator]

    nacional = ResultadosNacional.model_validate_json(
        (tmp_path / "pub" / "nacional.json").read_bytes()
    )
    linhas = {c.id: c for c in nacional.corridas}
    assert len([c for c in nacional.corridas if c.id == "TX-S"]) == 1
    assert linhas["TX-S"].manual
    assert linhas["TX-S"].cobertura == "estado"
    assert linhas["TX-S"].ficheiro == "tx-manual.json"
    assert linhas["TX-07"].cobertura == "condados"

    parciais = ResultadosParciais.model_validate_json(
        (tmp_path / "pub" / "parciais.json").read_bytes()
    )
    assert parciais.corridas_manuais == ("TX-S",)
    assert [c.estado for c in parciais.cobertura_parcial] == [CodigoEstado.TX]
    por_corrida = {(u.corrida, u.unidade): u for u in parciais.unidades}
    assert set(por_corrida) == {("TX-S", "total"), ("TX-07", "48201")}
    assert por_corrida["TX-S", "total"].votos_r == 5_990_741


def test_parciais_recusam_condados_numa_corrida_manual() -> None:
    with pytest.raises(ValueError, match="só com a unidade total"):
        ResultadosParciais.model_validate(
            {
                "metadados": {
                    "gerado_em": AGORA.isoformat(),
                    "fontes": [{"nome": "T", "url": URL, "obtida_em": AGORA.isoformat()}],
                },
                "ano": 2026,
                "instante": AGORA.isoformat(),
                "unidades": [
                    {
                        "corrida": "TX-S",
                        "unidade": "48201",
                        "votos_d": 1,
                        "votos_r": 1,
                        "votos_outros": 0,
                    }
                ],
                "corridas_manuais": ["TX-S"],
            }
        )
