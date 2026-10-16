"""Ensaio da noite eleitoral de ponta a ponta, com falhas injetadas num espelho local.

Uso::

    uv run python -m pipeline.jobs.ensaio_noite --estados NC,FL,GA,AK,TX --data 2024-11-05 \\
        --duracao 300 --intervalo 5 --relatorio /tmp/ensaio-noite-2024.md

Com ``--publicar ETIQUETA`` cada ciclo envia os ficheiros alterados para essa Release (com
``gh release upload --clobber``, como a recolha de produção); ``resultados-2026`` é recusada.

Ao contrário de ``ensaio_resultados`` (que reconstrói retratos em memória) e dos testes de
``test_robustez_noite`` (que simulam o HTTP com ``MockTransport``), aqui corre o ciclo REAL de
``pipeline.jobs.resultados`` (``Recolha`` + ``executar``, com o cliente ``httpx`` verdadeiro,
pedidos condicionais, repetições e tempos limite) contra um servidor HTTP local, o espelho, que:

* serve os ficheiros finais da fonte (2022 ou 2024) guardados em
  ``data/brutos/ensaio-noite/<anfitrião>/<caminho>``, com ETag e Last-Modified;
* se porta mal segundo um calendário (``Falha``): 404, 500/503, 429, corpo truncado, corpo
  vazio, resposta lenta e desafio anti-robô;
* muda o conteúdo servido em instantes marcados (``Alteracao``), para medir a latência entre
  a alteração na fonte e o momento em que ``parciais.json`` a reflete. Cada anfitrião começa
  com uma versão reduzida dos seus ficheiros (as primeiras linhas, ou os primeiros itens de
  uma lista JSON) e cresce até ao ficheiro final a cada alteração;
* com ``--manual``, serve também um ``manual.json`` que cresce como o de quem introduz os
  totais à mão (``MANUAIS``: Senado da Pensilvânia e, com o Texas, o do Texas, sobreposto a
  Harris). Essas corridas ficam fora da medição da latência dos estados.

Depois de cada ciclo, o observador verifica os invariantes (ver ``INVARIANTES``) e regista as
durações. O relatório em Markdown diz o que passou e o que falhou; o código de saída é 1 se
algum invariante falhar. Nada na produção é alterado para o ensaio passar: um invariante que
falha é um problema real a registar.
"""

import argparse
import hashlib
import json
import logging
import math
import shutil
import statistics
import sys
import tempfile
import threading
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from email.utils import formatdate
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Literal, cast
from urllib.parse import unquote, urlsplit

import httpx
from pydantic import ValidationError

from contratos.base import Fonte
from contratos.estados import CodigoEstado
from contratos.resultados import (
    ResultadosEstado,
    ResultadosNacional,
    ResultadosParciais,
)
from contratos.saude import SaudeRecolha
from pipeline.comum.descarga import USER_AGENT, contexto_tls, descarregar, obter_texto
from pipeline.comum.erros import ErroPipeline
from pipeline.connectors.results.comum import ConectorResultados
from pipeline.connectors.results.manual import FicheiroManual
from pipeline.connectors.results.registo import CONECTORES
from pipeline.jobs import resultado_manual, vigia
from pipeline.jobs.resultados import (
    FALHAS_ALERTA,
    NACIONAL,
    ORCAMENTO_CICLO,
    PARCIAIS,
    SAUDE,
    EstadoRecolha,
    Recolha,
    chave_recolha,
)
from pipeline.jobs.resultados import executar as executar_recolha
from pipeline.transform.resultados import ensaio
from pipeline.transform.resultados.parciais import montar_parciais

registo = logging.getLogger(__name__)

TipoFalha = Literal[
    "ausente", "erro_servidor", "limite", "corrompido", "vazio", "lento", "bloqueio"
]
TIPOS: tuple[TipoFalha, ...] = (
    "ausente",
    "erro_servidor",
    "limite",
    "corrompido",
    "vazio",
    "lento",
    "bloqueio",
)

RAIZ_PADRAO = Path("data/brutos/ensaio-noite")
ESTADOS_PADRAO = "NC,FL,GA,AK,TX"
SONDAGEM_S = 0.05
"""Intervalo com que o vigilante lê ``parciais.json`` para medir a latência."""

MARGEM_LATENCIA = 2.0
"""A latência aceitável é ``MARGEM_LATENCIA`` intervalos: a alteração espera, no máximo, o
fim do ciclo em curso mais um ciclo."""

INVARIANTES: dict[str, str] = {
    "ciclo_nao_falha": "O ciclo nunca rebenta e o ensaio corre até ao fim",
    "saudaveis_atualizam": "Um estado sem falha injetada tem sucesso em todos os ciclos",
    "ultimo_valido_preservado": "Um estado em falha mantém o seu último <uf>.json, byte a byte",
    "nada_invalido": "Todos os ficheiros escritos validam contra os contratos",
    "sem_regressao": "Nenhum total publicado desce entre ciclos (dados truncados nunca saem)",
    "falha_persistente": "Uma falha que continua a ser servida não volta a contar como sucesso",
    "alertas": "O alerta sobe às FALHAS_ALERTA falhas seguidas e desaparece na recuperação",
    "ciclo_dentro_do_intervalo": "Nenhum ciclo dura mais do que o intervalo",
    "lento_isolado": "Uma fonte lenta não atrasa os outros estados do mesmo ciclo",
    "latencia": "Cada alteração da fonte chega a parciais.json em tempo útil",
    "falhas_exercitadas": "Cada falha do calendário chegou a ser servida",
    "manual": "Cada entrada manual chega aos parciais com o selo, sem corridas duplicadas",
}

URL_MANUAL = (
    "https://github.com/tpereira2005/intercalares-eua-2026/releases/download/"
    "resultados-2026/manual.json"
)
ANFITRIAO_MANUAL = urlsplit(URL_MANUAL).netloc
MANUAIS: dict[str, tuple[str, str]] = {
    "PA-S": ("Bob Casey (D): {d}; Dave McCormick (R): {r}", "3384180:3399295"),
    "TX-S": ("Colin Allred (D): {d}; Ted Cruz (R): {r}", "5031249:5990741"),
}
"""Corridas introduzidas à mão no ensaio, com os totais finais de 2024 (D:R)."""

FRACOES_MANUAIS: tuple[float, ...] = (0.15, 0.35, 0.55, 0.75)
"""Instantes (frações da duração) das entradas manuais; cada uma traz mais votos."""


class ErroEnsaio(ErroPipeline):
    """Problema na preparação do ensaio (não da recolha)."""


@dataclass(frozen=True, slots=True)
class Falha:
    anfitriao: str
    inicio_s: float
    fim_s: float
    tipo: TipoFalha


@dataclass(frozen=True, slots=True)
class Alteracao:
    anfitriao: str
    instante_s: float


@dataclass(frozen=True, slots=True)
class Plano:
    falhas: tuple[Falha, ...]
    alteracoes: tuple[Alteracao, ...]

    def falhas_de(self, anfitriao: str) -> list[Falha]:
        return [f for f in self.falhas if f.anfitriao == anfitriao]

    def alteracoes_de(self, anfitriao: str) -> list[Alteracao]:
        return sorted(
            (a for a in self.alteracoes if a.anfitriao == anfitriao), key=lambda a: a.instante_s
        )


