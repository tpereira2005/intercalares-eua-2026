"""Fontes do Colorado: folhas diárias "Election Activity" do Secretary of State.

Durante a eleição geral, o Secretary of State publica todos os dias úteis um comunicado
com os boletins devolvidos até às 23h59 do dia anterior, com duas versões dos mesmos
números: um resumo gráfico em PDF e uma folha de cálculo (XLSX) com as tabelas por
condado, partido de registo, género e faixa etária, separadas entre correio e presencial.
Lemos a folha de cálculo, que tem as tabelas inteiras; o PDF só tem gráficos.

O nome da folha segue a data dos dados, mas não sempre da mesma maneira
(``20241022GeneralElectionActivity.xlsx``, ``20241028ElectionActivity.xlsx`` e, no dia da
eleição, ``20241105GeneralElectionActivity9AM.xlsx``). Por isso:

* em 2026, seguimos os comunicados listados na página de imprensa e lemos o endereço da
  folha em cada um;
* para 2022 e 2024 (referências), experimentamos as variantes conhecidas em cada dia.
"""

import re
from datetime import date, timedelta
from html.parser import HTMLParser
from urllib.parse import urljoin

NOME_FONTE = "Colorado Secretary of State, Ballot Return Reporting"
LICENCA = "Registo público (Colorado Open Records Act)"

BASE = "https://www.coloradosos.gov/pubs/newsRoom/pressReleases/"
INDICE = BASE + "index.html"

VARIANTES = ("GeneralElectionActivity", "ElectionActivity", "GeneralElectionActivity9AM")
"""Nomes das folhas nas eleições gerais de 2022 e 2024, depois da data (AAAAMMDD)."""

_FOLHA = re.compile(r"^(\d{8})[A-Za-z0-9]*Activity[A-Za-z0-9]*\.xlsx$")
_COMUNICADO = re.compile(r"PR(\d{8})[A-Za-z0-9]*Ballot[A-Za-z0-9]*\.html$")


def candidatos(dia: date) -> list[str]:
    """Endereços possíveis da folha com os dados até ``dia`` (anos de referência)."""
    d = dia.strftime("%Y%m%d")
    return [f"{BASE}{dia.year}/{d}{v}.xlsx" for v in VARIANTES]


def data_da_folha(url: str) -> date | None:
    """Data dos dados, lida do nome da folha (``None`` se não for uma folha diária)."""
    m = _FOLHA.match(url.rsplit("/", 1)[-1])
    if m is None:
        return None
    d = m.group(1)
    return date(int(d[:4]), int(d[4:6]), int(d[6:]))


class _Ligacoes(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.hrefs: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "a":
            self.hrefs += [v for k, v in attrs if k == "href" and v]


def _ligacoes(html: str, base: str) -> list[str]:
    leitor = _Ligacoes()
    leitor.feed(html)
    return [urljoin(base, h) for h in leitor.hrefs]


def comunicados(html: str, eleicao: date) -> list[str]:
    """Comunicados de boletins devolvidos da eleição geral, na página de imprensa.

    Só os publicados entre 40 dias antes e o dia a seguir à eleição, para deixar de fora
    as primárias do mesmo ano.
    """
    inicio, fim = eleicao - timedelta(days=40), eleicao + timedelta(days=1)
    vistos: dict[str, None] = {}
    for url in _ligacoes(html, INDICE):
        m = _COMUNICADO.search(url)
        if m is None:
            continue
        d = m.group(1)
        if inicio <= date(int(d[:4]), int(d[4:6]), int(d[6:])) <= fim:
            vistos[url] = None
    return sorted(vistos)


def folha_do_comunicado(html: str, url_comunicado: str) -> str | None:
    """Endereço da folha diária ligada a um comunicado (``None`` se não tiver)."""
    for url in _ligacoes(html, url_comunicado):
        nome = url.rsplit("/", 1)[-1]
        if data_da_folha(url) is not None and "primary" not in nome.lower():
            return url
    return None
