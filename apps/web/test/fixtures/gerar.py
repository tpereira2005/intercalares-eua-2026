"""Gera os ficheiros sintéticos dos testes e do desenvolvimento do site.

``voto-antecipado-sintetico.json`` segue o contrato ``VotoAntecipadoEstado`` (Carolina do
Norte, com ficheiro de eleitores) e ``pa-agregado-sintetico.json`` o contrato
``VotoAntecipadoAgregado`` (Pensilvânia, só boletins).

Os eleitores são aleatórios (semente fixa), com a forma do painel do pipeline:
nenhum valor vem de dados reais e o ficheiro nunca é publicado no site.

Uso: ``uv run python apps/web/test/fixtures/gerar.py``
"""

import sys
from datetime import UTC, date, datetime
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(RAIZ / "pipeline" / "tests" / "voto_antecipado"))

from conftest import boletins_sinteticos, painel_sintetico  # noqa: E402

from contratos.base import Fonte  # noqa: E402
from contratos.estados import CodigoEstado  # noqa: E402
from pipeline.comum.calendario import ELEICOES_NC, eleicao_geral  # noqa: E402
from pipeline.transform.early_vote import agregado  # noqa: E402
from pipeline.transform.early_vote.cubos import cubo_demografico, cubo_geografico  # noqa: E402
from pipeline.transform.early_vote.relatorio import CubosAno, montar  # noqa: E402

DESTINO = Path(__file__).with_name("voto-antecipado-sintetico.json")
DESTINO_AGREGADO = Path(__file__).with_name("pa-agregado-sintetico.json")


def cubos(ano: int, semente: int, taxa_extra: float = 0.0) -> CubosAno:
    painel = painel_sintetico(semente, n=30000, taxa_extra=taxa_extra)
    return CubosAno(ELEICOES_NC[ano], cubo_demografico(painel), cubo_geografico(painel))


def main() -> None:
    relatorio = montar(
        estado=CodigoEstado.NC,
        atual=cubos(2026, 10, 0.02),
        bases=[cubos(2022, 11), cubos(2018, 12, -0.03), cubos(2024, 13, 0.05)],
        dados_ate=date(2026, 10, 24),
        fontes=[
            Fonte.model_validate(
                {
                    "nome": "Dados sintéticos de teste",
                    "url": "https://exemplo.org/sintetico",
                    "obtida_em": datetime(2026, 10, 25, tzinfo=UTC),
                }
            )
        ],
        nomes_condados={"37183": "Wake", "37119": "Mecklenburg", "37001": "Alamance"},
        avisos=["Dados sintéticos: só para testes."],
        gerado_em=datetime(2026, 10, 25, tzinfo=UTC),
    )
    # Só as linhas que o site lê, para o ficheiro ficar pequeno; continua a cumprir o contrato.
    reduzido = relatorio.model_copy(
        update={
            "serie": [
                p for p in relatorio.serie if p.partido == "total" and p.modalidade == "total"
            ],
            "cruzamentos": [
                c for c in relatorio.cruzamentos if c.dimensao in ("partido", "modalidade")
            ],
            "geografia": [g for g in relatorio.geografia if g.faixa == "total"],
        }
    )
    DESTINO.write_text(reduzido.model_dump_json() + "\n", encoding="utf-8")
    sys.stdout.write(f"Escrito {DESTINO}\n")

    pa = agregado.montar(
        estado=CodigoEstado.PA,
        atual=agregado.cubos(boletins_sinteticos(20, n=20000), eleicao_geral("PA", 2026)),
        bases=[
            agregado.cubos(boletins_sinteticos(21, n=24000, ano=2022), eleicao_geral("PA", 2022)),
            agregado.cubos(boletins_sinteticos(22, n=30000, ano=2024), eleicao_geral("PA", 2024)),
        ],
        dados_ate=date(2026, 10, 24),
        dimensoes=("faixa", "partido", "modalidade", "condado", "distrito"),
        modalidades=("correio",),
        fontes=[
            Fonte.model_validate(
                {
                    "nome": "Dados sintéticos de teste",
                    "url": "https://exemplo.org/sintetico",
                    "obtida_em": datetime(2026, 10, 25, tzinfo=UTC),
                }
            )
        ],
        nomes_condados={"42001": "Adams", "42003": "Allegheny", "42101": "Philadelphia"},
        avisos=["Dados sintéticos: só para testes."],
        gerado_em=datetime(2026, 10, 25, tzinfo=UTC),
    )
    # Como acima, só as linhas que o site lê.
    pa = pa.model_copy(
        update={
            "serie": [
                p
                for p in pa.serie
                if p.faixa == "total" and p.partido == "total" and p.modalidade == "total"
            ]
        }
    )
    DESTINO_AGREGADO.write_text(pa.model_dump_json() + "\n", encoding="utf-8")
    sys.stdout.write(f"Escrito {DESTINO_AGREGADO}\n")


if __name__ == "__main__":
    main()