# --- Calendário por omissão ----------------------------------------------------------------

CALENDARIO: tuple[tuple[TipoFalha, float, float], ...] = (
    ("ausente", 0.07, 0.25),
    ("erro_servidor", 0.13, 0.18),
    ("limite", 0.30, 0.37),
    ("corrompido", 0.40, 0.47),
    ("vazio", 0.50, 0.56),
    ("lento", 0.60, 0.67),
    ("bloqueio", 0.72, 0.80),
)
"""Tipo, início e fim, como frações da duração. As falhas rodam pelos estados que não são o
estado sempre saudável, e sobrepõem-se no tempo."""

INSTANTES_ALTERACAO: tuple[float, ...] = (0.05, 0.30, 0.45, 0.58, 0.70, 0.82)
LIMITE_ALTERACAO = 0.82
"""Fração da duração depois da qual não há alterações (deixa tempo para a medir)."""


def plano_padrao(
    anfitrioes: dict[str, str], duracao: float, intervalo: float, saudavel: str | None = None
) -> Plano:
    """Calendário que exercita todos os tipos de falha em estados e instantes diferentes.

    ``anfitrioes`` mapeia o código do estado para o anfitrião da sua fonte. O estado sempre
    saudável (``saudavel``, por omissão FL se existir, senão o primeiro) nunca recebe
    falhas; tem duas alterações. Cada um dos outros recebe uma alteração, num instante que
    não cai numa das suas falhas.
    """
    ufs = list(anfitrioes)
    if saudavel is None:
        saudavel = "FL" if "FL" in ufs else ufs[0]
    outros = [anfitrioes[u] for u in ufs if u != saudavel]
    if not outros:
        return Plano((), ())
    falhas: list[Falha] = []
    for i, (tipo, ini, fim) in enumerate(CALENDARIO):
        inicio_s, fim_s = ini * duracao, fim * duracao
        if tipo == "ausente":  # tem de durar o suficiente para disparar o alerta
            fim_s = max(fim_s, inicio_s + (FALHAS_ALERTA + 2) * intervalo)
        falhas.append(Falha(outros[i % len(outros)], round(inicio_s, 2), round(fim_s, 2), tipo))
    alteracoes: list[Alteracao] = [
        Alteracao(anfitrioes[saudavel], round(0.33 * duracao, 2)),
        Alteracao(anfitrioes[saudavel], round(0.62 * duracao, 2)),
    ]
    for anfitriao in outros:
        proprias = [f for f in falhas if f.anfitriao == anfitriao]
        for fracao in INSTANTES_ALTERACAO:
            t = fracao * duracao
            livre = all(
                not (f.inicio_s - 2 * intervalo <= t <= f.fim_s + 2 * intervalo) for f in proprias
            )
            if livre and fracao <= LIMITE_ALTERACAO:
                alteracoes.append(Alteracao(anfitriao, round(t, 2)))
                break
    return Plano(tuple(falhas), tuple(alteracoes))


# --- Ficheiros do espelho ------------------------------------------------------------------


def caminho_espelho(raiz: Path, url: str) -> Path:
    """Onde fica, no espelho, o ficheiro de ``url`` (``<raiz>/<anfitrião>/<caminho>``)."""
    partes = urlsplit(url)
    return raiz / partes.netloc / partes.path.lstrip("/")


def reduzir(nome: str, conteudo: bytes, fracao: float) -> bytes:
    """Versão válida e menor do ficheiro: as primeiras ``fracao`` das linhas (cabeçalho
    incluído), ou dos itens da maior lista de um JSON."""
    if conteudo.lstrip(b"\xef\xbb\xbf \r\n\t")[:1] in (b"{", b"["):  # JSON, mesmo em .txt (NC)
        dados = json.loads(conteudo.decode("utf-8-sig"))
        if isinstance(dados, list):
            return json.dumps(dados[: max(1, int(len(dados) * fracao))]).encode("utf-8")
        if isinstance(dados, dict):
            listas = [k for k, v in dados.items() if isinstance(v, list) and v]
            if listas:
                chave = max(listas, key=lambda k: len(dados[k]))
                dados[chave] = dados[chave][: max(1, int(len(dados[chave]) * fracao))]
            return json.dumps(dados, ensure_ascii=False).encode("utf-8")
        return conteudo
    linhas = conteudo.splitlines(keepends=True)
    if len(linhas) <= 2:
        return conteudo
    return b"".join(linhas[: 1 + max(1, int((len(linhas) - 1) * fracao))])


def marcas_parciais(
    parciais: ResultadosParciais, ignorar: frozenset[str] = frozenset()
) -> dict[str, str]:
    """Impressão digital das unidades de ``parciais`` por estado: muda sempre que muda um voto.
    As corridas em ``ignorar`` (as manuais do ensaio) ficam de fora."""
    grupos: dict[str, list[tuple[object, ...]]] = {}
    for u in parciais.unidades:
        if u.corrida in ignorar:
            continue
        grupos.setdefault(u.corrida[:2], []).append(
            (u.corrida, u.unidade, u.votos_d, u.votos_r, u.votos_outros)
        )
    return {
        uf: hashlib.sha1(repr(sorted(g)).encode(), usedforsecurity=False).hexdigest()[:12]
        for uf, g in grupos.items()
    }


@dataclass
class Versoes:
    """Versões dos ficheiros de um estado, da mais pequena à final."""

    ficheiros: dict[str, list[bytes]]
    """Caminho no espelho (``anfitrião/caminho``) -> versões."""

    marcas: list[str]
    """Impressão digital esperada em ``parciais.json`` para este estado, em cada versão."""


def _marca_versao(
    conector: ConectorResultados,
    data: date,
    ficheiros: dict[str, bytes],
    fonte: Fonte,
    ignorar: frozenset[str] = frozenset(),
) -> str:
    with tempfile.TemporaryDirectory() as tmp:
        for nome, conteudo in ficheiros.items():
            destino = Path(tmp) / nome
            destino.parent.mkdir(parents=True, exist_ok=True)
            destino.write_bytes(conteudo)
        try:
            leitura = conector.ler(Path(tmp), data)
        except Exception as erro:
            msg = f"{conector.estado.value}: versão do espelho ilegível: {erro}"
            raise ErroEnsaio(msg) from erro
    parciais = montar_parciais([leitura], ano=data.year, instante=datetime.now(UTC), fontes=[fonte])
    return marcas_parciais(parciais, ignorar).get(conector.estado.value, "")


