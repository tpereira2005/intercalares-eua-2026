"""Iowa: leitura dos relatórios "Absentee Ballot Statistics" e montagem do ficheiro publicado.

O PDF de exemplo é o primeiro relatório da eleição de 2024 (4 páginas do ficheiro oficial
por distrito, só totais agregados). Os outros casos usam texto de páginas escrito à mão
no mesmo formato.
"""

from datetime import UTC, date, datetime
from pathlib import Path

import polars as pl
import pytest

from contratos.base import Fonte
from contratos.voto_antecipado_agregado import VotoAntecipadoAgregado
from pipeline.comum.erros import ErroFormatoFonte
from pipeline.connectors.early_vote.ia.ler import ler_paginas, ler_relatorios
from pipeline.jobs import voto_antecipado_ia as job
from pipeline.transform.early_vote import agregado

DADOS = Path(__file__).parent / "dados"
RAIZ = Path(__file__).parents[3]

CABECALHO = """Absentee Ballot Statistics
November 3, 2026 General Election
County/ Party / Receipt Method Requested Issued Received
"""
RODAPE = "Prepared by the Office of Iowa Secretary of State\nData Pulled: 7:00 AM (UTC)\n{data}"


def _pagina(corpo: str, data: str) -> str:
    return CABECALHO + corpo + "\n" + RODAPE.format(data=data)


def _n(tabela: pl.DataFrame, unidade: str, partido: str, tipo: str) -> int:
    filtro = (
        (pl.col("unidade") == unidade) & (pl.col("partido") == partido) & (pl.col("tipo") == tipo)
    )
    return int(tabela.filter(filtro)["n"].sum())


def test_le_o_pdf_oficial_por_distrito() -> None:
    tabela = ler_relatorios(DADOS / "ia_distritos_2024.pdf", "distrito")
    assert tabela["dados_ate"].unique().to_list() == [date(2024, 10, 16)]
    assert sorted(tabela["unidade"].unique().to_list()) == ["1", "2", "3", "4"]
    assert _n(tabela, "1", "dem", "presencial") == 4150
    assert _n(tabela, "1", "dem", "correio") == 370
    assert _n(tabela, "1", "dem", "pedidos") == 28316
    por_tipo = dict(tabela.group_by("tipo").agg(pl.col("n").sum()).iter_rows())
    assert por_tipo["correio"] + por_tipo["presencial"] == 28102


def test_recusa_ficheiros_que_nao_sao_pdf(tmp_path: Path) -> None:
    falso = tmp_path / "AbsenteeCongressional2026.pdf"
    falso.write_text("<html>404</html>", encoding="utf-8")
    with pytest.raises(ErroFormatoFonte, match="não é um PDF"):
        ler_relatorios(falso, "distrito")


def test_continuacao_de_pagina_colunas_em_branco_e_dia_repetido() -> None:
    primeira = """United States Representative District 1 30 28 12
Democrat 20 19 9
Counter / In-Office 5 5 5
Ballot not yet returned by voter 11 10 1
Mail 3 3 3
Mailing 2 2"""
    # A unidade continua na página seguinte, com o mesmo partido e um novo.
    segunda = """Republican 10 9 3
Satellite 2 2 2
37480 1 1 1
Other 1"""
    # O mesmo dia publicado outra vez: o último relatório substitui o primeiro.
    repetido = """United States Representative District 1 31 29 13
Democrat 21 20 10
Counter / In-Office 6 6 6
Mail 4 4 4
Republican 10 9 3
Satellite 3 3 3"""
    tabela = ler_paginas(
        [
            _pagina(primeira, "10/20/2026"),
            _pagina(segunda, "10/20/2026"),
            _pagina(repetido, "10/21/2026"),
            _pagina(repetido, "10/21/2026"),
        ],
        "distrito",
        "exemplo",
    )
    dia1 = tabela.filter(pl.col("dados_ate") == date(2026, 10, 19))
    assert _n(dia1, "1", "dem", "presencial") == 5
    assert _n(dia1, "1", "dem", "correio") == 4  # 3 por correio e 1 na linha dos pendentes
    assert _n(dia1, "1", "dem", "pendentes") == 10
    assert _n(dia1, "1", "rep", "correio") == 1  # forma com código numérico
    assert _n(dia1, "1", "outro", "pedidos") == 1
    dia2 = tabela.filter(pl.col("dados_ate") == date(2026, 10, 20))
    assert _n(dia2, "1", "dem", "presencial") == 6
    assert _n(dia2, "1", "rep", "presencial") == 3


