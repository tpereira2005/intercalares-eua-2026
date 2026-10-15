"""Arizona: tabela da Stealth Analytics (fonte não oficial).

O ficheiro de exemplo é uma versão reduzida e escrita à mão da página real, com a mesma
estrutura de tabela, números inventados e sem dados pessoais. Nenhum teste faz pedidos à rede.
"""

import re
from datetime import date
from pathlib import Path

import polars as pl
import pytest

from contratos.estados import CodigoEstado
from contratos.voto_antecipado_agregado import VotoAntecipadoAgregado
from pipeline.comum.erros import ErroFormatoFonte
from pipeline.connectors.early_vote.az import codigos
from pipeline.connectors.early_vote.az.ler import juntar_arquivo, ler_arquivo, ler_pagina
from pipeline.jobs import voto_antecipado_az as job

EXEMPLO = Path(__file__).parent / "dados" / "az_early_ballots_exemplo.html"
VOTOS = (
    50000 + 120 + 1500 + 900 + 700 + 200 + 90 + 40 + 2000 + 1100 + 9000 + 6000 + 250 + 10000 + 1200
)
EMITIDOS_TOTAL = sum(
    (
        26000,
        72000,
        60000,
        24000,
        12000,
        2800,
        6400,
        1980000,
        94000,
        52000,
        485000,
        200000,
        21600,
        138000,
        81700,
    )
)


def _html() -> str:
    return EXEMPLO.read_text(encoding="utf-8")


def test_le_os_15_condados() -> None:
    retrato = ler_pagina(_html())
    assert retrato.height == 15
    assert set(retrato["fips_condado"]) == set(codigos.FIPS_CONDADO.values())
    maricopa = retrato.filter(pl.col("fips_condado") == "04013").row(0, named=True)
    assert maricopa == {
        "dados_ate": date(2026, 10, 15),
        "fips_condado": "04013",
        "devolvidos": 50000,
        "emitidos": 1_980_000,
    }
    lapaz = retrato.filter(pl.col("fips_condado") == "04012").row(0, named=True)
    assert lapaz["dados_ate"] == date(2026, 10, 12)
    assert lapaz["devolvidos"] == 40


def test_recusa_condado_desconhecido() -> None:
    with pytest.raises(ErroFormatoFonte, match="desconhecido"):
        ler_pagina(_html().replace('<th scope="row">Yuma</th>', '<th scope="row">Narnia</th>'))


def test_recusa_condado_em_falta() -> None:
    sem_yuma = re.sub(r'<tr>\s*<th scope="row">Yuma</th>.*?</tr>', "", _html(), flags=re.DOTALL)
    assert "Yuma" not in sem_yuma
    with pytest.raises(ErroFormatoFonte, match="faltam"):
        ler_pagina(sem_yuma)


def test_recusa_cabecalho_alterado() -> None:
    with pytest.raises(ErroFormatoFonte, match="cabeçalhos"):
        ler_pagina(_html().replace(">Issued<", ">Mailed<"))


def test_recusa_devolvidos_acima_de_emitidos() -> None:
    errado = _html().replace("<td>50,000</td>", "<td>2,000,001</td>")
    with pytest.raises(ErroFormatoFonte, match="superam"):
        ler_pagina(errado)


def test_recusa_numero_invalido_e_data_invalida() -> None:
    with pytest.raises(ErroFormatoFonte, match="inteiro"):
        ler_pagina(_html().replace("<td>50,000</td>", "<td>-5</td>"))
    with pytest.raises(ErroFormatoFonte, match="data"):
        ler_pagina(_html().replace("2026-10-15</td>", "15/10/2026</td>"))


def test_recusa_se_os_termos_desaparecem() -> None:
    with pytest.raises(ErroFormatoFonte, match="termos"):
        ler_pagina(
            _html().replace("Free to cite and reuse with attribution", "All rights reserved")
        )