def construir_versoes(
    conector: ConectorResultados,
    data: date,
    raiz: Path,
    n_alteracoes: int,
    obter: Callable[[str], str],
    *,
    ignorar: frozenset[str] = frozenset(),
) -> Versoes:
    """``n_alteracoes`` versões reduzidas, cada uma legível e com resultados diferentes da
    seguinte (a fração baixa até a leitura mudar), mais o ficheiro final."""
    pedidos = conector.pedidos(data, obter)
    originais = {p.ficheiro: caminho_espelho(raiz, p.url).read_bytes() for p in pedidos}
    fonte = Fonte(
        nome=conector.nome_fonte,
        url=pedidos[0].url,
        licenca=conector.licenca,
        obtida_em=datetime.now(UTC),
    )
    posterior = _marca_versao(conector, data, originais, fonte, ignorar)
    marcas = [""] * n_alteracoes + [posterior]
    reduzidas: list[dict[str, bytes]] = [{} for _ in range(n_alteracoes)]
    limite = 1.0
    for k in reversed(range(n_alteracoes)):
        fracao = min((k + 1) / (n_alteracoes + 1), limite * 0.99)
        while True:
            candidata = {f: reduzir(f, b, fracao) for f, b in originais.items()}
            try:
                marca = _marca_versao(conector, data, candidata, fonte, ignorar)
            except ErroEnsaio:
                marca = posterior
            if marca != posterior:
                break
            fracao *= 0.8
            if fracao < 0.01:
                msg = f"{conector.estado.value}: não consegui uma versão reduzida distinta"
                raise ErroEnsaio(msg)
        reduzidas[k], marcas[k], posterior, limite = candidata, marca, marca, fracao
    versoes = [*reduzidas, originais]
    ficheiros = {
        f"{urlsplit(p.url).netloc}/{urlsplit(p.url).path.lstrip('/')}": [
            v[p.ficheiro] for v in versoes
        ]
        for p in pedidos
    }
    return Versoes(ficheiros, marcas)


def versoes_manuais(estados: Sequence[CodigoEstado], data: date) -> list[bytes]:
    """``manual.json`` vazio e depois uma versão por ``FRACOES_MANUAIS``, como o escreveria o
    workflow **Resultado manual**: cada entrada com mais votos e mais apuramento."""
    corridas = [c for c in MANUAIS if c == "PA-S" or CodigoEstado(c[:2]) in estados]
    ficheiro = FicheiroManual()
    versoes = [ficheiro.model_dump_json().encode()]
    for k in range(1, len(FRACOES_MANUAIS) + 1):
        progresso = k / len(FRACOES_MANUAIS)
        for corrida in corridas:
            modelo, finais = MANUAIS[corrida]
            d, r = (round(int(v) * progresso) for v in finais.split(":"))
            ficheiro, _ = resultado_manual.atualizar(
                ficheiro,
                corrida,
                texto_candidatos=modelo.format(d=d, r=r),
                texto_apuramento=f"{round(progresso * 99)}%",
                fonte="https://www.electionreturns.pa.gov/",
                apagar=False,
                agora=datetime.combine(data, datetime.min.time(), UTC),
            )
        versoes.append(ficheiro.model_dump_json().encode())
    return versoes


def preparar_espelho(
    raiz: Path, conectores: list[ConectorResultados], data: date, *, descarga: bool
) -> None:
    """Descarrega uma vez os ficheiros finais de cada estado para o espelho (se não existirem)."""
    cliente = httpx.Client(
        timeout=httpx.Timeout(60.0, read=300.0),
        follow_redirects=True,
        headers={"User-Agent": USER_AGENT},
        verify=contexto_tls(),
    )
    with cliente:

        def obter(url: str) -> str:
            return obter_texto(cliente, url)

        for conector in conectores:
            for p in conector.pedidos(data, obter):
                destino = caminho_espelho(raiz, p.url)
                if destino.exists() and destino.stat().st_size > 0:
                    continue
                if not descarga:
                    msg = f"{conector.estado.value}: falta {destino} (usa sem --sem-descarga)"
                    raise ErroEnsaio(msg)
                registo.info("A descarregar %s", p.url)
                descarregar(p.url, destino, cliente=cliente)


# --- Servidor espelho ----------------------------------------------------------------------


@dataclass
class Mudanca:
    alteracao: Alteracao
    epoca: float
    """Hora (``time.time()``) a que o servidor passou a servir a versão nova."""

    versao: int


@dataclass
class PedidoServido:
    t: float
    anfitriao: str
    caminho: str
    estado: int
    falha: TipoFalha | None


class _Servidor(ThreadingHTTPServer):
    daemon_threads = True
    espelho: "Espelho"