def test_recusa_formas_que_nao_somam_os_recebidos() -> None:
    errado = """United States Representative District 1 10 10 5
Democrat 10 10 5
Counter / In-Office 4 4 4"""
    with pytest.raises(ErroFormatoFonte, match="formas de receção somam 4, não 5"):
        ler_paginas([_pagina(errado, "10/20/2026")], "distrito", "exemplo")


def test_recusa_rotulos_desconhecidos() -> None:
    errado = """United States Representative District 1 10 10 5
Democrat 10 10 5
Carrier Pigeon 5 5 5"""
    with pytest.raises(ErroFormatoFonte, match="desconhecida"):
        ler_paginas([_pagina(errado, "10/20/2026")], "distrito", "exemplo")


def test_condados_pelo_nome_do_census() -> None:
    corpo = """O'Brien 4 4 4
Republican 4 4 4
Counter / In-Office 4 4 4
Polk 9 9 9
Democrat 9 9 9
Satellite 9 9 9"""
    tabela = ler_paginas([_pagina(corpo, "10/20/2026")], "condado", "exemplo")
    assert set(tabela["unidade"].to_list()) == {"19141", "19153"}


def _retratos() -> pl.DataFrame:
    linhas = []
    for dia, dem, rep in [(date(2026, 10, 20), 10, 4), (date(2026, 10, 22), 25, 30)]:
        for partido, n in (("dem", dem), ("rep", rep)):
            linhas += [
                (dia, 1, partido, "presencial", n),
                (dia, 1, partido, "correio", n // 2),
                (dia, 1, partido, "pedidos", 2 * n),
            ]
    return pl.DataFrame(linhas, schema=list(job.ESQUEMA_REFERENCIA.items()), orient="row")


def test_cubos_reproduzem_os_acumulados_da_fonte() -> None:
    cubos = agregado.cubos_de_retratos(_retratos(), job.eleicao(2026))
    # 22 de outubro: 12 dias antes; 20 de outubro: 14; 21 de outubro (sem relatório): 13.
    assert agregado.total_votos(cubos.votos, 12) == 25 + 12 + 30 + 15
    assert agregado.total_votos(cubos.votos, 13) == 10 + 5 + 4 + 2
    assert agregado.total_votos(cubos.votos, 14) == 10 + 5 + 4 + 2
    assert agregado.total_pedidos(cubos.pedidos, 12) == 2 * (25 + 30)
    pedidos = agregado.pedidos(cubos.pedidos, 12)
    total = pedidos.filter((pl.col("faixa") == "total") & (pl.col("partido") == "total"))
    assert total["devolvidos"].item() == 25 + 12 + 30 + 15


def test_troca_de_rotulos_partidarios_troca_o_resultado_do_iowa() -> None:
    fonte = Fonte(nome="t", url="https://exemplo.org/x.pdf", obtida_em=datetime.now(UTC))
    original = job.montar(_retratos(), {}, None, [fonte])
    trocado = job.montar(
        _retratos().with_columns(pl.col("partido").replace({"dem": "rep", "rep": "dem"})),
        {},
        None,
        [fonte],
    )

    def por_partido(p: VotoAntecipadoAgregado) -> dict[str, int]:
        return {
            x.partido: x.votos
            for x in p.serie
            if x.dias_antes == 12 and x.modalidade == "total" and x.faixa == "total"
        }

    a, b = por_partido(original), por_partido(trocado)
    assert a["dem"] == b["rep"]
    assert a["rep"] == b["dem"]
    assert a["total"] == b["total"]


def test_mesmo_ciclo_de_2022_da_ritmo_zero() -> None:
    """2022 deslocado para o calendário de 2026 tem de dar ritmo 0 face a 2022."""
    base = job.ler_referencia(RAIZ, 2022)
    assert base is not None
    deslocamento = date(2026, 11, 3) - date(2022, 11, 8)
    atual = base.with_columns(pl.col("dados_ate") + deslocamento).filter(
        pl.col("dados_ate") <= date(2026, 10, 22)
    )
    fonte = Fonte(nome="t", url="https://exemplo.org/x.pdf", obtida_em=datetime.now(UTC))
    publicado = job.montar(atual, {2022: base}, None, [fonte])
    assert publicado.granularidade == "condado"
    assert publicado.dias_antes == 12
    linhas = [c for c in publicado.comparacao if c.ano_base == 2022]
    assert linhas
    assert all(c.ritmo == 0 for c in linhas if c.votos_base)
    distritos = {g.codigo for g in publicado.geografia if g.nivel == "distrito"}
    assert distritos == {"1", "2", "3", "4"}
