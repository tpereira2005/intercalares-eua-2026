"""CSV ``id,vencedor,margem`` para a avaliação da previsão (``jobs.avaliacao_previsao``).

Só entram as corridas com todas as secções apuradas e um candidato democrata ou
republicano à frente. Não é uma chamada de vencedor durante a noite: serve para avaliar a
previsão depois de a contagem acabar. ``margem`` é D-R em pontos percentuais do total.
"""

import csv
import io
from collections.abc import Iterable

from contratos.resultados import ResultadosEstado

CASAS = 3


def linhas(estados: Iterable[ResultadosEstado]) -> list[tuple[str, str, float]]:
    resultado = []
    for estado in estados:
        for c in estado.corridas:
            if c.cargo == "governador" or not c.total or not c.candidatos:
                continue
            if c.unidades_totais is None or c.unidades_reportadas != c.unidades_totais:
                continue
            primeiro = c.candidatos[0]
            if primeiro.partido == "outro":
                continue
            d = sum(x.votos for x in c.candidatos if x.partido == "dem")
            r = sum(x.votos for x in c.candidatos if x.partido == "rep")
            vencedor = "D" if primeiro.partido == "dem" else "R"
            resultado.append((c.id, vencedor, round(100 * (d - r) / c.total, CASAS)))
    return sorted(resultado)


def csv_avaliacao(estados: Iterable[ResultadosEstado]) -> str:
    saida = io.StringIO()
    escritor = csv.writer(saida, lineterminator="\n")
    escritor.writerow(["id", "vencedor", "margem"])
    escritor.writerows(linhas(estados))
    return saida.getvalue()
