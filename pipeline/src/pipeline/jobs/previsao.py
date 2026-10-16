"""Calcula a previsão para a Câmara e o Senado e grava o ficheiro publicado.

Uso::

    uv run python -m pipeline.jobs.previsao --saida data/publicado/previsao/2026.json

Lê a referência versionada em ``data/reference/modelo`` (eleições de 2012 a 2024),
descarrega da Wikipédia as listas de candidatos, os PVI e as sondagens de 2026 e corre os
backtests de 2018, 2022 e 2024 com o mesmo código. Depois de 1 de novembro de 2026 o
corte fica fixo: a previsão publicada é a congelada.

Com ``--cenarios`` grava também a grelha de cenários do ambiente nacional, calculada pelo
mesmo simulador (``modelo.cenarios``); com ``--alteracoes``, o registo de alterações do
método (``modelo.alteracoes``); com ``--sensibilidade``, a análise de sensibilidade de
2026, sem backtests (``jobs.sensibilidade_previsao``). No GitHub Actions, os ficheiros
levam o commit que os gerou.
"""

import argparse
import logging
import os
import re
from datetime import UTC, date, datetime
from pathlib import Path

import httpx

from contratos.base import Fonte
from contratos.previsao import HistoricoPrevisao
from contratos.sondagens import SondagensCongresso
from pipeline.modelo import alteracoes as registo_alteracoes
from pipeline.modelo import carregar as carga
from pipeline.modelo import cenarios as grelha_cenarios
from pipeline.modelo import publicar_sondagens
from pipeline.modelo.dados import LinhaModelo
from pipeline.modelo.fontes import wikipedia
from pipeline.modelo.historico import acrescentar
from pipeline.modelo.previsao import DATAS_ELEICAO, Dados, corte_final, estimar, prever
from pipeline.modelo.publicar import avaliar, montar
from pipeline.modelo.verificacoes import PrevisaoIncoerente, exigir_coerencia

registo = logging.getLogger(__name__)

ANOS_BACKTEST = (2018, 2022, 2024)
DESEMPATE_REAL = {2018: "R", 2022: "D", 2024: "R"}
"""Partido do vice-presidente no Congresso eleito (decide um Senado 50-50)."""

URL_WIKIPEDIA = "https://en.wikipedia.org/wiki/"
URL_REPOSITORIO = "https://github.com/tpereira2005/intercalares-eua-2026"


def codigo_commit() -> str | None:
    """Commit que gerou os ficheiros (``GITHUB_SHA`` no GitHub Actions)."""
    sha = os.environ.get("GITHUB_SHA", "").strip().lower()
    return sha if re.fullmatch(r"[0-9a-f]{7,40}", sha) else None


def fontes(agora: datetime) -> list[Fonte]:
    titulos = (carga.titulo_casa(carga.ANO_ATUAL), carga.titulo_senado(carga.ANO_ATUAL))
    resultado = [
        Fonte(
            nome=f"Wikipédia: {titulo}",
            url=URL_WIKIPEDIA + titulo.replace(" ", "_"),
            licenca="CC BY-SA 4.0",
            obtida_em=agora,
        )
        for titulo in titulos
    ]
    resultado.append(
        Fonte(
            nome="FiveThirtyEight: raw_polls.csv (sondagens e resultados até 2022)",
            url=carga.URL_538,
            licenca="CC BY 4.0",
            obtida_em=agora,
        )
    )
    return resultado


def _dados(*, atualizar: bool) -> tuple[Dados, float, list[tuple[str, float]]]:
    """Referência versionada mais os dados de 2026 (corridas, sondagens, classificações)."""
    with httpx.Client(
        headers={"User-Agent": wikipedia.USER_AGENT}, timeout=60.0, follow_redirects=True
    ) as cliente:
        corridas, sondagens, redesenhados, (generico, agregadores) = carga.dados_2026(
            cliente, atualizar=atualizar
        )
        classificacoes = carga.classificacoes_2026(cliente, atualizar=atualizar)
    dados = carga.carregar(
        atual=corridas,
        sondagens_atuais=sondagens,
        redesenho_atual=redesenhados,
        classificacoes_atuais=classificacoes,
    )
    return dados, generico, agregadores