class _Manipulador(BaseHTTPRequestHandler):
    def log_message(self, format: str, *args: object) -> None:  # noqa: A002
        del format, args

    def _espelho(self) -> "Espelho":
        return cast(_Servidor, self.server).espelho

    def _responder(
        self, estado: int, corpo: bytes = b"", cabecalhos: dict[str, str] | None = None
    ) -> None:
        try:
            self.send_response(estado)
            for chave, valor in (cabecalhos or {}).items():
                self.send_header(chave, valor)
            self.send_header("Content-Length", str(len(corpo)))
            self.end_headers()
            if corpo and self.command != "HEAD":
                self.wfile.write(corpo)
        except OSError:  # o cliente desistiu (tempo limite)
            pass

    def do_GET(self) -> None:
        espelho = self._espelho()
        caminho = unquote(urlsplit(self.path).path).lstrip("/")
        anfitriao, _, resto = caminho.partition("/")
        falha = espelho.falha_ativa(anfitriao)
        estado = self._servir(espelho, anfitriao, resto, falha)
        espelho.registar(anfitriao, resto, estado, falha)

    def _servir(  # noqa: PLR0911
        self, espelho: "Espelho", anfitriao: str, resto: str, falha: TipoFalha | None
    ) -> int:
        match falha:
            case "ausente":
                self._responder(404, b"Not Found")
                return 404
            case "erro_servidor":
                estado = 503 if espelho.proximo() % 2 else 500
                self._responder(estado, b"Server Error")
                return estado
            case "limite":
                self._responder(
                    429, b"Too Many Requests", {"Retry-After": str(espelho.retry_after)}
                )
                return 429
            case "bloqueio":
                self._responder(202, b"", {"x-amzn-waf-action": "challenge"})
                return 202
            case "lento":
                espelho.parar.wait(espelho.lento_s)
                falha = None  # depois da demora, responde normalmente (o cliente já desistiu)
            case _:
                pass
        conteudo = espelho.conteudo(anfitriao, resto)
        if conteudo is None:
            self._responder(404, b"Not Found")
            return 404
        corpo, modificado = conteudo
        cabecalhos = {"Content-Type": "application/octet-stream"}
        if falha == "vazio":
            self._responder(200, b"", cabecalhos)
            return 200
        if falha == "corrompido":
            corpo = corpo[: len(corpo) // 2]
        etag = '"' + hashlib.sha1(corpo, usedforsecurity=False).hexdigest()[:16] + '"'
        cabecalhos |= {"ETag": etag, "Last-Modified": formatdate(modificado, usegmt=True)}
        if self.headers.get("If-None-Match") == etag:
            self._responder(304, b"", cabecalhos)
            return 304
        desde = self.headers.get("If-Modified-Since")
        sem_etag = "If-None-Match" not in self.headers
        if desde is not None and sem_etag and desde == cabecalhos["Last-Modified"]:
            self._responder(304, b"", cabecalhos)
            return 304
        self._responder(200, corpo, cabecalhos)
        return 200


class Espelho:
    """Servidor HTTP local que serve ``raiz`` e aplica o calendário de falhas e alterações."""

    def __init__(
        self,
        raiz: Path,
        plano: Plano,
        versoes: dict[str, Versoes] | None = None,
        *,
        anfitrioes_estado: dict[str, str] | None = None,
        lento_s: float = 22.0,
        retry_after: int = 5,
    ) -> None:
        self.raiz = raiz.resolve()
        self.plano = plano
        self.lento_s = lento_s
        self.retry_after = retry_after
        self.parar = threading.Event()
        self.t0: float | None = None
        self.epoca0: float = 0.0
        self.mudancas: list[Mudanca] = []
        self.pedidos: list[PedidoServido] = []
        self._trinco = threading.Lock()
        self._contador = 0
        self._versao: dict[str, int] = {}
        self._versoes: dict[str, list[bytes]] = {}
        for v in (versoes or {}).values():
            self._versoes.update(v.ficheiros)
        self._servidor = _Servidor(("127.0.0.1", 0), _Manipulador)
        self._servidor.espelho = self
        self._fios: list[threading.Thread] = []
        del anfitrioes_estado

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self._servidor.server_address[1]}"

    def arrancar(self) -> None:
        fio = threading.Thread(target=self._servidor.serve_forever, daemon=True, name="espelho")
        fio.start()
        self._fios.append(fio)

    def iniciar_relogio(self) -> None:
        """Marca o instante zero do calendário e arranca as alterações."""
        self.t0 = time.monotonic()
        self.epoca0 = time.time()
        fio = threading.Thread(target=self._alterar, daemon=True, name="alteracoes")
        fio.start()
        self._fios.append(fio)

    def terminar(self) -> None:
        self.parar.set()
        self._servidor.shutdown()
        self._servidor.server_close()

    def agora(self) -> float:
        return 0.0 if self.t0 is None else time.monotonic() - self.t0

    def _alterar(self) -> None:
        for alteracao in sorted(self.plano.alteracoes, key=lambda a: a.instante_s):
            if self.parar.wait(max(0.0, alteracao.instante_s - self.agora())):
                return
            with self._trinco:
                versao = self._versao.get(alteracao.anfitriao, 0) + 1
                self._versao[alteracao.anfitriao] = versao
                self.mudancas.append(Mudanca(alteracao, time.time(), versao))

    def falha_ativa(self, anfitriao: str, t: float | None = None) -> TipoFalha | None:
        if self.t0 is None:
            return None
        instante = self.agora() if t is None else t
        for f in self.plano.falhas:
            if f.anfitriao == anfitriao and f.inicio_s <= instante < f.fim_s:
                return f.tipo
        return None

    def falhas_entre(self, anfitriao: str, inicio_s: float, fim_s: float) -> list[TipoFalha]:
        """Falhas do anfitrião cuja janela cruza ``[inicio_s, fim_s]``."""
        return [
            f.tipo
            for f in self.plano.falhas
            if f.anfitriao == anfitriao and f.inicio_s <= fim_s and inicio_s < f.fim_s
        ]

    def falha_cobre(self, anfitriao: str, inicio_s: float, fim_s: float) -> bool:
        """``True`` se uma única falha do anfitrião cobre todo o intervalo."""
        return any(
            f.anfitriao == anfitriao and f.inicio_s <= inicio_s and fim_s < f.fim_s
            for f in self.plano.falhas
        )

    def proximo(self) -> int:
        with self._trinco:
            self._contador += 1
            return self._contador

    def registar(self, anfitriao: str, caminho: str, estado: int, falha: TipoFalha | None) -> None:
        with self._trinco:
            self.pedidos.append(PedidoServido(self.agora(), anfitriao, caminho, estado, falha))

    def conteudo(self, anfitriao: str, resto: str) -> tuple[bytes, float] | None:
        """Corpo e hora de modificação da versão atual do ficheiro, ou ``None`` se não existe."""
        chave = f"{anfitriao}/{resto}"
        versoes = self._versoes.get(chave)
        if versoes is not None:
            indice = min(self._versao.get(anfitriao, 0), len(versoes) - 1)
            return versoes[indice], math.floor(self.epoca0 or 0) + indice
        caminho = (self.raiz / anfitriao / resto).resolve()
        if not caminho.is_relative_to(self.raiz) or not caminho.is_file():
            return None
        return caminho.read_bytes(), caminho.stat().st_mtime


# --- Observação ----------------------------------------------------------------------------


@dataclass
class RegistoEstado:
    uf: str
    inicio_s: float
    """Início do estado dentro do ciclo (segundos desde o início do ciclo)."""

    gasto: float
    t_inicio: float
    """Relógio do espelho no início e no fim do estado, para cruzar com as falhas."""

    t_fim: float
    falhou: bool = False
    erro: str | None = None
    falhas_seguidas: int = 0
    alerta: str | None = None
    afetado_por: list[TipoFalha] = field(default_factory=list)


@dataclass
class Ciclo:
    indice: int
    inicio_s: float
    """Relógio do espelho no início do ciclo."""

    duracao: float = 0.0
    estados: dict[str, RegistoEstado] = field(default_factory=dict)


@dataclass
class Invariante:
    id: str
    descricao: str
    problemas: list[str]

    @property
    def ok(self) -> bool:
        return not self.problemas


@dataclass
class Latencia:
    anfitriao: str
    uf: str
    instante_s: float
    versao: int
    epoca: float
    escrita_s: float | None
    """Segundos entre a alteração na fonte e o ``parciais.json`` que a reflete."""

    publicavel_s: float | None
    """Segundos até ao fim do ciclo em que isso aconteceu (momento do envio da Release)."""

    nota: str = ""


def percentil(valores: list[float], p: float) -> float:
    if not valores:
        return 0.0
    ordenados = sorted(valores)
    return ordenados[max(0, math.ceil(p * len(ordenados)) - 1)]


