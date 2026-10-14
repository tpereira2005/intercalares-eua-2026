"""Colorado: folhas diárias do Secretary of State.

As folhas de teste são construídas aqui, com números inventados e a estrutura das folhas
reais de 2024 (só contagens agregadas por condado, partido, género e faixa).
"""

import zipfile
from datetime import UTC, date, datetime
from pathlib import Path
from xml.sax.saxutils import escape

import polars as pl
import pytest

from contratos.base import Fonte
from contratos.estados import CodigoEstado
from pipeline.comum.condados import nomes
from pipeline.comum.erros import ErroFormatoFonte
from pipeline.connectors.early_vote.co import fontes
from pipeline.connectors.early_vote.co.ler import ler_folha
from pipeline.jobs import voto_antecipado_co as job
from pipeline.transform.early_vote import agregado

PARTIDOS = ["ACN", "DEM", "REP", "UAF"]
FAIXAS = ["<18", "18-24", "25-34", "35-44", "45-54", "55-64", "65-74", "75 AND OVER"]
GENEROS = ["Female", "Male", "Not Disclosed"]

Linha = list[str | int]


def _linha(rotulo: str, valores: list[int]) -> Linha:
    return [rotulo, *valores, sum(valores)]


def _por_idade(titulo: str, fator: int) -> list[Linha]:
    linhas: list[Linha] = [[titulo], ["Gender/Age Range", *PARTIDOS, "Grand Total"]]
    total = [0] * len(PARTIDOS)
    for g, genero in enumerate(GENEROS):
        blocos = [
            [fator * (g + 1) * (i + 1) * (p + 1) for p in range(len(PARTIDOS))]
            for i in range(len(FAIXAS))
        ]
        subtotal = [sum(col) for col in zip(*blocos, strict=True)]
        total = [a + b for a, b in zip(total, subtotal, strict=True)]
        linhas.append(_linha(genero, subtotal))
        linhas += [_linha(f, b) for f, b in zip(FAIXAS, blocos, strict=True)]
    return [*linhas, _linha("Grand Total", total), ["end of worksheet"]]