def executar(
    saida: Path,
    *,
    corte: date | None,
    atualizar: bool,
    historico: Path | None = None,
    ficheiro_sondagens: Path | None = None,
    ficheiro_cenarios: Path | None = None,
    ficheiro_alteracoes: Path | None = None,
    ficheiro_sensibilidade: Path | None = None,
) -> None:
    final = corte_final(carga.ANO_ATUAL)
    corte = min(corte or datetime.now(UTC).date(), final)
    dados, generico, agregadores = _dados(atualizar=atualizar)
    backtests = []
    for ano in ANOS_BACKTEST:
        backtests.extend(avaliar(prever(dados, ano), dados, DESEMPATE_REAL[ano]))
    ambiente_publicado = (generico, "agregadores") if agregadores else None
    previsao = prever(dados, carga.ANO_ATUAL, corte=corte, ambiente_publicado=ambiente_publicado)
    agora = datetime.now(UTC)
    commit = codigo_commit()
    ficheiro = montar(
        previsao,
        fontes=fontes(agora),
        gerado_em=agora,
        agregadores=agregadores,
        backtests=backtests,
        codigo_commit=commit,
    )
    exigir_coerencia(ficheiro, dados.corridas[carga.ANO_ATUAL])
    saida.parent.mkdir(parents=True, exist_ok=True)
    saida.write_text(ficheiro.model_dump_json(indent=1), encoding="utf-8")
    registo.info(
        "Previsão gravada em %s: Câmara P(D)=%.3f, Senado P(D)=%.3f",
        saida,
        ficheiro.camara.prob_controlo_d,
        ficheiro.senado.prob_controlo_d,
    )
    if historico is not None:
        anterior = (
            HistoricoPrevisao.model_validate_json(historico.read_text(encoding="utf-8"))
            if historico.exists()
            else None
        )
        novo = acrescentar(anterior, ficheiro)
        historico.parent.mkdir(parents=True, exist_ok=True)
        historico.write_text(novo.model_dump_json(), encoding="utf-8")
        registo.info("Histórico com %d dias gravado em %s", len(novo.dias), historico)
    if ficheiro_cenarios is not None:
        cenarios = grelha_cenarios.calcular(
            dados,
            carga.ANO_ATUAL,
            corte,
            ambiente_publicado,
            fontes=fontes(agora),
            gerado_em=agora,
            codigo_commit=commit,
        )
        base = next(
            c for c in cenarios.cenarios if c.desvio_ambiente == 0 and c.fator_erro_sondagens == 1
        )
        if (base.camara.prob_controlo_d, base.senado.prob_controlo_d) != (
            ficheiro.camara.prob_controlo_d,
            ficheiro.senado.prob_controlo_d,
        ):
            raise PrevisaoIncoerente("O cenário de base não reproduz a previsão publicada")
        ficheiro_cenarios.parent.mkdir(parents=True, exist_ok=True)
        ficheiro_cenarios.write_text(cenarios.model_dump_json(), encoding="utf-8")
        registo.info("%d cenários gravados em %s", len(cenarios.cenarios), ficheiro_cenarios)
    if ficheiro_sensibilidade is not None:
        # Importação tardia: o job da sensibilidade importa constantes deste módulo.
        from pipeline.jobs import sensibilidade_previsao  # noqa: PLC0415

        linhas_sensibilidade = sensibilidade_previsao.analisar(
            dados, corte, ambiente_publicado, backtests=False
        )
        sensibilidade = sensibilidade_previsao.contrato(
            linhas_sensibilidade,
            ano=carga.ANO_ATUAL,
            corte=corte,
            fontes=fontes(agora),
            gerado_em=agora,
            codigo_commit=commit,
        )
        base_sensibilidade = sensibilidade.variantes[0]
        if base_sensibilidade.nome != "Modelo publicado" or (
            base_sensibilidade.camara.prob_controlo_d,
            base_sensibilidade.senado.prob_controlo_d,
        ) != (ficheiro.camara.prob_controlo_d, ficheiro.senado.prob_controlo_d):
            raise PrevisaoIncoerente(
                "A variante de base da sensibilidade não reproduz a previsão publicada"
            )
        ficheiro_sensibilidade.parent.mkdir(parents=True, exist_ok=True)
        ficheiro_sensibilidade.write_text(sensibilidade.model_dump_json(), encoding="utf-8")
        registo.info(
            "%d variantes de sensibilidade gravadas em %s",
            len(sensibilidade.variantes),
            ficheiro_sensibilidade,
        )
    if ficheiro_alteracoes is not None:
        alteracoes = registo_alteracoes.montar(
            carga.ANO_ATUAL,
            fontes=[
                Fonte(
                    nome="Escrutínio: registo de alterações do método",
                    url=f"{URL_REPOSITORIO}/blob/main/{registo_alteracoes.REGISTO}",
                    obtida_em=agora,
                )
            ],
            gerado_em=agora,
        )
        ficheiro_alteracoes.parent.mkdir(parents=True, exist_ok=True)
        ficheiro_alteracoes.write_text(alteracoes.model_dump_json(indent=1), encoding="utf-8")
        registo.info(
            "%d alterações do método gravadas em %s",
            len(alteracoes.alteracoes),
            ficheiro_alteracoes,
        )
    if ficheiro_sondagens is not None:
        linhas = [c.linha for c in previsao.senado.corridas if c.linha.certo is None]
        minimo, maximo = publicar_sondagens.COMPETITIVA
        competitivas = [
            c.linha
            for c in previsao.camara.corridas
            if c.linha.certo is None and minimo <= c.prob_d <= maximo
        ]
        escrever_sondagens(
            ficheiro_sondagens,
            dados=dados,
            corte=corte,
            linhas=linhas,
            agregadores=agregadores,
            agora=agora,
            linhas_camara=competitivas,
            atualizar=atualizar,
        )


