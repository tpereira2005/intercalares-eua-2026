import zipfile
from datetime import date
from pathlib import Path

import pytest

from pipeline.comum.erros import ErroFormatoFonte
from pipeline.comum.leitura import data_geracao, ler_cabecalho, ler_tudo


def _escrever(caminho: Path, texto: str, codificacao: str = "utf-8") -> Path:
    caminho.write_bytes(texto.encode(codificacao))
    return caminho


def test_le_apenas_as_colunas_pedidas_com_aspas_e_quebras_de_linha(tmp_path: Path) -> None:
    ficheiro = _escrever(
        tmp_path / "f.csv",
        'id,nome,idade\n"1","ANA ""ZE"" SILVA","40"\n"2","LINHA\nPARTIDA","51"\n',
    )
    tabela, relatorio = ler_tudo(ficheiro, ["id", "idade"])
    assert tabela.columns == ["id", "idade"]
    assert tabela.rows() == [("1", "40"), ("2", "51")]
    assert relatorio.linhas == 2
    assert relatorio.linhas_invalidas == 0


def test_le_dentro_de_zip_e_utf16_com_tabulacoes(tmp_path: Path) -> None:
    conteudo = "﻿a\tb\n1\t2\n".encode("utf-16")
    arquivo = tmp_path / "f.zip"
    with zipfile.ZipFile(arquivo, "w") as z:
        z.writestr("f.txt", conteudo)
    tabela, _ = ler_tudo(arquivo, ["b"], delimitador="\t", codificacao="utf-16")
    assert tabela["b"].to_list() == ["2"]
    assert ler_cabecalho(arquivo, delimitador="\t", codificacao="utf-16") == ["a", "b"]


def test_falha_se_faltar_coluna(tmp_path: Path) -> None:
    ficheiro = _escrever(tmp_path / "f.csv", "a,b\n1,2\n")
    with pytest.raises(ErroFormatoFonte, match="Colunas em falta"):
        ler_tudo(ficheiro, ["a", "c"])


def test_falha_se_houver_demasiadas_linhas_partidas(tmp_path: Path) -> None:
    linhas = "\n".join(["1,2"] * 50 + ["1,2,3"] * 5)
    ficheiro = _escrever(tmp_path / "f.csv", "a,b\n" + linhas + "\n")
    with pytest.raises(ErroFormatoFonte, match="número errado"):
        ler_tudo(ficheiro, ["a"])


def test_tolera_poucas_linhas_partidas(tmp_path: Path) -> None:
    linhas = "\n".join(["1,2"] * 5000 + ["1,2,3"])
    ficheiro = _escrever(tmp_path / "f.csv", "a,b\n" + linhas + "\n")
    tabela, relatorio = ler_tudo(ficheiro, ["a"])
    assert tabela.height == 5000
    assert relatorio.linhas_invalidas == 1
    assert relatorio.exemplos_invalidos == [5002]


def test_data_de_geracao_vem_do_zip(tmp_path: Path) -> None:
    arquivo = tmp_path / "f.zip"
    with zipfile.ZipFile(arquivo, "w") as z:
        z.writestr(zipfile.ZipInfo("f.csv", date_time=(2026, 10, 13, 5, 16, 0)), "a\n1\n")
    assert data_geracao(arquivo) == date(2026, 10, 13)
    assert data_geracao(tmp_path / "f.csv") is None