class Observador:
    """Regista os ciclos e verifica os invariantes no fim de cada um."""

    def __init__(
        self,
        espelho: Espelho,
        saida: Path,
        data: date,
        anfitrioes: dict[str, str],
        intervalo: float,
    ) -> None:
        self.espelho = espelho
        self.saida = saida
        self.data = data
        self.anfitrioes = anfitrioes
        self.intervalo = intervalo
        self.ciclos: list[Ciclo] = []
        self.violacoes: dict[str, list[str]] = {k: [] for k in INVARIANTES}
        self.erros_ensaio: list[str] = []
        self._atual: Ciclo | None = None
        self._bytes: dict[str, bytes] = {}
        self._validados: dict[str, str] = {}
        self._anteriores: dict[str, ResultadosEstado] = {}
        self._ultimo_reg: dict[str, RegistoEstado] = {}
        self.alerta_visto: set[str] = set()
        self.alerta_limpo: set[str] = set()
        self.max_falhas: dict[str, int] = {}
        self.fim_ciclos: list[float] = []
        """Hora (``time.time()``) do fim de cada ciclo."""

        self.manuais_vistos: set[int] = set()
        self.vistos_manuais: set[str] = set()
        """Corridas que já apareceram em ``corridas_manuais``."""
        """Votos democratas de PA-S vistos em ``parciais.json`` (um por entrada manual)."""

    def ciclo_inicio(self) -> None:
        self._atual = Ciclo(len(self.ciclos), self.espelho.agora())
        self._inicio_mono = time.monotonic()

    def estado_feito(self, uf: str, t_inicio: float, t_fim: float) -> None:
        if self._atual is None:
            return
        self._atual.estados[uf] = RegistoEstado(
            uf, t_inicio - self._atual.inicio_s, t_fim - t_inicio, t_inicio, t_fim
        )

    def ciclo_fim(self, recolha: Recolha, agora: datetime) -> None:
        ciclo = self._atual
        if ciclo is None:
            return
        ciclo.duracao = time.monotonic() - self._inicio_mono
        self.fim_ciclos.append(time.time())
        self.ciclos.append(ciclo)
        try:
            self._verificar(recolha, ciclo, agora)
        except Exception as erro:  # defeito do ensaio, não da recolha
            self.erros_ensaio.append(f"ciclo {ciclo.indice}: {type(erro).__name__}: {erro}")
            registo.exception("Erro do observador")

    # -- verificações por ciclo --

    def _verificar(self, recolha: Recolha, ciclo: Ciclo, agora: datetime) -> None:
        n = ciclo.indice
        saude = json.loads((self.saida / SAUDE).read_text(encoding="utf-8"))
        alertas_vigia = "\n".join(vigia.alertas(saude, agora, vigia.MAXIMO_MINUTOS))
        for uf, estado in recolha.estados.items():
            reg = ciclo.estados.get(uf.value)
            anfitriao = self.anfitrioes.get(uf.value, ANFITRIAO_MANUAL)
            if reg is None:
                # Um estado ainda em curso (fonte lenta) ou em pausa por um Retry-After não
                # entra neste ciclo; os outros seguem sem ele.
                if uf not in recolha.em_curso() and estado.nao_antes is None:
                    self.violacoes["ciclo_nao_falha"].append(
                        f"ciclo {n}: {uf.value} não foi processado"
                    )
                continue
            reg.falhou = estado.falhas_seguidas > 0
            reg.erro = estado.ultimo_erro
            reg.falhas_seguidas = estado.falhas_seguidas
            reg.alerta = estado.alerta(agora)
            reg.afetado_por = self.espelho.falhas_entre(
                anfitriao, reg.t_inicio, reg.t_inicio + reg.gasto
            )
            self.max_falhas[uf.value] = max(self.max_falhas.get(uf.value, 0), reg.falhas_seguidas)
            self._saudaveis(n, reg)
            self._persistente(n, reg)
            self._preservado(n, reg)
            self._alertas(n, reg, alertas_vigia)
        self._ficheiros(n, ciclo)
        self._manuais(n)

    def _manuais(self, n: int) -> None:
        """Corridas únicas no resumo; as manuais com o selo e só a unidade ``total``."""
        v = self.violacoes["manual"]
        if (self.saida / NACIONAL).exists():
            resumo = ResultadosNacional.model_validate_json((self.saida / NACIONAL).read_bytes())
            ids = [c.id for c in resumo.corridas]
            for repetida in sorted({i for i in ids if ids.count(i) > 1}):
                v.append(f"ciclo {n}: {repetida} repetida em {NACIONAL}")
            for c in resumo.corridas:
                if c.manual and c.id not in MANUAIS:
                    v.append(f"ciclo {n}: {c.id} com o selo manual sem entrada manual")
                elif c.id in self.vistos_manuais and not c.manual:
                    v.append(f"ciclo {n}: {c.id} sem o selo manual em {NACIONAL}")
        if not (self.saida / PARCIAIS).exists():
            return
        parciais = ResultadosParciais.model_validate_json((self.saida / PARCIAIS).read_bytes())
        for corrida in parciais.corridas_manuais:
            self.vistos_manuais.add(corrida)
            if corrida not in MANUAIS:
                v.append(f"ciclo {n}: {corrida} marcada como manual sem entrada manual")
        for u in parciais.unidades:
            if u.corrida == "PA-S":
                self.manuais_vistos.add(u.votos_d)

    def _saudaveis(self, n: int, reg: RegistoEstado) -> None:
        if reg.falhou and not reg.afetado_por:
            self.violacoes["saudaveis_atualizam"].append(
                f"ciclo {n}: {reg.uf} falhou sem falha injetada ({reg.erro})"
            )

    def _persistente(self, n: int, reg: RegistoEstado) -> None:
        """Se o ciclo anterior falhou e a mesma falha continuou a ser servida durante os dois
        ciclos, este não pode contar como sucesso (a fonte não melhorou)."""
        anterior = self._ultimo_reg.get(reg.uf)
        self._ultimo_reg[reg.uf] = reg
        if anterior is None or not anterior.falhou or reg.falhou:
            return
        host = self.anfitrioes[reg.uf]
        if self.espelho.falha_cobre(host, anterior.t_inicio, reg.t_inicio + reg.gasto):
            self.violacoes["falha_persistente"].append(
                f"ciclo {n}: {reg.uf} voltou a contar como sucesso com a falha ainda ativa "
                f"(a falha anterior era: {anterior.erro})"
            )

    def _preservado(self, n: int, reg: RegistoEstado) -> None:
        caminho = self.saida / f"{reg.uf.lower()}.json"
        agora = caminho.read_bytes() if caminho.exists() else None
        antes = self._bytes.get(reg.uf)
        if antes is not None and agora is None:
            self.violacoes["ultimo_valido_preservado"].append(
                f"ciclo {n}: {caminho.name} desapareceu"
            )
        elif reg.falhou and agora != antes:
            self.violacoes["ultimo_valido_preservado"].append(
                f"ciclo {n}: {reg.uf} falhou ({reg.erro}) e {caminho.name} mudou"
            )
        if agora is not None:
            self._bytes[reg.uf] = agora

    def _alertas(self, n: int, reg: RegistoEstado, alertas_vigia: str) -> None:
        v = self.violacoes["alertas"]
        if reg.falhas_seguidas >= FALHAS_ALERTA:
            if reg.alerta is None:
                v.append(f"ciclo {n}: {reg.uf} com {reg.falhas_seguidas} falhas e sem alerta")
            else:
                self.alerta_visto.add(reg.uf)
            if f"{reg.uf}:" not in alertas_vigia:
                v.append(f"ciclo {n}: o vigia não lista o alerta de {reg.uf}")
        elif reg.alerta is not None:
            v.append(
                f"ciclo {n}: {reg.uf} com alerta ({reg.alerta}) e só {reg.falhas_seguidas} falhas"
            )
        if reg.falhas_seguidas == 0 and reg.uf in self.alerta_visto:
            if reg.alerta is None:
                self.alerta_limpo.add(reg.uf)
            else:
                v.append(f"ciclo {n}: {reg.uf} recuperou mas o alerta continua")

    def _ficheiros(self, n: int, ciclo: Ciclo) -> None:
        for sobra in self.saida.rglob("*.parcial"):
            self.violacoes["nada_invalido"].append(f"ciclo {n}: ficheiro temporário {sobra.name}")
        for caminho in sorted(self.saida.glob("*.json")):
            texto = caminho.read_bytes()
            chave = hashlib.sha1(texto, usedforsecurity=False).hexdigest()
            if self._validados.get(caminho.name) == chave:
                continue
            self._validados[caminho.name] = chave
            try:
                modelo = self._validar(caminho.name, texto)
            except (ValidationError, ValueError) as erro:
                self.violacoes["nada_invalido"].append(
                    f"ciclo {n}: {caminho.name} inválido: {str(erro)[:150]}"
                )
                continue
            if isinstance(modelo, ResultadosEstado):
                anterior = self._anteriores.get(caminho.name)
                if anterior is not None:
                    for p in ensaio.verificar_sequencia([anterior, modelo]):
                        self.violacoes["sem_regressao"].append(
                            f"ciclo {n}: {caminho.name} {p.corrida}: {p.descricao}"
                        )
                self._anteriores[caminho.name] = modelo
        del ciclo

    def _validar(
        self, nome: str, texto: bytes
    ) -> ResultadosEstado | ResultadosNacional | ResultadosParciais | None:
        if nome == SAUDE:
            SaudeRecolha.model_validate_json(texto)
            return None
        if nome == NACIONAL:
            return ResultadosNacional.model_validate_json(texto)
        if nome == PARCIAIS:
            return ResultadosParciais.model_validate_json(texto)
        estado = ResultadosEstado.model_validate_json(texto)
        uf = estado.estado.value.lower()
        if nome not in (f"{uf}.json", f"{uf}-manual.json") or estado.data_eleicao != self.data:
            msg = f"{nome}: estado ou data errados ({estado.estado.value}, {estado.data_eleicao})"
            raise ValueError(msg)
        return estado