def escrever_sondagens(
    caminho: Path,
    *,
    dados: Dados,
    corte: date,
    linhas: list[LinhaModelo],
    agregadores: list[tuple[str, float]],
    agora: datetime,
    linhas_camara: list[LinhaModelo],
    atualizar: bool,
) -> None:
    """Atualiza o ficheiro das sondagens (a série do voto genérico continua a anterior)."""
    anterior = ler_sondagens(caminho)
    with httpx.Client(
        headers={"User-Agent": wikipedia.USER_AGENT}, timeout=60.0, follow_redirects=True
    ) as cliente:
        sondagens_camara = carga.sondagens_camara_wikipedia(linhas_camara, cliente, atualizar)
    ficheiro = publicar_sondagens.montar(
        dados,
        carga.ANO_ATUAL,
        corte,
        linhas,
        agregadores,
        anterior=anterior,
        fontes=fontes(agora),
        gerado_em=agora,
        referencia_generico=publicar_sondagens.ler_referencia_generico(),
        linhas_camara=linhas_camara,
        sondagens_camara=sondagens_camara,
    )
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.write_text(ficheiro.model_dump_json(), encoding="utf-8")
    registo.info(
        "Sondagens de %d corridas e %d dias do voto genérico gravadas em %s",
        len(ficheiro.corridas),
        len(ficheiro.voto_generico),
        caminho,
    )


