"""Evolução da projeção ao longo da noite (contrato ``HistoricoNoite``).

A recolha de resultados produz um instante novo a cada 30 s nos momentos de mais
atividade. Guardar todos faria o ficheiro crescer sem limite, por isso dois pontos
guardados seguidos distam pelo menos ``intervalo``. O último ponto é sempre a projeção
mais recente e é provisório: enquanto não distar ``intervalo`` do penúltimo, o ponto
seguinte substitui-o.
"""

from collections.abc import Iterable
from datetime import timedelta

from contratos.base import Metadados
from contratos.noite import (
    HistoricoNoite,
    PontoNoite,
    PontoNoiteCamara,
    PontoNoiteCorrida,
    ProjecaoNoite,
    ResumoCamaraNoite,
)
from pipeline.comum.erros import ErroPipeline

INTERVALO = timedelta(minutes=5)


class HistoricoIncompativel(ErroPipeline):
    """O histórico existente partiu de outra previsão ou de outra noite."""


def _camara(r: ResumoCamaraNoite) -> PontoNoiteCamara:
    return PontoNoiteCamara(
        prob_controlo_d=r.prob_controlo_d,
        prob_controlo_r=r.prob_controlo_r,
        lugares_d_mediana=r.lugares_d_mediana,
        lugares_d_p10=r.lugares_d_p10,
        lugares_d_p90=r.lugares_d_p90,
        corridas_com_votos=r.corridas_com_votos,
    )


def ponto(projecao: ProjecaoNoite) -> PontoNoite:
    """Reduz uma projeção ao que os gráficos de evolução precisam."""
    com_votos = [c for c in projecao.corridas if c.votos_contados > 0]
    return PontoNoite(
        instante=projecao.instante,
        gerado_em=projecao.metadados.gerado_em,
        desvio_nacional=projecao.desvio_nacional.media,
        votos_contados=sum(c.votos_contados for c in com_votos),
        camara=_camara(projecao.camara),
        senado=_camara(projecao.senado),
        corridas=tuple(
            PontoNoiteCorrida(
                id=c.id,
                prob_d=c.prob_d,
                margem_projetada=c.margem_projetada,
                margem_p10=c.margem_p10,
                margem_p90=c.margem_p90,
                fracao_contada=c.fracao_contada,
            )
            for c in com_votos
        ),
    )


def _espacar(
    pontos: Iterable[PontoNoite], novo: PontoNoite, intervalo: timedelta
) -> list[PontoNoite]:
    lista = [p for p in pontos if p.instante < novo.instante]
    if len(lista) >= 2 and lista[-1].instante - lista[-2].instante < intervalo:
        lista.pop()
    lista.append(novo)
    return lista


def acrescentar(
    anterior: HistoricoNoite | None,
    projecao: ProjecaoNoite,
    *,
    intervalo: timedelta = INTERVALO,
) -> HistoricoNoite:
    """Acrescenta a projeção ao histórico (ou começa um novo).

    Um instante igual ou anterior a um já guardado substitui os pontos a partir dele: a
    recolha pode ter recomeçado com retratos corrigidos.
    """
    if anterior is not None and (
        anterior.ano != projecao.ano
        or anterior.corte_prior != projecao.corte_prior
        or anterior.reconstruido != projecao.reconstruido
    ):
        raise HistoricoIncompativel(
            f"histórico de {anterior.ano} com corte {anterior.corte_prior} "
            f"(reconstruído: {anterior.reconstruido}); projeção de {projecao.ano} com corte "
            f"{projecao.corte_prior} (reconstruída: {projecao.reconstruido})"
        )
    pontos = _espacar(anterior.pontos if anterior else (), ponto(projecao), intervalo)
    return HistoricoNoite(
        metadados=Metadados(
            gerado_em=projecao.metadados.gerado_em, fontes=projecao.metadados.fontes
        ),
        ano=projecao.ano,
        corte_prior=projecao.corte_prior,
        prior_congelado=projecao.prior_congelado,
        reconstruido=projecao.reconstruido,
        intervalo_minutos=int(intervalo.total_seconds() // 60),
        pontos=tuple(pontos),
    )
