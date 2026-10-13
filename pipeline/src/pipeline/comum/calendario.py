"""Calendário eleitoral: datas das eleições gerais e janelas de voto antecipado presencial.

A comparação entre ciclos faz-se sempre por **dias antes da eleição** (``dias_antes``), a
única forma justa de comparar a mesma altura do ciclo. As janelas de voto presencial servem
para anotar os gráficos e saber se o voto presencial já começou.
"""

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True, slots=True)
class EleicaoGeral:
    estado: str
    data: date
    tipo: str
    """``"intercalar"`` ou ``"presidencial"``."""

    inicio_presencial: date | None
    fim_presencial: date | None
    referencia_historico: int | None
    """Ano da eleição anterior do mesmo tipo, usada para classificar o histórico de voto."""

    notas: tuple[str, ...] = ()

    @property
    def ano(self) -> int:
        return self.data.year

    def dias_antes(self, dia: date) -> int:
        return (self.data - dia).days

    def janela_presencial_dias_antes(self) -> tuple[int, int] | None:
        """(primeiro dia, último dia) do voto presencial, em dias antes da eleição."""
        if self.inicio_presencial is None or self.fim_presencial is None:
            return None
        return self.dias_antes(self.inicio_presencial), self.dias_antes(self.fim_presencial)


# Carolina do Norte. O voto antecipado presencial ("one-stop") começa na terceira
# quinta-feira antes da eleição e termina no último sábado (G.S. 163-227.6). Em 2018
# começou numa quarta-feira, 17 de outubro.
ELEICOES_NC: dict[int, EleicaoGeral] = {
    2018: EleicaoGeral(
        "NC",
        date(2018, 11, 6),
        "intercalar",
        date(2018, 10, 17),
        date(2018, 11, 3),
        None,
        ("O histórico individual público só cobre eleições desde 2016.",),
    ),
    2020: EleicaoGeral(
        "NC",
        date(2020, 11, 3),
        "presidencial",
        date(2020, 10, 15),
        date(2020, 10, 31),
        2016,
        ("Pandemia: voto por correspondência excecional; usar sempre com aviso.",),
    ),
    2022: EleicaoGeral(
        "NC", date(2022, 11, 8), "intercalar", date(2022, 10, 20), date(2022, 11, 5), 2018
    ),
    2024: EleicaoGeral(
        "NC",
        date(2024, 11, 5),
        "presidencial",
        date(2024, 10, 17),
        date(2024, 11, 2),
        2020,
        (
            "Primeira eleição geral com identificação com fotografia obrigatória.",
            "A correspondência passou a ter de chegar até às 19h30 do dia da eleição.",
            "O envio dos boletins por correio atrasou cerca de duas semanas (reimpressão "
            "ordenada pelos tribunais), o que atrasa a curva de correio de 2024.",
            "O furacão Helene (fim de setembro) afetou o oeste do estado.",
        ),
    ),
    2026: EleicaoGeral(
        "NC", date(2026, 11, 3), "intercalar", date(2026, 10, 15), date(2026, 10, 31), 2022
    ),
}


def eleicao_nc(ano: int) -> EleicaoGeral:
    try:
        return ELEICOES_NC[ano]
    except KeyError as erro:
        msg = f"Eleição geral da Carolina do Norte desconhecida: {ano}"
        raise ValueError(msg) from erro


DATAS_ELEICOES_GERAIS: dict[int, date] = {
    2014: date(2014, 11, 4),
    2016: date(2016, 11, 8),
    2018: date(2018, 11, 6),
    2020: date(2020, 11, 3),
    2022: date(2022, 11, 8),
    2024: date(2024, 11, 5),
    2026: date(2026, 11, 3),
}
"""Primeira terça-feira depois da primeira segunda-feira de novembro (igual em todos os estados)."""


def eleicao_geral(estado: str, ano: int, notas: tuple[str, ...] = ()) -> EleicaoGeral:
    """Eleição geral de ``ano`` num estado sem janela de voto presencial modelada aqui.

    Para estados onde o voto antecipado presencial não existe ou não se distingue na fonte
    (na Pensilvânia, por exemplo, tudo é voto por correspondência).
    """
    try:
        data = DATAS_ELEICOES_GERAIS[ano]
    except KeyError as erro:
        msg = f"Ano sem eleição geral conhecida: {ano}"
        raise ValueError(msg) from erro
    tipo = "presidencial" if ano % 4 == 0 else "intercalar"
    return EleicaoGeral(estado, data, tipo, None, None, None, notas)
