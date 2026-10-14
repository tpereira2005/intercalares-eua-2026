"""Sinal etário do voto antecipado na Carolina do Norte (``DiagnosticoIdade``).

Uso, depois do job do voto antecipado da Carolina do Norte ter gravado os cubos de 2026::

    uv run python -m pipeline.jobs.idade_nc \\
        --cubo data/publicado/voto-antecipado/cubos/cubo_demografico_2026.parquet \\
        --nc data/publicado/voto-antecipado/nc.json \\
        --saida data/publicado/voto-antecipado/idade-nc.json

Lê os cubos de 2016 a 2024 (``data/reference/nc``) e as margens presidenciais por condado
de 2020 e 2024 (``data/reference/modelo``). O dia dos dados é o ``dados_ate`` do ``nc.json``
(``--nc``) ou a véspera de hoje. Antes de 14 dias da eleição, ou com menos de 200 000 votos
antecipados, não escreve nada (e diz porquê).
"""

import argparse
import csv
import logging
from collections.abc import Sequence
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import cast

import polars as pl

from contratos.base import Fonte, Metadados
from contratos.estados import CodigoEstado
from contratos.idade import BacktestIdade, DiagnosticoIdade, GrupoIdade, PartidoIdade
from contratos.voto_antecipado import Faixa, VotoAntecipadoEstado
from pipeline.comum.calendario import DATAS_ELEICOES_GERAIS
from pipeline.connectors.early_vote.nc.fontes import URL_ELEITORES, URL_HISTORICO
from pipeline.modelo import idade

registo = logging.getLogger(__name__)

ANO = 2026
ANOS = (2016, 2018, 2020, 2022, 2024)
PRESIDENCIAIS = (2020, 2024)
PASTA_NC = Path("data/reference/nc")
PASTA_MODELO = Path("data/reference/modelo")
URL_PRESIDENCIAIS = "https://github.com/tonmcg/US_County_Level_Election_Results_08-24"
VOTOS_MINIMOS = 200_000
DIAS_MAXIMOS = 14
"""O sinal só se publica a partir de duas semanas antes da eleição e com o voto antecipado
presencial já em curso. Antes disso só há correio, as curvas de chegada das referências
assentam em poucos votos e o sinal é ruído: com os cubos de 2018 e 2022 no lugar de 2026,
a 21 dias dava de -6 a +18 pontos com intervalos de 70 pontos."""

NOTAS = (
    "Diagnóstico mostrado, com peso zero na previsão.",
    "Compara o eleitorado com os registados do próprio ano, para não confundir a deriva do "
    "registo partidário com a participação.",
    "As margens dos grupos vêm de uma regressão ecológica nos condados e são aproximadas.",
    "Nos backtests, o sinal acerta no sentido mais vezes do que na magnitude.",
)


def dias_antes(cubo: pl.DataFrame, dados_ate: date | None = None) -> int | None:
    """Dias antes da eleição do último dia completo (``None`` sem voto até lá).

    ``dados_ate`` é o último dia completo do rastreador (``dados_ate`` do ``nc.json``). Sem
    ele, usa-se a véspera de hoje, como o job da Carolina do Norte: o dia corrente está
    incompleto e o ficheiro da NCSBE traz por vezes boletins com datas futuras, que ficam
    de fora. Nunca depois da eleição.
    """
    eleicao = DATAS_ELEICOES_GERAIS[ANO]
    limite = dados_ate or datetime.now(UTC).date() - timedelta(days=1)
    dias = max((eleicao - limite).days, 0)
    votos = cubo.filter(pl.col("modalidade") != "nao_votou", pl.col("dias_antes") >= dias)
    return None if votos.is_empty() else dias


