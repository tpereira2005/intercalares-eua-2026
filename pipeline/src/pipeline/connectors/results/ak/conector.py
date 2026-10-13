"""Conector de resultados do Alasca.

Na noite eleitoral, a Division of Elections publica um CSV com uma linha por secção,
corrida e candidato (``GA_ENR_Precinct_State_of_Alaska.csv``, em ``/enr<aa>/results/``),
com os votos totais e por tipo: dia da eleição, voto antecipado por correspondência
(``Absentee``), voto antecipado presencial (``Early Voting``), votos contestados
(``Question``, o provisório) e ``Remote``. O mesmo formato fica publicado depois de cada
eleição (``ENRbyPrecinct.csv`` em 2024).

O Alasca não tem condados: só se publica o total do estado. As secções incluem, em cada
distrito da câmara estadual, pseudo-secções para o voto antecipado, por correspondência e
contestado, que vão sendo contadas nos dias seguintes. Uma secção conta como apurada
quando tem boletins ou a fonte a marca como reportada (``Reporting_flag``, que nos
ficheiros finais vem sempre a 0). No voto preferencial, só a primeira escolha.

O servidor envia um certificado intermédio errado; o pipeline junta o intermédio que o
próprio certificado indica (ver ``pipeline.comum.descarga.contexto_tls``).
"""

from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

import polars as pl

from contratos.estados import CodigoEstado
from pipeline.comum.erros import ErroDescarga, ErroFormatoFonte
from pipeline.connectors.results.comum import ObterTexto, Pedido, identificar_corrida, partido
from pipeline.transform.resultados.montar import (
    COLUNAS_MODALIDADES,
    COLUNAS_UNIDADES,
    COLUNAS_VOTOS,
    Leitura,
)

FICHEIRO = "seccoes.csv"
CAMPOS = (
    "Precinct_name",
    "Reporting_flag",
    "Contest_title",
    "candidate_name",
    "Party_Code",
    "total_ballots",
    "total_votes",
)
MODALIDADES = {
    "Election Day_votes": "dia_eleicao",
    "Absentee_votes": "correio",
    "Early Voting_votes": "antecipado_presencial",
    "Question_votes": "provisorio",
    "Remote_votes": "outro",
}
"""Colunas da fonte com os votos por tipo."""


@dataclass(frozen=True, slots=True)
class ConectorAK:
    estado: CodigoEstado = CodigoEstado.AK
    nome_fonte: str = "Alaska Division of Elections, Election Results"
    licenca: str | None = "Registo público (AS 40.25.110)"
    eleicoes: dict[date, str] = field(
        default_factory=lambda: {
            date(2024, 11, 5): "https://www.elections.alaska.gov/results/24GENR/ENRbyPrecinct.csv",
            date(2026, 11, 3): (
                "https://www.elections.alaska.gov/enr26/results/GA_ENR_Precinct_State_of_Alaska.csv"
            ),
        }
    )

    def pedidos(self, data: date, obter: ObterTexto) -> list[Pedido]:
        del obter
        url = self.eleicoes.get(data)
        if url is None:
            msg = f"AK: sem endereço de resultados conhecido para {data}"
            raise ErroDescarga(msg)
        return [Pedido(url, FICHEIRO)]

    def ler(self, pasta: Path, data: date) -> Leitura:
        del data
        caminho = pasta / FICHEIRO
        try:
            bruto = pl.read_csv(caminho, infer_schema_length=0, encoding="utf8-lossy")
        except (pl.exceptions.PolarsError, OSError) as erro:
            msg = f"{caminho.name}: não é um CSV legível"
            raise ErroFormatoFonte(msg) from erro
        em_falta = [c for c in (*CAMPOS, *MODALIDADES) if c not in bruto.columns]
        if em_falta:
            msg = f"{caminho.name}: faltam colunas {em_falta}"
            raise ErroFormatoFonte(msg)
        corridas = {
            t: d
            for t in bruto["Contest_title"].unique().to_list()
            if (d := identificar_corrida(self.estado, t)) is not None
        }
        if not corridas:
            msg = f"{caminho.name}: nenhuma corrida federal ou de governador"
            raise ErroFormatoFonte(msg)
        numeros = ["total_ballots", "total_votes", *MODALIDADES]
        try:
            tabela = bruto.filter(pl.col("Contest_title").is_in(list(corridas))).with_columns(
                pl.col(numeros).str.strip_chars().cast(pl.Int64),
                pl.col("Contest_title")
                .replace_strict({t: d.id for t, d in corridas.items()})
                .alias("corrida"),
                pl.col("candidate_name").str.strip_chars().alias("candidato"),
                pl.col("Party_Code").str.strip_chars().fill_null("").alias("rotulo"),
            )
        except pl.exceptions.PolarsError as erro:
            msg = f"{caminho.name}: números inválidos"
            raise ErroFormatoFonte(msg) from erro

        por_candidato = tabela.group_by("corrida", "candidato", "rotulo").agg(
            pl.col("total_votes").sum().alias("votos"),
            *(pl.col(c).sum().alias(m) for c, m in MODALIDADES.items()),
        )
        votos = [
            (r["corrida"], r["candidato"], r["candidato"], partido(r["rotulo"]),
             r["rotulo"] or None, "estado", None, r["votos"])
            for r in por_candidato.iter_rows(named=True)
        ]  # fmt: skip
        modalidades = [
            (r["corrida"], r["candidato"], "estado", None, m, r[m])
            for r in por_candidato.iter_rows(named=True)
            for m in MODALIDADES.values()
        ]
        seccoes = tabela.group_by("corrida", "Precinct_name").agg(
            ((pl.col("total_ballots").max() > 0) | (pl.col("Reporting_flag") == "1").any()).alias(
                "apurada"
            )
        )
        unidades = [
            (r["corrida"], "estado", None, r["reportadas"], r["totais"])
            for r in seccoes.group_by("corrida")
            .agg(pl.col("apurada").sum().alias("reportadas"), pl.len().alias("totais"))
            .iter_rows(named=True)
        ]
        return Leitura(
            corridas=tuple(corridas.values()),
            votos=pl.DataFrame(votos, schema=COLUNAS_VOTOS, orient="row"),
            unidades=pl.DataFrame(unidades, schema=COLUNAS_UNIDADES, orient="row"),
            tipo_unidade="seccao",
            modalidades=pl.DataFrame(modalidades, schema=COLUNAS_MODALIDADES, orient="row"),
        )
