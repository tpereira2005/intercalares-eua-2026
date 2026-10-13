"""Cobertura parcial por condados (Texas, pelo condado de Harris) sobre um excerto real do
ficheiro oficial de 2024 (só totais por candidato)."""

import shutil
from datetime import UTC, date, datetime
from pathlib import Path

import pytest

from contratos.base import Fonte
from contratos.estados import CodigoEstado
from pipeline.comum.erros import ErroFormatoFonte
from pipeline.connectors.results.condados.conector import ConectorCondados
from pipeline.connectors.results.condados.harris import FonteHarris
from pipeline.transform.resultados.avaliacao import linhas
from pipeline.transform.resultados.montar import linhas_nacionais, montar
from pipeline.transform.resultados.parciais import montar_parciais

DADOS = Path(__file__).parent / "dados"
TEXAS = ConectorCondados(CodigoEstado.TX, (FonteHarris(),))


def _fonte() -> Fonte:
    return Fonte.model_validate(
        {"nome": "Teste", "url": "https://exemplo.org/r.json", "obtida_em": datetime.now(UTC)}
    )


@pytest.fixture
def pasta(tmp_path: Path) -> Path:
    destino = tmp_path / "48201"
    destino.mkdir()
    shutil.copy(DADOS / "harris" / "resultsbyballot.json", destino / "resultsbyballot.json")
    return tmp_path


def test_harris_le_senado_e_camara_por_tipo_de_voto(pasta: Path) -> None:
    leitura = TEXAS.ler(pasta, date(2024, 11, 5))
    assert {c.id for c in leitura.corridas} == {"TX-S", "TX-07"}  # sem cargos estaduais
    senado = leitura.votos.filter(leitura.votos["corrida"] == "TX-S")
    por_nome = dict(senado.select("nome", "votos").iter_rows())
    assert por_nome["COLIN ALLRED"] == 841_784
    assert por_nome["TED CRUZ"] == 666_027
    assert set(senado["codigo"].to_list()) == {"48201"}
    assert set(senado["nivel"].to_list()) == {"condado"}
    assert leitura.modalidades is not None
    allred = leitura.modalidades.filter(leitura.modalidades["candidato"] == "COLIN ALLRED")
    assert allred["votos"].sum() == 841_784
    assert leitura.cobertura_condados == ("48201",)


def test_pedidos_vao_para_a_subpasta_do_condado() -> None:
    pedidos = TEXAS.pedidos(date(2026, 11, 3), lambda _u: "")
    assert [(p.url, p.ficheiro) for p in pedidos] == [
        (
            "https://appfiles.harrisvotes.com/harrisvotes/prd/Data/1126/resultsbyballot.json",
            "48201/resultsbyballot.json",
        )
    ]


def test_recusa_ficheiro_de_outra_eleicao(pasta: Path) -> None:
    with pytest.raises(ErroFormatoFonte, match="eleição 1124"):
        TEXAS.ler(pasta, date(2026, 11, 3))


def test_cobertura_parcial_chega_ao_site_ao_modelo_e_fica_fora_da_avaliacao(
    pasta: Path,
) -> None:
    data = date(2024, 11, 5)
    leitura = TEXAS.ler(pasta, data)
    resultado = montar(estado=CodigoEstado.TX, data_eleicao=data, leitura=leitura,
                       fontes=[_fonte()])  # fmt: skip
    assert resultado.cobertura == "condados"
    assert resultado.condados_cobertos == ("48201",)
    assert "não o resultado do estado" in resultado.avisos[0]
    assert {x.cobertura for x in linhas_nacionais(resultado, "tx.json")} == {"condados"}
    assert linhas([resultado]) == []  # nunca entra na avaliação da previsão

    parciais = montar_parciais([leitura], ano=2024, instante=datetime.now(UTC), fontes=[_fonte()])
    assert [c.estado for c in parciais.cobertura_parcial] == [CodigoEstado.TX]
    assert {u.unidade for u in parciais.unidades} == {"48201"}  # sem "total" do estado