def montar(
    diagnostico: idade.Diagnostico, *, ano: int, gerado_em: datetime, fontes: Sequence[Fonte]
) -> DiagnosticoIdade:
    d = diagnostico
    grupos = tuple(
        GrupoIdade(
            faixa=cast("Faixa", f),
            partido=cast("PartidoIdade", p),
            quota_antecipado=float(d.quotas_antecipado[i]),
            quota_projetada=float(d.quotas_projetadas[i]),
            quota_registados=float(d.quotas_registados[i]),
            quota_final_referencia=float(d.quotas_final_referencia[i]),
            margem=float(d.margens[i]),
            margem_minima=float(d.margens_minimas[i]),
            margem_maxima=float(d.margens_maximas[i]),
        )
        for i, (f, p) in enumerate(idade.GRUPOS)
    )
    return DiagnosticoIdade(
        metadados=Metadados(gerado_em=gerado_em, fontes=tuple(fontes)),
        ano=ano,
        estado=CodigoEstado.NC,
        data_dados=DATAS_ELEICOES_GERAIS[ano] - timedelta(days=d.dias_antes),
        dias_antes=d.dias_antes,
        votos_antecipados=d.votos_antecipados,
        ano_referencia=d.ano_referencia,
        grupos=grupos,
        inclinacao_projetada=d.inclinacao_projetada,
        inclinacao_referencia=d.inclinacao_referencia,
        efeito=d.efeito,
        efeito_p10=d.efeito_p10,
        efeito_p90=d.efeito_p90,
        erro_backtest=d.erro_backtest,
        backtests=tuple(
            BacktestIdade(
                ano=b.ano,
                referencias=b.referencias,
                dias_antes=b.dias_antes,
                inclinacao_real=b.real,
                inclinacao_projetada=b.projetada,
            )
            for b in d.backtests
        ),
        notas=NOTAS,
    )


def referencias(pasta: Path = PASTA_NC) -> dict[int, idade.Referencia]:
    return {
        a: idade.Referencia(
            a,
            pl.read_parquet(pasta / f"cubo_demografico_{a}.parquet"),
            pl.read_parquet(pasta / f"cubo_final_{a}.parquet"),
        )
        for a in ANOS
    }


def margens(anos: dict[int, idade.Referencia]) -> dict[tuple[int, float], idade.Vetor]:
    presidenciais = {}
    for a in PRESIDENCIAIS:
        with (PASTA_MODELO / f"presidencial_condados_{a}.csv").open(encoding="utf-8") as f:
            presidenciais[a] = idade.ler_presidenciais(csv.DictReader(f))
    return idade.conjunto_margens({a: anos[a].final for a in PRESIDENCIAIS}, presidenciais)


def executar(cubo: Path, saida: Path, *, dados_ate: date | None = None) -> bool:
    atual = pl.read_parquet(cubo)
    dias = dias_antes(atual, dados_ate)
    if dias is None:
        registo.warning("Ainda não há voto antecipado no cubo de %d", ANO)
        return False
    if dias > DIAS_MAXIMOS:
        registo.warning(
            "A %d dias da eleição o sinal etário ainda é ruído: só a partir de %d dias",
            dias, DIAS_MAXIMOS,
        )  # fmt: skip
        return False
    anos = referencias()
    diagnostico = idade.diagnosticar(atual, anos, margens(anos), ano=ANO, dias_antes=dias)
    if diagnostico.votos_antecipados < VOTOS_MINIMOS:
        registo.warning(
            "Só %d votos antecipados: sinal etário adiado", diagnostico.votos_antecipados
        )
        return False
    agora = datetime.now(UTC)
    fontes = (
        Fonte(nome="North Carolina State Board of Elections (eleitores)", url=URL_ELEITORES,
              licenca="Registo público (N.C.G.S. 132)", obtida_em=agora),
        Fonte(nome="North Carolina State Board of Elections (histórico de voto)",
              url=URL_HISTORICO, licenca="Registo público (N.C.G.S. 132)",
              obtida_em=agora),
        Fonte(nome="Resultados presidenciais por condado (tonmcg)", url=URL_PRESIDENCIAIS,
              licenca="MIT", obtida_em=agora),
    )  # fmt: skip
    resultado = montar(diagnostico, ano=ANO, gerado_em=agora, fontes=fontes)
    saida.parent.mkdir(parents=True, exist_ok=True)
    saida.write_text(resultado.model_dump_json(indent=1) + "\n", encoding="utf-8")
    registo.info(
        "Sinal etário a %d dias: %+.1f pontos (80%%: %+.1f a %+.1f), %d votos antecipados",
        dias, resultado.efeito, resultado.efeito_p10, resultado.efeito_p90,
        resultado.votos_antecipados,
    )  # fmt: skip
    return True


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cubo", type=Path, required=True, help="cubo demográfico de 2026")
    parser.add_argument("--saida", type=Path, required=True)
    parser.add_argument(
        "--nc", type=Path, default=None, help="nc.json do rastreador (dá o último dia completo)"
    )
    args = parser.parse_args()
    dados_ate = None
    if args.nc is not None:
        texto = args.nc.read_text(encoding="utf-8")
        dados_ate = VotoAntecipadoEstado.model_validate_json(texto).dados_ate
    executar(args.cubo, args.saida, dados_ate=dados_ate)


if __name__ == "__main__":
    main()