def apenas_sondagens(caminho: Path, *, atualizar: bool) -> None:
    """Depois do congelamento: atualiza só as sondagens, até ao dia da eleição.

    A previsão congelada não muda; as sondagens usam o corte de hoje (exclusive), sem o
    limite de 1 de novembro.
    """
    corte = min(datetime.now(UTC).date(), DATAS_ELEICAO[carga.ANO_ATUAL])
    with httpx.Client(
        headers={"User-Agent": wikipedia.USER_AGENT}, timeout=60.0, follow_redirects=True
    ) as cliente:
        corridas, sondagens, redesenhados, (_, agregadores) = carga.dados_2026(
            cliente, atualizar=atualizar
        )
    dados = carga.carregar(atual=corridas, sondagens_atuais=sondagens, redesenho_atual=redesenhados)
    _, linhas_senado = estimar(dados, carga.ANO_ATUAL, "senado")
    linhas = [ln for ln in linhas_senado[carga.ANO_ATUAL] if ln.certo is None]
    # Os distritos são os do último ficheiro publicado antes do congelamento.
    anterior = ler_sondagens(caminho)
    distritos = {c.id for c in anterior.corridas if c.camara == "camara"} if anterior else set()
    _, linhas_c = estimar(dados, carga.ANO_ATUAL, "camara")
    escrever_sondagens(
        caminho,
        dados=dados,
        corte=corte,
        linhas=linhas,
        agregadores=agregadores,
        agora=datetime.now(UTC),
        linhas_camara=[ln for ln in linhas_c[carga.ANO_ATUAL] if ln.id in distritos],
        atualizar=atualizar,
    )


def ler_sondagens(caminho: Path) -> SondagensCongresso | None:
    if not caminho.exists():
        return None
    return SondagensCongresso.model_validate_json(caminho.read_text(encoding="utf-8"))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--saida", type=Path, help="Ficheiro da previsão (exceto com --apenas-sondagens)."
    )
    parser.add_argument(
        "--corte",
        type=date.fromisoformat,
        default=None,
        help="Data de corte (AAAA-MM-DD); por omissão hoje, nunca depois de 1 de novembro.",
    )
    parser.add_argument(
        "--sem-descarga",
        action="store_true",
        help="Usa só as páginas da Wikipédia já guardadas em data/brutos/modelo/wiki.",
    )
    parser.add_argument(
        "--historico",
        type=Path,
        default=None,
        help="Ficheiro do histórico diário a atualizar (criado se não existir).",
    )
    parser.add_argument(
        "--sondagens",
        type=Path,
        default=None,
        help="Ficheiro das sondagens para o site a atualizar (criado se não existir).",
    )
    parser.add_argument(
        "--cenarios",
        type=Path,
        default=None,
        help="Ficheiro da grelha de cenários do ambiente nacional (CenariosPrevisao).",
    )
    parser.add_argument(
        "--alteracoes",
        type=Path,
        default=None,
        help="Ficheiro do registo de alterações do método (AlteracoesPrevisao).",
    )
    parser.add_argument(
        "--sensibilidade",
        type=Path,
        default=None,
        help="Ficheiro da análise de sensibilidade, sem backtests (SensibilidadePrevisao).",
    )
    parser.add_argument(
        "--apenas-sondagens",
        action="store_true",
        help="Depois do congelamento: atualiza só o ficheiro das sondagens (até à eleição).",
    )
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    if args.apenas_sondagens:
        if args.sondagens is None:
            parser.error("--apenas-sondagens precisa de --sondagens")
        apenas_sondagens(args.sondagens, atualizar=not args.sem_descarga)
        return
    if args.saida is None:
        parser.error("--saida é obrigatório")
    executar(
        args.saida,
        corte=args.corte,
        atualizar=not args.sem_descarga,
        historico=args.historico,
        ficheiro_sondagens=args.sondagens,
        ficheiro_cenarios=args.cenarios,
        ficheiro_alteracoes=args.alteracoes,
        ficheiro_sensibilidade=args.sensibilidade,
    )


if __name__ == "__main__":
    main()