@dataclass
class RecolhaObservada(Recolha):
    """A recolha de produção, com ganchos de medição que não alteram o seu comportamento."""

    observador: Observador | None = None

    def ciclo(self, conectores: Sequence[ConectorResultados]) -> list[Path]:
        if self.observador:
            self.observador.ciclo_inicio()
        return super().ciclo(conectores)

    def _estado(self, conector: ConectorResultados, estado: EstadoRecolha) -> Path | None:
        obs = self.observador
        inicio = obs.espelho.agora() if obs else 0.0
        try:
            return super()._estado(conector, estado)
        finally:
            if obs:
                # A entrada manual sobreposta ao Texas regista-se à parte (TX-manual).
                obs.estado_feito(chave_recolha(conector).upper(), inicio, obs.espelho.agora())

    def escrever_saude(self) -> Path:
        caminho = super().escrever_saude()
        if self.observador:
            self.observador.ciclo_fim(self, datetime.now(UTC))
        return caminho


class Vigilante(threading.Thread):
    """Lê ``parciais.json`` de ``SONDAGEM_S`` em ``SONDAGEM_S`` segundos e guarda cada versão
    nova com a hora a que foi vista, para medir a latência das alterações."""

    def __init__(self, caminho: Path, ignorar: frozenset[str] = frozenset()) -> None:
        super().__init__(daemon=True, name="vigilante")
        self.caminho = caminho
        self.ignorar = ignorar
        self.parar = threading.Event()
        self.eventos: list[tuple[float, dict[str, str]]] = []

    def run(self) -> None:
        visto = ""
        while not self.parar.wait(SONDAGEM_S):
            try:
                texto = self.caminho.read_bytes()
            except OSError:
                continue
            chave = hashlib.sha1(texto, usedforsecurity=False).hexdigest()
            if chave == visto:
                continue
            visto = chave
            try:
                somas = marcas_parciais(ResultadosParciais.model_validate_json(texto), self.ignorar)
            except ValidationError:
                continue
            self.eventos.append((time.time(), somas))


# --- Relatório -----------------------------------------------------------------------------


@dataclass
class Relatorio:
    data: date
    estados: list[str]
    duracao: float
    intervalo: float
    plano: Plano
    anfitrioes: dict[str, str]
    ciclos: list[Ciclo]
    invariantes: list[Invariante]
    latencias: list[Latencia]
    pedidos: list[PedidoServido]
    erros_ensaio: list[str]
    max_falhas: dict[str, int]
    avisos: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return all(i.ok for i in self.invariantes) and not self.erros_ensaio

    def duracoes(self) -> list[float]:
        return [c.duracao for c in self.ciclos]

    def falhados(self) -> list[str]:
        return [i.id for i in self.invariantes if not i.ok]


def _n(valor: float, casas: int = 1) -> str:
    return f"{valor:.{casas}f}".replace(".", ",")


def para_markdown(r: Relatorio) -> str:  # noqa: PLR0912
    d = r.duracoes()
    ufs = {v: k for k, v in r.anfitrioes.items()}
    linhas = [
        f"# Ensaio da noite eleitoral: {r.data:%Y-%m-%d} ({', '.join(r.estados)})",
        "",
        f"Resultado: **{'PASSOU' if r.ok else 'FALHOU'}**. Duração {_n(r.duracao, 0)} s, "
        f"intervalo {_n(r.intervalo)} s, {len(r.ciclos)} ciclos.",
        "",
        "## Calendário de falhas",
        "",
        "| Estado | Anfitrião | Falha | De (s) | Até (s) |",
        "| --- | --- | --- | ---: | ---: |",
    ]
    for f in sorted(r.plano.falhas, key=lambda f: f.inicio_s):
        linhas.append(
            f"| {ufs.get(f.anfitriao, '?')} | {f.anfitriao} | {f.tipo} | "
            f"{_n(f.inicio_s)} | {_n(f.fim_s)} |"
        )
    linhas += ["", "Alterações da fonte:", ""]
    for a in sorted(r.plano.alteracoes, key=lambda a: a.instante_s):
        linhas.append(f"- {ufs.get(a.anfitriao, '?')} ({a.anfitriao}) aos {_n(a.instante_s)} s")
    linhas += [
        "",
        "## Invariantes",
        "",
        "| Invariante | Resultado | Descrição |",
        "| --- | :---: | --- |",
    ]
    for i in r.invariantes:
        resultado = "passou" if i.ok else f"FALHOU ({len(i.problemas)})"
        linhas.append(f"| `{i.id}` | {resultado} | {i.descricao} |")
    for i in r.invariantes:
        if i.problemas:
            linhas += ["", f"### `{i.id}`: {len(i.problemas)} problema(s)", ""]
            linhas += [f"- {p}" for p in i.problemas[:15]]
            if len(i.problemas) > 15:
                linhas.append(f"- ... e mais {len(i.problemas) - 15}")
    linhas += [
        "",
        "## Duração dos ciclos",
        "",
        f"- Ciclos: {len(d)}; média {_n(statistics.fmean(d) if d else 0, 2)} s; "
        f"mediana {_n(statistics.median(d) if d else 0, 2)} s",
        f"- p95: **{_n(percentil(d, 0.95), 2)} s**; máximo: **{_n(max(d, default=0), 2)} s**",
        f"- Acima do intervalo ({_n(r.intervalo)} s): "
        f"{sum(1 for x in d if x > r.intervalo)} ciclos",
        "",
        "Os ciclos mais longos, com o tempo gasto por estado (início dentro do ciclo / gasto):",
        "",
        "| Ciclo | Duração (s) | Estados (início s / gasto s, falha injetada) |",
        "| ---: | ---: | --- |",
    ]
    for c in sorted(r.ciclos, key=lambda c: -c.duracao)[:8]:
        if c.duracao <= r.intervalo:
            break
        partes = [
            f"{e.uf} {_n(e.inicio_s)}/{_n(e.gasto)}"
            + (f" [{','.join(sorted(set(e.afetado_por)))}]" if e.afetado_por else "")
            for e in c.estados.values()
        ]
        linhas.append(f"| {c.indice} | {_n(c.duracao)} | {'; '.join(partes)} |")
    linhas += [
        "",
        "## Latência das alterações",
        "",
        "Tempo desde que o espelho passou a servir a versão nova até `parciais.json` a refletir "
        "(escrita) e até ao fim do ciclo em que isso aconteceu (momento do envio à Release).",
        "",
        "| Estado | Alteração (s) | Versão | Escrita (s) | Envio (s) | Nota |",
        "| --- | ---: | ---: | ---: | ---: | --- |",
    ]
    for latencia in r.latencias:
        escrita = "não chegou" if latencia.escrita_s is None else _n(latencia.escrita_s, 2)
        envio = "·" if latencia.publicavel_s is None else _n(latencia.publicavel_s, 2)
        linhas.append(
            f"| {latencia.uf} | {_n(latencia.instante_s)} | {latencia.versao} | {escrita} | "
            f"{envio} | {latencia.nota} |"
        )
    valores = [x.escrita_s for x in r.latencias if x.escrita_s is not None]
    if valores:
        linhas += [
            "",
            f"Latência de escrita: mediana {_n(statistics.median(valores), 2)} s, "
            f"máxima {_n(max(valores), 2)} s.",
        ]
    contagem: dict[str, dict[int, int]] = {}
    for p in r.pedidos:
        por_codigo = contagem.setdefault(p.falha or "normal", {})
        por_codigo[p.estado] = por_codigo.get(p.estado, 0) + 1
    linhas += [
        "",
        "## Pedidos servidos pelo espelho",
        "",
        "| Falha | Pedidos por código HTTP |",
        "| --- | --- |",
    ]
    for tipo, codigos in sorted(contagem.items()):
        linhas.append(f"| {tipo} | {', '.join(f'{k}: {v}' for k, v in sorted(codigos.items()))} |")
    linhas += ["", "## Alertas", ""]
    for uf, maximo in sorted(r.max_falhas.items()):
        linhas.append(f"- {uf}: máximo de falhas seguidas {maximo}")
    linhas.append(f"- Limiar de alerta: {FALHAS_ALERTA} falhas seguidas.")
    problemas = [f"`{i.id}`: {i.problemas[0]}" for i in r.invariantes if i.problemas]
    problemas += [f"Defeito do ensaio: {e}" for e in r.erros_ensaio] + r.avisos
    linhas += ["", "## Problemas encontrados", ""]
    linhas += [f"- {p}" for p in problemas] if problemas else ["Nenhum."]
    return "\n".join(linhas) + "\n"


