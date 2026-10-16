"""Estados que o job do UF Election Lab publica, e o que a fonte cobre em cada um."""

from dataclasses import dataclass

from contratos.estados import CodigoEstado

OFICIAIS = frozenset(
    {
        CodigoEstado.NC,
        CodigoEstado.PA,
        CodigoEstado.ME,
        CodigoEstado.FL,
        CodigoEstado.IA,
        CodigoEstado.CO,
        CodigoEstado.AZ,
    }
)
"""Estados que já têm fonte própria (oficial, ou o Arizona com a Stealth Analytics). Nunca
se publicam a partir do UF Election Lab, para o resumo nacional não duplicar estados."""


@dataclass(frozen=True, slots=True)
class EstadoUF:
    estado: CodigoEstado
    modalidades: tuple[str, ...]
    """Modalidades que a fonte separa neste estado."""

    avisos: tuple[str, ...] = ()


ESTADOS: dict[CodigoEstado, EstadoUF] = {
    CodigoEstado.GA: EstadoUF(
        CodigoEstado.GA,
        ("correio", "presencial"),
        (
            "Os votos juntam o ficheiro estadual de voto por correspondência com os totais "
            "por condado do painel de participação da Geórgia (vale o valor mais alto em "
            "cada condado), para incluir o voto presencial antecipado do próprio dia.",
        ),
    ),
    CodigoEstado.MI: EstadoUF(
        CodigoEstado.MI,
        ("correio",),
        (
            "A fonte só conta os boletins devolvidos: o voto presencial antecipado não vem "
            "separado.",
        ),
    ),
    CodigoEstado.OH: EstadoUF(
        CodigoEstado.OH,
        ("correio", "presencial"),
        (
            "O voto presencial antecipado é aproximado: conta-se como presencial um boletim "
            "enviado e recebido no mesmo dia, por isso pode diferir do que o Secretary of "
            "State do Ohio publica.",
        ),
    ),
    CodigoEstado.NV: EstadoUF(CodigoEstado.NV, ("correio", "presencial")),
    CodigoEstado.TX: EstadoUF(CodigoEstado.TX, ("correio", "presencial")),
}
"""Os estados prioritários cujo servidor oficial bloqueia a recolha automática. Um estado
sem votos no ficheiro (o Texas, a 16 de outubro de 2026) não gera ficheiro."""
