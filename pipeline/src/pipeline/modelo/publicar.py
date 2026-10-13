"""Conversão de uma previsão (e dos backtests) para o contrato ``PrevisaoCongresso``."""

from collections.abc import Sequence
from datetime import datetime

import numpy as np
import numpy.typing as npt

from contratos.base import Fonte, Metadados
from contratos.estados import CodigoEstado
from contratos.previsao import (
    AgregadorVotoGenerico,
    AmbienteNacional,
    Backtest,
    FonteAmbiente,
    ParametrosErroSondagens,
    ParametrosFundamentos,
    PontoDistribuicao,
    PrevisaoCongresso,
    PrevisaoCorrida,
    ResumoCamara,
)
from pipeline.modelo.dados import LinhaModelo
from pipeline.modelo.estimacao import Fundamentos
from pipeline.modelo.previsao import DATAS_ELEICAO, SIMULACOES, Dados, Previsao, corte_final
from pipeline.modelo.simulacao import ResultadoCamara, ResultadoCorrida

LUGARES_CAMARA = 435
LUGARES_SENADO = 100
MAIORIA_SENADO = 51
LIMITE_COMPETITIVO = 15.0
"""Corridas com margem prevista abaixo deste valor contam para o viés e o erro médio."""

FONTES_AMBIENTE: dict[str, FonteAmbiente] = {
    "agregadores": "agregadores",
    "media_sondagens_voto_generico": "media_sondagens_voto_generico",
    "sondagens_senado": "sondagens_senado",
}

NOTAS = (
    "Margens em pontos percentuais, sempre Democrata menos Republicano (D\u2212R).",
    "Os parâmetros estimam-se só com eleições anteriores ao ano previsto; os backtests usam "
    "exatamente o mesmo código com os dados disponíveis dois dias antes de cada eleição.",
    "Nenhuma correção de sinal é aplicada ao voto genérico: o erro histórico entra só como "
    "dimensão da incerteza, igual para os dois lados.",
    "O voto antecipado não altera a previsão (peso 0): três ciclos de um só estado não chegam "
    "para calibrar um peso. Mostra-se à parte como diagnóstico.",
)


def _int(valor: float) -> int:
    return round(valor)


def resumo_camara(
    resultado: ResultadoCamara, camara: str, fora_d: int = 0, fora_r: int = 0
) -> ResumoCamara:
    lugares = resultado.lugares_d
    contagens = np.bincount(lugares)
    total = len(lugares)
    distribuicao = tuple(
        PontoDistribuicao(lugares=i, probabilidade=float(c) / total)
        for i, c in enumerate(contagens)
        if c > 0
    )
    p5, p10, p50, p90, p95 = np.percentile(lugares, [5, 10, 50, 90, 95])
    return ResumoCamara(
        camara="camara" if camara == "camara" else "senado",
        lugares_total=LUGARES_CAMARA if camara == "camara" else LUGARES_SENADO,
        maioria=LUGARES_CAMARA // 2 + 1 if camara == "camara" else MAIORIA_SENADO,
        prob_controlo_d=resultado.prob_controlo_d,
        prob_controlo_r=resultado.prob_controlo_r,
        lugares_d_media=float(np.mean(lugares)),
        lugares_d_p5=_int(p5),
        lugares_d_p10=_int(p10),
        lugares_d_mediana=_int(p50),
        lugares_d_p90=_int(p90),
        lugares_d_p95=_int(p95),
        lugares_independentes_media=float(np.mean(resultado.lugares_i)),
        lugares_fora_de_jogo_d=fora_d,
        lugares_fora_de_jogo_r=fora_r,
        limiar_nacional=resultado.limiar_nacional,
        distribuicao=distribuicao,
    )


def _incumbente(linha: LinhaModelo) -> str | None:
    if linha.incumbente > 0:
        return "I" if linha.lado_d_independente else "D"
    if linha.incumbente < 0:
        return "I" if linha.lado_r_independente else "R"
    return None


def previsao_corrida(corrida: ResultadoCorrida) -> PrevisaoCorrida:
    linha = corrida.linha
    sond = corrida.sondagens
    inc = _incumbente(linha)
    certo = linha.certo
    return PrevisaoCorrida(
        id=linha.id,
        camara="camara" if linha.camara == "camara" else "senado",
        estado=CodigoEstado(linha.estado),
        candidato_d=linha.lado_d or None,
        candidato_r=linha.lado_r or None,
        lado_d_independente=linha.lado_d_independente,
        lado_r_independente=linha.lado_r_independente,
        incumbente_recandidato="D" if inc == "D" else "R" if inc == "R" else "I" if inc else None,
        pvi=linha.pvi / 2.0,
        decidida="D" if certo == "D" else "R" if certo == "R" else "I" if certo else None,
        margem_fundamentos=corrida.fundamentos if certo is None else corrida.media,
        margem_sondagens=sond.margem if sond is not None else None,
        institutos=sond.institutos if sond is not None else 0,
        peso_sondagens=corrida.peso_sondagens,
        margem_prevista=corrida.media,
        margem_p10=corrida.p10,
        margem_p90=corrida.p90,
        prob_d=corrida.prob_d,
    )


def parametros_fundamentos(
    fund: Fundamentos, camara: str, anos: Sequence[int]
) -> ParametrosFundamentos:
    return ParametrosFundamentos(
        camara="camara" if camara == "camara" else "senado",
        anos_treino=tuple(anos),
        observacoes=fund.observacoes,
        intercepto=fund.intercepto,
        inclinacao_pvi=fund.inclinacao,
        incumbencia=fund.incumbencia,
        persistencia=fund.persistencia,
        desvio_ano=fund.sd_ano,
        desvio_regiao=fund.sd_regiao,
        desvio_corrida=fund.sd_corrida,
    )