# --- Ensaio --------------------------------------------------------------------------------


def _sem_rede(url: str) -> str:
    msg = f"o ensaio não devia pedir {url} para descobrir pedidos"
    raise ErroEnsaio(msg)


def _latencias(
    espelho: Espelho,
    vigilante: Vigilante,
    observador: Observador,
    versoes: dict[str, Versoes],
    ufs: dict[str, str],
) -> list[Latencia]:
    resultado: list[Latencia] = []
    for m in sorted(espelho.mudancas, key=lambda m: m.epoca):
        if m.alteracao.anfitriao not in ufs:  # manual.json: verificado à parte
            continue
        uf = ufs[m.alteracao.anfitriao]
        esperado = versoes[uf].marcas[m.versao]
        anterior = versoes[uf].marcas[m.versao - 1]
        nota = "" if esperado != anterior else "soma igual à versão anterior (medição ambígua)"
        visto = next(
            (t for t, somas in vigilante.eventos if t >= m.epoca and somas.get(uf) == esperado),
            None,
        )
        fim = next((t for t in observador.fim_ciclos if visto is not None and t >= visto), None)
        resultado.append(
            Latencia(
                m.alteracao.anfitriao,
                uf,
                m.alteracao.instante_s,
                m.versao,
                m.epoca,
                None if visto is None else visto - m.epoca,
                None if fim is None or visto is None else fim - m.epoca,
                nota,
            )
        )
    return resultado


def _fechar(  # noqa: PLR0912, PLR0917
    observador: Observador,
    plano: Plano,
    latencias: list[Latencia],
    espelho: Espelho,
    intervalo: float,
    latencia_maxima: float,
    erro_fatal: str | None,
) -> list[Invariante]:
    v = observador.violacoes
    if erro_fatal:
        v["ciclo_nao_falha"].append(f"o ciclo levantou: {erro_fatal}")
    if len(observador.ciclos) < 2:
        v["ciclo_nao_falha"].append(f"só {len(observador.ciclos)} ciclo(s) concluído(s)")
    for uf, h in observador.anfitrioes.items():
        longa = any(
            f.anfitriao == h
            and f.tipo in ("ausente", "bloqueio")
            and f.fim_s - f.inicio_s >= (FALHAS_ALERTA + 1) * intervalo
            for f in plano.falhas
        )
        if not longa:
            continue
        if uf not in observador.alerta_visto:
            v["alertas"].append(f"{uf}: a falha longa do calendário nunca levantou alerta")
        elif uf not in observador.alerta_limpo:
            v["alertas"].append(f"{uf}: o alerta nunca foi limpo depois da recuperação")
    for c in observador.ciclos:
        if c.duracao > intervalo:
            causa = sorted({t for e in c.estados.values() for t in e.afetado_por})
            v["ciclo_dentro_do_intervalo"].append(
                f"ciclo {c.indice}: {c.duracao:.1f} s > {intervalo:.1f} s "
                f"(falhas ativas: {', '.join(causa) or 'nenhuma'})"
            )
        for lento in c.estados.values():
            if "lento" not in lento.afetado_por or lento.gasto <= intervalo:
                continue
            depois = [e for e in c.estados.values() if e.inicio_s > lento.inicio_s]
            atrasados = [e for e in depois if e.inicio_s - lento.inicio_s > intervalo]
            texto = f"ciclo {c.indice}: {lento.uf} (lento) demorou {lento.gasto:.1f} s"
            if atrasados:
                texto += "; " + "; ".join(
                    f"{e.uf} só começou aos {e.inicio_s:.1f} s do ciclo" for e in atrasados
                )
            else:
                texto += "; o ciclo seguinte (todos os estados) começa com este atraso"
            v["lento_isolado"].append(texto)
    for x in latencias:
        if x.escrita_s is None:
            v["latencia"].append(
                f"{x.uf}: a alteração dos {x.instante_s:.1f} s nunca chegou a parciais.json"
            )
        elif x.escrita_s > latencia_maxima:
            v["latencia"].append(
                f"{x.uf}: a alteração dos {x.instante_s:.1f} s chegou ao fim de "
                f"{x.escrita_s:.1f} s (máximo {latencia_maxima:.1f} s)"
            )
    dos_estados = [a for a in plano.alteracoes if a.anfitriao in observador.anfitrioes.values()]
    if len(latencias) < len(dos_estados):
        v["latencia"].append(
            f"só {len(latencias)} de {len(dos_estados)} alterações ocorreram antes do fim"
        )
    for f in plano.falhas:
        if not any(p.anfitriao == f.anfitriao and p.falha == f.tipo for p in espelho.pedidos):
            v["falhas_exercitadas"].append(
                f"{f.tipo} em {f.anfitriao} ({f.inicio_s:.1f}-{f.fim_s:.1f} s): "
                "nenhum pedido caiu na janela"
            )
    return [Invariante(k, INVARIANTES[k], v[k]) for k in INVARIANTES]


