"""Conector do estado de Washington.

O ficheiro de exemplo é um excerto do CSV oficial de 2024 (``20241105_congressional.csv``):
presidente e Senado (que se ignoram) e os distritos 1, 3, 4 e 9 da Câmara. O 4.º tem dois
Republicanos e o 9.º dois Democratas (primárias "top two"). O nome da corrida do 3.º distrito
vem em maiúsculas, como na fonte.
"""

from datetime import UTC, date, datetime
from pathlib import Path

import polars as pl
import pytest

from contratos.base import Fonte
from contratos.estados import CodigoEstado
from pipeline.comum.erros import ErroFormatoFonte
from pipeline.connectors.results.registo import CONECTORES, DISTRITOS
from pipeline.connectors.results.wa.conector import ConectorWA, rotulo_partido
from pipeline.transform.resultados import ensaio
from pipeline.transform.resultados.montar import Leitura, linhas_nacionais, montar

DADOS = Path(__file__).parent / "dados" / "wa"
DATA = date(2024, 11, 5)
CABECALHO = '"Race","Candidate","Party","Votes","PercentageOfTotalVotes","JurisdictionName"\n'


def _fonte() -> Fonte:
    return Fonte.model_validate(
        {"nome": "Teste", "url": "https://exemplo.org/r.csv", "obtida_em": datetime.now(UTC)}
    )


def _votos(leitura: Leitura, corrida: str) -> dict[str, int]:
    tabela = leitura.votos.filter(pl.col("corrida") == corrida)
    return dict(zip(tabela["nome"].to_list(), tabela["votos"].to_list(), strict=True))


def _escrever(pasta: Path, linhas: str) -> Path:
    (pasta / "congressional.csv").write_text(CABECALHO + linhas, encoding="utf-8")
    return pasta


def test_estado_registado() -> None:
    assert isinstance(CONECTORES[CodigoEstado.WA], ConectorWA)
    assert DISTRITOS[CodigoEstado.WA] == 10


def test_pedido_usa_a_data_da_eleicao_em_minusculas() -> None:
    pedidos = ConectorWA().pedidos(date(2026, 11, 3), lambda _url: "")
    assert [(p.url, p.ficheiro) for p in pedidos] == [
        (
            "https://results.vote.wa.gov/results/20261103/export/20261103_congressional.csv",
            "congressional.csv",
        )
    ]


def test_so_a_camara_e_o_total_de_cada_distrito() -> None:
    leitura = ConectorWA().ler(DADOS, DATA)
    # Sem presidente nem Senado; o nome em maiúsculas do 3.º distrito também é reconhecido.
    assert [c.id for c in leitura.corridas] == ["WA-01", "WA-03", "WA-04", "WA-09"]
    assert {(c.cargo, c.distrito) for c in leitura.corridas} == {
        ("camara", d) for d in (1, 3, 4, 9)
    }
    assert set(leitura.votos["nivel"]) == {"estado"}
    assert leitura.modalidades is None
    assert leitura.cobertura_condados == ()
    assert leitura.tipo_unidade is None
    assert leitura.unidades.height == 0


def test_votos_e_partidos() -> None:
    leitura = ConectorWA().ler(DADOS, DATA)
    assert _votos(leitura, "WA-03") == {
        "Marie Gluesenkamp Perez": 215_177,
        "Joe Kent": 199_054,
        "WRITE-IN": 1_673,
    }
    partidos = dict(zip(leitura.votos["nome"], leitura.votos["partido"], strict=True))
    assert partidos["Marie Gluesenkamp Perez"] == "dem"
    assert partidos["Joe Kent"] == "rep"
    assert partidos["WRITE-IN"] == "outro"
    rotulos = dict(zip(leitura.votos["nome"], leitura.votos["partido_fonte"], strict=True))
    assert rotulos["Joe Kent"] == "(Prefers Republican Party)"
    assert rotulos["WRITE-IN"] is None  # o campo vem em branco


@pytest.mark.parametrize(
    ("texto", "esperado"),
    [
        ("(Prefers Democratic Party)", "dem"),
        ("(Prefers Republican Party)", "rep"),
        ("(Prefers GOP Party)", "rep"),
        ("(Prefers MAGA Republican Party)", "rep"),
        ("(Prefers Democrat Party)", "dem"),
        ("(Prefers Libertarian Party)", "outro"),
        ("(Prefers Independent Party)", "outro"),
        ("(States No Party Preference)", "outro"),
        ("Democratic Party Nominees", "dem"),
        (" ", "outro"),
        ("", "outro"),
    ],
)
def test_mapeamento_de_partidos(texto: str, esperado: str) -> None:
    assert rotulo_partido(texto) == esperado