def _por_condado(titulo: str, total: list[int]) -> list[Linha]:
    """Distribui ``total`` (por partido) pelos 64 condados: o último fica com o resto."""
    condados = sorted(nomes("CO").values())
    linhas: list[Linha] = [[titulo], ["COUNTY", *PARTIDOS, "Grand Total"]]
    resto = list(total)
    for nome in condados[:-1]:
        parte = [v // 100 for v in total]
        resto = [r - p for r, p in zip(resto, parte, strict=True)]
        linhas.append(_linha(nome, parte))
    linhas.append(_linha(condados[-1], resto))
    return [*linhas, _linha("Grand Total", total), ["end of worksheet"]]


def _totais(folha: list[Linha]) -> list[int]:
    ultima = next(ln for ln in folha if ln[0] == "Grand Total")
    return [int(v) for v in ln_valores(ultima)]


def ln_valores(ln: Linha) -> list[str | int]:
    return ln[1 : 1 + len(PARTIDOS)]


def _livro(**alteracoes: list[Linha]) -> dict[str, list[Linha]]:
    livro: dict[str, list[Linha]]
    correio = _por_idade("RETURNED MAIL BALLOTS", 100)
    presencial = _por_idade("IN PERSON BALLOTS", 1)
    todos = [a + b for a, b in zip(_totais(correio), _totais(presencial), strict=True)]
    livro = {
        "Voter_Counts": [["Voter Status", *PARTIDOS, "Grand Total"]],
        "All_Returned_Ballots_By_County": _por_condado("ALL RETURNED BALLOTS", todos),
        "Returned_Mail_Ballots_GenderAge": correio,
        "In_Person_Ballots_By_County": _por_condado("IN PERSON BALLOTS", _totais(presencial)),
        "In_Person_Ballots_GenderAge": presencial,
    }
    return {**livro, **alteracoes}


def _coluna(i: int) -> str:
    letras = ""
    i += 1
    while i:
        i, r = divmod(i - 1, 26)
        letras = chr(65 + r) + letras
    return letras


def _xml_folha(linhas: list[Linha]) -> str:
    corpo = []
    for n, ln in enumerate(linhas, start=1):
        celulas = []
        for i, v in enumerate(ln):
            ref = f"{_coluna(i)}{n}"
            if isinstance(v, int):
                celulas.append(f'<c r="{ref}"><v>{v}</v></c>')
            else:
                celulas.append(f'<c r="{ref}" t="inlineStr"><is><t>{escape(v)}</t></is></c>')
        corpo.append(f'<row r="{n}">{"".join(celulas)}</row>')
    return (
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        f"<sheetData>{''.join(corpo)}</sheetData></worksheet>"
    )


def _escrever(caminho: Path, livro: dict[str, list[Linha]]) -> Path:
    ns = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
    rel = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
    folhas = "".join(
        f'<sheet name="{nome}" sheetId="{i}" r:id="rId{i}"/>'
        for i, nome in enumerate(livro, start=1)
    )
    relacoes = "".join(
        f'<Relationship Id="rId{i}" Type="{rel}/worksheet" Target="worksheets/sheet{i}.xml"/>'
        for i in range(1, len(livro) + 1)
    )
    with zipfile.ZipFile(caminho, "w") as z:
        z.writestr(
            "xl/workbook.xml",
            f'<workbook xmlns="{ns}" xmlns:r="{rel}"><sheets>{folhas}</sheets></workbook>',
        )
        z.writestr(
            "xl/_rels/workbook.xml.rels",
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            f"{relacoes}</Relationships>",
        )
        for i, linhas in enumerate(livro.values(), start=1):
            z.writestr(f"xl/worksheets/sheet{i}.xml", _xml_folha(linhas))
    return caminho


def test_folha_valida_soma_generos_e_tira_o_correio_por_condado(tmp_path: Path) -> None:
    r = ler_folha(_escrever(tmp_path / "f.xlsx", _livro()), date(2026, 10, 20))
    assert set(r.idade["faixa"].unique()) == {
        "18-24", "25-34", "35-44", "45-54", "55-64", "65-74", "75+"
    }  # fmt: skip
    assert set(r.idade["partido"].unique()) == {"dem", "rep", "nao_afiliado", "outro"}
    # "<18" junta-se aos 18-24: (1 + 2) * (1 + 2 + 3) géneros, partido DEM (p = 1), correio.
    jovens = r.idade.filter(
        (pl.col("faixa") == "18-24") & (pl.col("partido") == "dem") & (pl.col("tipo") == "correio")
    )
    assert jovens["n"].to_list() == [100 * (1 + 2) * (1 + 2 + 3) * 2]
    assert r.idade["n"].sum() == r.condados["n"].sum()
    por_tipo = r.condados.group_by("tipo").agg(pl.col("n").sum())
    idade_tipo = r.idade.group_by("tipo").agg(pl.col("n").sum())
    assert por_tipo.sort("tipo").equals(idade_tipo.sort("tipo"))
    assert r.condados["fips_condado"].n_unique() == 64


@pytest.mark.parametrize(
    "estragar",
    [
        "partidos_nao_somam",
        "faixas_nao_somam",
        "condado_desconhecido",
        "condados_nao_batem_com_idade",
    ],
)
def test_folha_inconsistente_e_recusada(tmp_path: Path, estragar: str) -> None:
    livro = _livro()
    if estragar == "partidos_nao_somam":
        livro["Returned_Mail_Ballots_GenderAge"][4][-1] = 1
    elif estragar == "faixas_nao_somam":
        ln = livro["In_Person_Ballots_GenderAge"][4]
        ln[2] = int(ln[2]) + 1
        ln[-1] = int(ln[-1]) + 1
    elif estragar == "condado_desconhecido":
        livro["In_Person_Ballots_By_County"][2][0] = "Atlantis"
    else:
        todos = livro["All_Returned_Ballots_By_County"]
        todos[2][2] = int(todos[2][2]) + 5
        todos[2][-1] = int(todos[2][-1]) + 5
        todos[-2][2] = int(todos[-2][2]) + 5
        todos[-2][-1] = int(todos[-2][-1]) + 5
    with pytest.raises(ErroFormatoFonte):
        ler_folha(_escrever(tmp_path / "f.xlsx", livro), date(2026, 10, 20))


def test_um_ficheiro_que_nao_e_xlsx_e_recusado(tmp_path: Path) -> None:
    (tmp_path / "f.xlsx").write_text("<html>404</html>")
    with pytest.raises(ErroFormatoFonte):
        ler_folha(tmp_path / "f.xlsx", date(2026, 10, 20))


def test_comunicados_da_eleicao_geral_e_folha_de_cada_um() -> None:
    indice = (
        '<a href="2026/PR20260629BallotReturns.html">primária</a>'
        '<a href="2026/PR20261020BallotReturns.html">geral</a>'
        '<a href="2026/PR20261103BallotReturns9AM.html">dia da eleição</a>'
        '<a href="2026/PR20261012DropBoxes.html">outro</a>'
    )
    urls = fontes.comunicados(indice, date(2026, 11, 3))
    assert urls == [
        fontes.BASE + "2026/PR20261020BallotReturns.html",
        fontes.BASE + "2026/PR20261103BallotReturns9AM.html",
    ]
    pagina = (
        '<a href="20261019GeneralElectionActivity.xlsx">XLSX</a>'
        '<a href="2026GeneralElectionReturnReporting15daysout.pdf">PDF</a>'
    )
    folha = fontes.folha_do_comunicado(pagina, urls[0])
    assert folha == fontes.BASE + "2026/20261019GeneralElectionActivity.xlsx"
    assert fontes.data_da_folha(folha) == date(2026, 10, 19)
    assert (
        fontes.folha_do_comunicado('<a href="20260628PrimaryElectionActivity.xlsx">', urls[0])
        is None
    )
    assert fontes.data_da_folha(
        fontes.BASE + "2024/20241105GeneralElectionActivity9AM.xlsx"
    ) == date(2024, 11, 5)


def _retratos(tmp_path: Path, dias: list[date]) -> tuple[pl.DataFrame, pl.DataFrame]:
    relatorios = []
    for i, dia in enumerate(dias, start=1):
        livro = _livro(
            Returned_Mail_Ballots_GenderAge=_por_idade("RETURNED MAIL BALLOTS", 100 * i),
        )
        correio = livro["Returned_Mail_Ballots_GenderAge"]
        presencial = livro["In_Person_Ballots_GenderAge"]
        todos = [a + b for a, b in zip(_totais(correio), _totais(presencial), strict=True)]
        livro["All_Returned_Ballots_By_County"] = _por_condado("ALL RETURNED BALLOTS", todos)
        relatorios.append(ler_folha(_escrever(tmp_path / f"{i}.xlsx", livro), dia))
    return job._juntar(relatorios)


def test_publicado_compara_ao_mesmo_dia_e_tem_mapa_por_condado(tmp_path: Path) -> None:
    atual = _retratos(tmp_path, [date(2026, 10, 19), date(2026, 10, 20)])
    base = _retratos(tmp_path, [date(2022, 10, 24), date(2022, 10, 25), date(2022, 10, 26)])
    fonte = Fonte(nome="Teste", url="https://exemplo.org/f.xlsx", obtida_em=datetime.now(UTC))
    publicado = job.montar(atual, {2022: base}, [fonte], [])
    assert publicado.estado == CodigoEstado.CO
    assert publicado.dias_antes == 14
    ciclo_2022 = next(c for c in publicado.ciclos if c.ano == 2022)
    # 2026 a 14 dias = segundo relatório; 2022 a 14 dias (25 de outubro) = segundo também.
    assert ciclo_2022.votos_mesmo_dia == publicado.ciclos[0].votos
    assert publicado.ciclos[0].pedidos is None
    assert {c.categoria for c in publicado.comparacao if c.dimensao == "faixa"} >= {"25-34", "75+"}
    condados = [g for g in publicado.geografia if g.nivel == "condado" and g.partido == "total"]
    assert {g.ano for g in condados} == {2022, 2026}
    assert all(g.faixa == "total" for g in publicado.geografia)
    assert any("Sem comparação com 2024" in a for a in publicado.avisos)


def test_retratos_sem_pedidos_dao_cubo_de_pedidos_vazio(tmp_path: Path) -> None:
    idade, _ = _retratos(tmp_path, [date(2026, 10, 19)])
    cubos = agregado.cubos_de_retratos(idade, job.eleicao(2026))
    assert cubos.pedidos.is_empty()
    assert cubos.votos["n"].sum() == idade["n"].sum()