ETIQUETA_PRODUCAO = "resultados-2026"
"""Release da noite real: o ensaio nunca publica para aí."""


def validar_etiqueta(publicar: str | None) -> None:
    """Recusa publicar o ensaio na Release de produção."""
    if publicar is not None and publicar.strip() == ETIQUETA_PRODUCAO:
        msg = (
            f"o ensaio não pode publicar na Release de produção {ETIQUETA_PRODUCAO!r}; "
            "usa outra etiqueta (por exemplo resultados-ensaio)"
        )
        raise ValueError(msg)


def executar(
    estados: list[CodigoEstado],
    data: date,
    *,
    duracao: float,
    intervalo: float,
    saida: Path,
    raiz: Path = RAIZ_PADRAO,
    descarga: bool = True,
    plano: Plano | None = None,
    cliente: httpx.Client | None = None,
    lento_s: float = 22.0,
    retry_after: int = 5,
    latencia_maxima: float | None = None,
    manual: bool = False,
    publicar: str | None = None,
) -> Relatorio:
    """Corre o ensaio e devolve o relatório (não termina o processo).

    Com ``publicar``, cada ciclo envia os ficheiros alterados para essa Release, como a
    recolha de produção (``Recolha.enviar``).
    """
    validar_etiqueta(publicar)
    conectores = [CONECTORES[e] for e in estados]
    ignorar = frozenset(MANUAIS) if manual else frozenset()
    preparar_espelho(raiz, conectores, data, descarga=descarga)
    anfitrioes = {
        c.estado.value: urlsplit(c.pedidos(data, _sem_rede)[0].url).netloc for c in conectores
    }
    ufs = {h: uf for uf, h in anfitrioes.items()}
    plano = plano or plano_padrao(anfitrioes, duracao, intervalo)
    versoes = {
        c.estado.value: construir_versoes(
            c,
            data,
            raiz,
            len(plano.alteracoes_de(anfitrioes[c.estado.value])),
            _sem_rede,
            ignorar=ignorar,
        )
        for c in conectores
        if plano.alteracoes_de(anfitrioes[c.estado.value])
    }
    servidas = dict(versoes)
    if manual:
        partes = urlsplit(URL_MANUAL)
        servidas["manual"] = Versoes(
            {f"{partes.netloc}{partes.path}": versoes_manuais(estados, data)}, []
        )
        plano = Plano(
            plano.falhas,
            plano.alteracoes
            + tuple(Alteracao(ANFITRIAO_MANUAL, round(f * duracao, 2)) for f in FRACOES_MANUAIS),
        )
    brutos = saida.parent / f"{saida.name}-brutos"
    for pasta in (saida, brutos):
        shutil.rmtree(pasta, ignore_errors=True)
    espelho = Espelho(raiz, plano, servidas, lento_s=lento_s, retry_after=retry_after)
    espelho.arrancar()
    proprio = cliente is None
    http = cliente or httpx.Client(
        timeout=httpx.Timeout(20.0),
        follow_redirects=True,
        headers={"User-Agent": USER_AGENT},
    )
    observador = Observador(espelho, saida, data, anfitrioes, intervalo)
    recolha = RecolhaObservada(
        data,
        saida,
        brutos,
        espelho.url,
        cliente=http,
        orcamento=min(ORCAMENTO_CICLO, intervalo / 3),
        publicar=publicar,
        reconstruido=True,  # o espelho repete os ficheiros finais de uma eleição passada
        manual=URL_MANUAL if manual else None,
        observador=observador,
    )
    vigilante = Vigilante(saida / PARCIAIS, ignorar)
    vigilante.start()
    erro_fatal: str | None = None
    espelho.iniciar_relogio()
    try:
        executar_recolha(recolha, conectores, intervalo=intervalo, duracao=duracao)
    except Exception as erro:  # o ciclo nunca devia rebentar
        erro_fatal = f"{type(erro).__name__}: {erro}"
        registo.exception("A recolha rebentou")
    finally:
        time.sleep(2 * SONDAGEM_S)
        vigilante.parar.set()
        vigilante.join()
        espelho.terminar()
        if proprio:
            http.close()
    latencias = _latencias(espelho, vigilante, observador, versoes, ufs)
    maxima = latencia_maxima if latencia_maxima is not None else MARGEM_LATENCIA * intervalo
    if manual:
        servidos = {m.versao for m in espelho.mudancas if m.alteracao.anfitriao == ANFITRIAO_MANUAL}
        if len(observador.manuais_vistos - {0}) < len(servidos):
            observador.violacoes["manual"].append(
                f"só {len(observador.manuais_vistos - {0})} de {len(servidos)} entradas "
                "manuais chegaram a parciais.json"
            )
    invariantes = _fechar(observador, plano, latencias, espelho, intervalo, maxima, erro_fatal)
    return Relatorio(
        data=data,
        estados=[e.value for e in estados],
        duracao=duracao,
        intervalo=intervalo,
        plano=plano,
        anfitrioes=anfitrioes,
        ciclos=observador.ciclos,
        invariantes=invariantes,
        latencias=latencias,
        pedidos=espelho.pedidos,
        erros_ensaio=observador.erros_ensaio,
        max_falhas=observador.max_falhas,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--estados", default=ESTADOS_PADRAO)
    parser.add_argument("--data", type=date.fromisoformat, default=date(2024, 11, 5))
    parser.add_argument("--duracao", type=float, default=300.0, help="segundos")
    parser.add_argument("--intervalo", type=float, default=5.0, help="segundos")
    parser.add_argument("--saida", type=Path, default=RAIZ_PADRAO / "saida")
    parser.add_argument("--raiz", type=Path, default=RAIZ_PADRAO, help="pasta do espelho")
    parser.add_argument("--relatorio", type=Path, help="onde escrever o relatório em Markdown")
    parser.add_argument("--sem-descarga", action="store_true")
    parser.add_argument("--lento", type=float, default=22.0, help="demora da fonte lenta (s)")
    parser.add_argument("--latencia-maxima", type=float)
    parser.add_argument(
        "--manual", action="store_true", help="servir também entradas manuais (PA-S, TX-S)"
    )
    parser.add_argument(
        "--publicar",
        metavar="ETIQUETA",
        help="Release de ensaio para onde enviar os ficheiros a cada ciclo (nunca resultados-2026)",
    )
    args = parser.parse_args(argv)
    try:
        validar_etiqueta(args.publicar)
    except ValueError as erro:
        parser.error(str(erro))
    logging.basicConfig(level=logging.WARNING, format="%(asctime)s %(levelname)s %(message)s")
    estados = [CodigoEstado(e.strip().upper()) for e in args.estados.split(",")]
    relatorio = executar(
        estados,
        args.data,
        duracao=args.duracao,
        intervalo=args.intervalo,
        saida=args.saida,
        raiz=args.raiz,
        descarga=not args.sem_descarga,
        lento_s=args.lento,
        latencia_maxima=args.latencia_maxima,
        manual=args.manual,
        publicar=args.publicar,
    )
    texto = para_markdown(relatorio)
    if args.relatorio:
        args.relatorio.parent.mkdir(parents=True, exist_ok=True)
        args.relatorio.write_text(texto, encoding="utf-8")
    sys.stdout.write(texto)
    return 0 if relatorio.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