def test_top_two_do_mesmo_partido() -> None:
    leitura = ConectorWA().ler(DADOS, DATA)
    partidos_9 = leitura.votos.filter(pl.col("corrida") == "WA-09")
    assert dict(zip(partidos_9["nome"], partidos_9["partido"], strict=True)) == {
        "Adam Smith": "dem",
        "Melissa Chaudhry": "dem",
        "WRITE-IN": "outro",
    }
    partidos_4 = leitura.votos.filter(pl.col("corrida") == "WA-04")
    assert dict(zip(partidos_4["nome"], partidos_4["partido"], strict=True)) == {
        "Jerrod Sessler": "rep",
        "Dan Newhouse": "rep",
        "WRITE-IN": "outro",
    }
    resultado = montar(
        estado=CodigoEstado.WA, data_eleicao=DATA, leitura=leitura, fontes=[_fonte()]
    )
    nove = next(c for c in resultado.corridas if c.id == "WA-09")
    # Ordenados pelos votos, sem fundir os dois Democratas; o total soma tudo.
    assert [c.nome for c in nove.candidatos] == ["Adam Smith", "Melissa Chaudhry", "WRITE-IN"]
    assert nove.total == 182_780 + 90_601 + 5_917
    nacional = {x.id: x for x in linhas_nacionais(resultado, "wa.json")}
    assert nacional["WA-09"].votos_dem == 182_780 + 90_601
    assert nacional["WA-09"].votos_rep == 0
    assert nacional["WA-04"].votos_rep == 136_175 + 153_477
    assert nacional["WA-04"].votos_dem == 0


def test_resultado_montado_sem_apuramento() -> None:
    leitura = ConectorWA().ler(DADOS, DATA)
    resultado = montar(
        estado=CodigoEstado.WA, data_eleicao=DATA, leitura=leitura, fontes=[_fonte()]
    )
    assert resultado.cobertura == "estado"
    um = next(c for c in resultado.corridas if c.id == "WA-01")
    assert um.total == 227_213 + 132_538 + 907
    assert um.unidades_reportadas is None
    assert um.unidades_totais is None
    assert um.tipo_unidade is None
    assert [x.apuramento for x in linhas_nacionais(resultado, "wa.json")] == [None] * 4


def test_ensaio_sem_descidas() -> None:
    leitura = ConectorWA().ler(DADOS, DATA)
    retratos = [
        montar(estado=CodigoEstado.WA, data_eleicao=DATA, leitura=p, fontes=[_fonte()])
        for p in ensaio.progressao(leitura, 4, semente=3)
    ]
    assert ensaio.verificar_sequencia(retratos) == []


# --- Validação: dados que falham nunca são publicados ----------------------------------------


def test_colunas_inesperadas(tmp_path: Path) -> None:
    (tmp_path / "congressional.csv").write_text("A,B\n1,2\n", encoding="utf-8")
    with pytest.raises(ErroFormatoFonte, match="colunas inesperadas"):
        ConectorWA().ler(tmp_path, DATA)


def test_sem_corridas_da_camara(tmp_path: Path) -> None:
    pasta = _escrever(
        tmp_path, '"U.S. Senator","Maria Cantwell","(Prefers Democratic Party)",10,100,"x"\n'
    )
    with pytest.raises(ErroFormatoFonte, match="nenhuma corrida da Câmara"):
        ConectorWA().ler(pasta, DATA)


@pytest.mark.parametrize("votos", ["abc", "-5", "1.5", ""])
def test_votos_invalidos(tmp_path: Path, votos: str) -> None:
    pasta = _escrever(
        tmp_path,
        '"Congressional District 1 - U.S. Representative","A B","(Prefers Democratic Party)",'
        f'"{votos}",1,"Congressional"\n',
    )
    with pytest.raises(ErroFormatoFonte, match="votos inválidos"):
        ConectorWA().ler(pasta, DATA)


def test_candidato_repetido(tmp_path: Path) -> None:
    linha = (
        '"Congressional District 1 - U.S. Representative","A B","(Prefers Democratic Party)",'
        '10,50,"Congressional"\n'
    )
    with pytest.raises(ErroFormatoFonte, match="candidato repetido"):
        ConectorWA().ler(_escrever(tmp_path, linha * 2), DATA)


def test_candidato_sem_nome(tmp_path: Path) -> None:
    pasta = _escrever(
        tmp_path,
        '"Congressional District 1 - U.S. Representative"," ","(Prefers Democratic Party)",'
        '10,50,"Congressional"\n',
    )
    with pytest.raises(ErroFormatoFonte, match="candidato sem nome"):
        ConectorWA().ler(pasta, DATA)


def test_votos_com_separador_de_milhares(tmp_path: Path) -> None:
    pasta = _escrever(
        tmp_path,
        '"Congressional District 1 - U.S. Representative","A B","(Prefers Democratic Party)",'
        '"227,213",63,"Congressional"\n',
    )
    assert _votos(ConectorWA().ler(pasta, DATA), "WA-01") == {"A B": 227_213}