def _lugares_reais(resultado: ResultadoCamara, base: int) -> int:
    ganhos = 0
    for c in resultado.corridas:
        if c.linha.certo is not None:
            ganhos += c.linha.certo in {"D", "I"}
        else:
            ganhos += c.linha.vencedor == "D"
    return base + ganhos


def _controlo_real(lugares_d: int, total: int, desempate: str) -> str:
    if 2 * lugares_d > total:
        return "D"
    if 2 * lugares_d == total:
        return "D" if desempate == "D" else "R"
    return "R"


def avaliar(previsao: Previsao, dados: Dados, desempate_real: str = "R") -> list[Backtest]:
    """Compara uma previsão de um ano passado com os resultados reais."""
    backtests: list[Backtest] = []
    camaras: tuple[tuple[str, ResultadoCamara, int, int], ...] = (
        ("camara", previsao.camara, 0, LUGARES_CAMARA),
        ("senado", previsao.senado, previsao.composicao.continuam_d, LUGARES_SENADO),
    )
    for nome, resultado, base, total in camaras:
        avaliadas = [c for c in resultado.corridas if c.linha.margem is not None]
        if not avaliadas:
            continue
        reais = np.array([c.linha.margem or 0.0 for c in avaliadas])
        medias = np.array([c.media for c in avaliadas])
        probs = np.array([c.prob_d for c in avaliadas])
        dentro = np.array([c.p10 <= (c.linha.margem or 0.0) <= c.p90 for c in avaliadas])
        competitivas = np.abs(medias) < LIMITE_COMPETITIVO
        lugares_reais = _lugares_reais(resultado, base)
        lugares = resultado.lugares_d
        backtests.append(
            Backtest(
                ano=previsao.ano,
                camara="camara" if nome == "camara" else "senado",
                corte=previsao.corte,
                ambiente_previsto=previsao.ambiente.margem,
                ambiente_real=dados.nacional[previsao.ano],
                fonte_ambiente=FONTES_AMBIENTE[previsao.fonte_ambiente],
                prob_controlo_d=resultado.prob_controlo_d,
                prob_controlo_r=resultado.prob_controlo_r,
                controlo_real="D"
                if _controlo_real(lugares_reais, total, desempate_real) == "D"
                else "R",
                lugares_d_mediana=_int(float(np.median(lugares))),
                lugares_d_p10=_int(float(np.percentile(lugares, 10))),
                lugares_d_p90=_int(float(np.percentile(lugares, 90))),
                lugares_d_reais=lugares_reais,
                corridas_avaliadas=len(avaliadas),
                corridas_erradas=tuple(
                    c.linha.id for c in avaliadas if (c.prob_d > 0.5) != ((c.linha.margem or 0) > 0)
                ),
                brier=float(np.mean((probs - (reais > 0)) ** 2)),
                vies_competitivas=_media(medias[competitivas] - reais[competitivas]),
                erro_absoluto_competitivas=_media(
                    np.abs(medias[competitivas] - reais[competitivas])
                ),
                cobertura_80=float(np.mean(dentro)),
            )
        )
    return backtests


def _media(valores: npt.NDArray[np.float64]) -> float:
    return float(np.mean(valores)) if len(valores) else 0.0


def montar(
    previsao: Previsao,
    *,
    fontes: Sequence[Fonte],
    gerado_em: datetime,
    agregadores: Sequence[tuple[str, float]] = (),
    backtests: Sequence[Backtest] = (),
) -> PrevisaoCongresso:
    """Monta o ficheiro publicado a partir de uma previsão já calculada."""
    composicao = previsao.composicao
    corridas = [*previsao.camara.corridas, *previsao.senado.corridas]
    return PrevisaoCongresso(
        metadados=Metadados(gerado_em=gerado_em, fontes=tuple(fontes)),
        ano=previsao.ano,
        data_eleicao=DATAS_ELEICAO[previsao.ano],
        corte=previsao.corte,
        congelada=previsao.corte >= corte_final(previsao.ano),
        simulacoes=SIMULACOES,
        semente=previsao.semente,
        ambiente=AmbienteNacional(
            margem=previsao.ambiente.margem,
            desvio_padrao=previsao.ambiente.sd,
            fonte=FONTES_AMBIENTE[previsao.fonte_ambiente],
            agregadores=tuple(
                AgregadorVotoGenerico(nome=nome, margem=margem) for nome, margem in agregadores
            ),
        ),
        camara=resumo_camara(previsao.camara, "camara"),
        senado=resumo_camara(
            previsao.senado, "senado", composicao.continuam_d, composicao.continuam_r
        ),
        corridas=tuple(previsao_corrida(c) for c in corridas),
        fundamentos=(
            parametros_fundamentos(previsao.fundamentos_camara, "camara", previsao.anos_treino),
            parametros_fundamentos(previsao.fundamentos_senado, "senado", previsao.anos_treino),
        ),
        erro_sondagens=ParametrosErroSondagens(
            observacoes=previsao.erro_sondagens.observacoes,
            erro_base=previsao.erro_sondagens.base,
            erro_por_instituto=previsao.erro_sondagens.por_instituto,
            desvio_ano=previsao.erro_sondagens.sd_ano,
            ligacao_nacional=previsao.erro_sondagens.ligacao_nacional,
        ),
        peso_voto_antecipado=0.0,
        backtests=tuple(backtests),
        notas=NOTAS,
    )
