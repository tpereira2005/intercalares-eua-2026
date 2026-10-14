"""Modelo etário (``modelo/idade.py``): projeção do eleitorado, margens dos grupos e o
teste de troca de partidos com os cubos reais da Carolina do Norte."""

import csv
from datetime import date
from pathlib import Path

import numpy as np
import polars as pl
import pytest

from pipeline.jobs import idade_nc
from pipeline.modelo import idade

TROCA = {"dem": "rep", "rep": "dem"}


def _cubo(linhas: list[tuple[str, str, str, int | None, int]]) -> pl.DataFrame:
    return pl.DataFrame(
        linhas,
        schema={"faixa": pl.String, "partido": pl.String, "modalidade": pl.String,
                "dias_antes": pl.Int16, "n": pl.UInt32},
        orient="row",
    )  # fmt: skip


def _trocar(tabela: pl.DataFrame) -> pl.DataFrame:
    return tabela.with_columns(pl.col("partido").replace(TROCA))


def test_projecao_com_curvas_conhecidas() -> None:
    """Se na referência metade de cada grupo chega até ao dia, a projeção duplica-o."""
    antecipado = _cubo([("18-24", "dem", "presencial", 10, 100), ("75+", "rep", "correio", 9, 300)])
    final = _cubo([("18-24", "dem", "x", None, 200), ("75+", "rep", "x", None, 600)])
    ref = idade.Referencia(2022, antecipado, final)
    atual = _cubo([("18-24", "dem", "presencial", 12, 50), ("75+", "rep", "correio", 8, 50)])
    q = idade.projetar_final(idade.antecipado_ate(atual, 7), [ref], 7)
    i, j = idade.GRUPOS.index(("18-24", "dem")), idade.GRUPOS.index(("75+", "rep"))
    assert q[i] == pytest.approx(0.5)
    assert q[j] == pytest.approx(0.5)
    assert q.sum() == pytest.approx(1.0)


def test_outro_junta_se_aos_nao_filiados_e_desconhecida_fica_de_fora() -> None:
    v = idade.contagens(
        _cubo([("30-39", "outro", "x", 1, 3), ("30-39", "nao_afiliado", "x", 1, 2),
               ("desconhecida", "dem", "x", 1, 9)])
    )  # fmt: skip
    assert v.sum() == 5
    assert v[idade.GRUPOS.index(("30-39", "nao_afiliado"))] == 5


def test_regressao_ecologica_recupera_margens_por_partido() -> None:
    rng = np.random.default_rng(0)
    verdade = np.array([[80.0, -90.0, -10.0]] * len(idade.FAIXAS)).ravel()
    composicao = rng.dirichlet(np.ones(len(idade.GRUPOS)), size=300)
    margens = composicao @ verdade
    estimadas = idade.margens_grupos(composicao, margens, np.full(300, 1000.0), 8.0)
    assert np.abs(estimadas.ravel() - verdade).max() < 3.0
    assert np.all(np.abs(estimadas) <= 100.0)


@pytest.fixture(scope="module")
def reais() -> tuple[dict[int, idade.Referencia], dict[int, dict[str, tuple[float, float]]]]:
    anos = idade_nc.referencias()
    presidenciais = {}
    for a in idade_nc.PRESIDENCIAIS:
        caminho = Path(f"data/reference/modelo/presidencial_condados_{a}.csv")
        with caminho.open(encoding="utf-8") as f:
            presidenciais[a] = idade.ler_presidenciais(csv.DictReader(f))
    return anos, presidenciais


def test_trocar_partidos_troca_o_sinal(
    reais: tuple[dict[int, idade.Referencia], dict[int, dict[str, tuple[float, float]]]],
) -> None:
    anos, presidenciais = reais
    finais = {a: anos[a].final for a in presidenciais}
    conjunto = idade.conjunto_margens(finais, presidenciais)
    atual = anos[2022].demografico
    normal = idade.diagnosticar(atual, anos, conjunto, ano=2026, dias_antes=7)

    trocados = {a: idade.Referencia(a, _trocar(r.demografico), _trocar(r.final))
                for a, r in anos.items()}  # fmt: skip
    conjunto_t = idade.conjunto_margens(
        {a: trocados[a].final for a in presidenciais},
        {a: {c: (v, -m) for c, (v, m) in r.items()} for a, r in presidenciais.items()},
    )
    espelho = idade.diagnosticar(_trocar(atual), trocados, conjunto_t, ano=2026, dias_antes=7)

    assert espelho.efeito == pytest.approx(-normal.efeito, abs=1e-6)
    assert espelho.efeito_p10 == pytest.approx(-normal.efeito_p90, abs=1e-6)
    assert espelho.erro_backtest == pytest.approx(normal.erro_backtest, abs=1e-6)
    i, j = idade.GRUPOS.index(("50-64", "dem")), idade.GRUPOS.index(("50-64", "rep"))
    assert espelho.margens[j] == pytest.approx(-normal.margens[i], abs=1e-6)


def test_sem_voto_antecipado_nao_escreve(tmp_path: Path) -> None:
    cubo = tmp_path / "cubo.parquet"
    _cubo([("18-24", "dem", "nao_votou", None, 10)]).write_parquet(cubo)
    assert idade_nc.dias_antes(pl.read_parquet(cubo)) is None
    assert not idade_nc.executar(cubo, tmp_path / "idade.json")
    assert not (tmp_path / "idade.json").exists()


def test_dia_dos_dados_ignora_datas_futuras_e_o_dia_corrente() -> None:
    cubo = _cubo([("18-24", "dem", "correio", 21, 10), ("18-24", "dem", "correio", 19, 1)])
    # Dados até 13/10/2026 (21 dias antes): o boletim a 19 dias é uma data futura.
    assert idade_nc.dias_antes(cubo, date(2026, 10, 13)) == 21
    assert idade_nc.dias_antes(cubo, date(2026, 10, 1)) is None


def test_cedo_demais_nao_escreve(tmp_path: Path) -> None:
    cubo = tmp_path / "cubo.parquet"
    _cubo([("18-24", "dem", "correio", 21, 300_000)]).write_parquet(cubo)
    assert not idade_nc.executar(cubo, tmp_path / "idade.json", dados_ate=date(2026, 10, 13))
    assert not (tmp_path / "idade.json").exists()