def test_confere_a_linha_de_total_quando_existe() -> None:
    soma_devolvidos = f"{VOTOS:,}"
    soma_emitidos = f"{EMITIDOS_TOTAL:,}"
    total = (
        f'<tr><th scope="row">Arizona</th><td>{soma_devolvidos}</td><td>{soma_emitidos}</td>'
        "<td>9</td><td>2026-10-15</td></tr>\n"
    )
    ok = _html().replace("</tbody>", total + "</tbody>")
    assert ler_pagina(ok).height == 15
    with pytest.raises(ErroFormatoFonte, match="total"):
        ler_pagina(ok.replace(f"<td>{soma_devolvidos}</td>", f"<td>{VOTOS + 1:,}</td>"))


def test_arquivo_acumula_e_nao_duplica_o_dia(tmp_path: Path) -> None:
    primeiro = ler_pagina(_html())
    arquivo = juntar_arquivo(None, primeiro)
    assert arquivo.height == 15
    # O mesmo retrato outra vez não duplica nada.
    assert juntar_arquivo(arquivo, primeiro).height == 15
    # Um dia novo para Maricopa acrescenta uma linha; o dia repetido com valor novo substitui.
    novo = ler_pagina(
        _html().replace("<td>50,000</td>", "<td>60,000</td>").replace("2026-10-15", "2026-10-16")
    )
    arquivo = juntar_arquivo(arquivo, novo.filter(pl.col("fips_condado") == "04013"))
    assert arquivo.height == 16
    corrigido = novo.filter(pl.col("fips_condado") == "04013").with_columns(
        pl.lit(61_000, dtype=pl.Int64).alias("devolvidos")
    )
    arquivo = juntar_arquivo(arquivo, corrigido)
    maricopa = arquivo.filter(pl.col("fips_condado") == "04013")
    assert maricopa["devolvidos"].to_list() == [50000, 61_000]
    caminho = tmp_path / "historico.csv"
    assert ler_arquivo(caminho) is None
    arquivo.write_csv(caminho)
    assert ler_arquivo(caminho) is not None
    assert ler_arquivo(caminho).equals(arquivo)  # type: ignore[union-attr]


def test_json_valida_no_contrato_e_marca_fonte_nao_oficial(tmp_path: Path) -> None:
    pasta = tmp_path / "data" / "brutos" / "az"
    pasta.mkdir(parents=True)
    (pasta / "early-ballots.html").write_text(_html(), encoding="utf-8")
    saida = tmp_path / "az.json"
    arquivo = tmp_path / "historico-az-2026.csv"
    job.executar(tmp_path, saida, arquivo, descarregar_=False)
    job.executar(tmp_path, saida, arquivo, descarregar_=False)  # repetir não duplica

    publicado = VotoAntecipadoAgregado.model_validate_json(saida.read_text(encoding="utf-8"))
    assert publicado.estado is CodigoEstado.AZ
    assert [f.oficial for f in publicado.metadados.fontes] == [False]
    assert (publicado.metadados.fontes[0].licenca or "").startswith("Livre para citar")
    assert publicado.granularidade == "condado"
    assert publicado.modalidades == ("correio",)
    assert publicado.dados_ate == date(2026, 10, 15)
    assert publicado.dias_antes == 19
    assert publicado.ciclos[0].votos == VOTOS
    assert publicado.ciclos[0].pedidos == EMITIDOS_TOTAL
    assert publicado.pedidos[0].pendentes == EMITIDOS_TOTAL - VOTOS
    assert len(publicado.geografia) == 15
    assert {g.partido for g in publicado.geografia} == {"total"}
    assert {g.nome for g in publicado.geografia} >= {"La Paz", "Santa Cruz", "Maricopa"}
    assert publicado.comparacao == ()
    assert any("não oficial" in a for a in publicado.avisos)
    assert ler_arquivo(arquivo).height == 15  # type: ignore[union-attr]
    # Só o dia em que já há valor de todos os condados entra na série.
    assert {p.dias_antes for p in publicado.serie} == {19}
    assert {p.votos for p in publicado.serie} == {VOTOS}
    assert any("14 condados ainda não atualizaram" in a for a in publicado.avisos)
