"""Repete noites de 2022 ou 2024 com o Modelo C e mede a qualidade da projeção.

Uso, depois de gerar os instantes com o ensaio da recolha de resultados::

    uv run python -m pipeline.jobs.ensaio_resultados --estado NC --data 2022-11-08 \\
        --parciais data/brutos/repeticao/NC-2022
    uv run python -m pipeline.jobs.repeticao_noite --ano 2022 \\
        --parciais data/brutos/repeticao/NC-2022 data/brutos/repeticao/GA-2022 \\
        --saida data/brutos/repeticao/relatorio-2022.json

O ponto de partida é a previsão do backtest desse ano (a mesma que estaria congelada) e a
referência por condado é a presidencial anterior (2020). Cada passo junta o instante
correspondente de todos os estados. Com ``--ordem modos`` usa a reconstrução por modo de
voto (``noite.repeticao.por_modos``) em vez da ordem do ensaio. Por passo, regista:
corridas com votos, Brier, cobertura dos intervalos de 80% e erro absoluto da margem;
no fim, as corridas que chegaram a ter 99% para quem perdeu (chamadas erradas).
"""

import argparse
import json
import logging
from datetime import UTC, datetime
from pathlib import Path

from contratos.base import Fonte
from contratos.resultados import ResultadosParciais
from pipeline.jobs.avaliacao_previsao import DESEMPATE
from pipeline.modelo import carregar as carga
from pipeline.modelo.noite.entrada import de_parciais, ler_referencia
from pipeline.modelo.noite.projecao import projetar
from pipeline.modelo.noite.repeticao import finais, juntar, por_modos
from pipeline.modelo.previsao import prever
from pipeline.modelo.publicar import montar

registo = logging.getLogger(__name__)

REFERENCIA = Path("data/reference/modelo/presidencial_condados_2020.csv")
CHAMADA = 0.99
SIMULACOES = 10_000


def _ler(caminho: Path) -> ResultadosParciais:
    return ResultadosParciais.model_validate_json(caminho.read_text(encoding="utf-8"))


def sequencia(pasta: Path, ordem: str, passos: int, semente: int) -> list[ResultadosParciais]:
    final = _ler(pasta / "final.json")
    if ordem == "modos":
        return por_modos(final, passos, semente)
    return [_ler(p) for p in sorted((pasta / "instantes").glob("*.json"))] + [final]


def repetir(
    ano: int, pastas: list[Path], ordem: str, passos: int, semente: int
) -> dict[str, object]:
    agora = datetime.now(UTC)
    fonte = Fonte(
        nome="Referência do modelo e resultados oficiais (ensaio)",
        url="https://github.com/tpereira2005/intercalares-eua-2026",
        obtida_em=agora,
    )
    previsao = montar(prever(carga.carregar(), ano), fontes=[fonte], gerado_em=agora)
    referencia = ler_referencia(REFERENCIA)
    sequencias = [sequencia(p, ordem, passos, semente) for p in pastas]
    reais = {k: v for s in sequencias for k, v in finais(s[-1]).items()}
    n = max(len(s) for s in sequencias)
    linhas: list[dict[str, object]] = []
    maximo_perdedor: dict[str, float] = {}
    for i in range(n):
        instante = juntar([s[min(i, len(s) - 1)] for s in sequencias])
        projecao = projetar(
            previsao,
            de_parciais(instante),
            referencia,
            fontes=[fonte],
            gerado_em=agora,
            desempate=DESEMPATE[ano],
            simulacoes=SIMULACOES,
        )
        avaliadas = [c for c in projecao.corridas if c.id in reais and not c.decidida]
        brier = cobertura = erro = 0.0
        for c in avaliadas:
            real = reais[c.id]
            ganhou_d = real.vencedor == "D"
            brier += (c.prob_d - ganhou_d) ** 2
            cobertura += c.margem_p10 <= real.margem <= c.margem_p90
            erro += abs(c.margem_projetada - real.margem)
            perdedor = 1 - c.prob_d if ganhou_d else c.prob_d
            maximo_perdedor[c.id] = max(maximo_perdedor.get(c.id, 0.0), perdedor)
        k = max(len(avaliadas), 1)
        contados = sum(c.votos_contados for c in avaliadas)
        esperados = sum(c.votos_esperados or 0 for c in avaliadas)
        linhas.append(
            {
                "passo": i + 1,
                "corridas": len(avaliadas),
                "fracao_contada": contados / esperados if esperados else 0.0,
                "brier": brier / k,
                "cobertura_80": cobertura / k,
                "erro_absoluto": erro / k,
                "desvio_nacional": projecao.desvio_nacional.media,
            }
        )
        registo.info(
            "passo %2d: %.0f%% contado, Brier %.3f, cobertura %.2f, erro %.2f, desvio %+.1f",
            i + 1,
            100 * float(str(linhas[-1]["fracao_contada"])),
            brier / k,
            cobertura / k,
            erro / k,
            projecao.desvio_nacional.media,
        )
    erradas = sorted(c for c, p in maximo_perdedor.items() if p >= CHAMADA)
    piores = sorted(maximo_perdedor.items(), key=lambda x: -x[1])[:5]
    registo.info(
        "Maior probabilidade dada a quem perdeu: %s",
        ", ".join(f"{c} {p:.2f}" for c, p in piores),
    )
    registo.info("Chamadas erradas (>= %.0f%% para quem perdeu): %s", 100 * CHAMADA, erradas)
    return {
        "ano": ano,
        "ordem": ordem,
        "passos": linhas,
        "chamadas_erradas": erradas,
        "maior_probabilidade_perdedor": dict(piores),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ano", type=int, choices=(2022, 2024), required=True)
    parser.add_argument("--parciais", type=Path, nargs="+", required=True)
    parser.add_argument("--ordem", choices=("ensaio", "modos"), default="ensaio")
    parser.add_argument("--passos", type=int, default=12)
    parser.add_argument("--semente", type=int, default=0)
    parser.add_argument("--saida", type=Path, default=None)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    relatorio = repetir(args.ano, args.parciais, args.ordem, args.passos, args.semente)
    if args.saida is not None:
        args.saida.parent.mkdir(parents=True, exist_ok=True)
        args.saida.write_text(json.dumps(relatorio, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
