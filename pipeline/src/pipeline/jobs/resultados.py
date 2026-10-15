"""Recolha dos resultados da noite eleitoral, em ciclo.

Uso::

    uv run python -m pipeline.jobs.resultados --data 2026-11-03 --saida data/publicado/resultados

A cada ``--intervalo`` segundos (30 por omissão), pede a cada estado os seus ficheiros com
pedidos condicionais (ETag, Last-Modified). Quando algum mudou:

1. guarda uma cópia dos ficheiros da fonte em ``--brutos/<estado>/<hora>/`` (para o ensaio
   geral e para rever a noite depois);
2. lê, valida e escreve ``<estado>.json`` (contrato ``ResultadosEstado``);
3. compara com o retrato anterior e regista descidas de totais (correções da fonte);
4. reescreve ``nacional.json`` e ``parciais.json`` (entrada do estimador ao vivo, com uma
   cópia por instante em ``--brutos/parciais/``) e, com ``--publicar``, envia os ficheiros
   alterados para a Release indicada.

Um estado que falha (fonte em baixo, resposta vazia, ficheiro corrompido, 403/429,
formato novo, ou qualquer erro inesperado na leitura) não para os outros: o seu último
ficheiro válido continua publicado e nada inválido é escrito. Os estados são recolhidos em
paralelo e o ciclo só espera ``ORCAMENTO_CICLO`` segundos: uma fonte lenta continua em
fundo e entra no ciclo em que acabar, sem atrasar as outras. A cada ciclo, ``saude.json``
diz, por estado, o último sucesso, a última alteração da fonte, as falhas seguidas e se
há alerta (ver ``pipeline.jobs.vigia``). ``--espelho`` troca o servidor de cada fonte por
um servidor local, para o ensaio geral.
"""

import argparse
import json
import logging
import shutil
import subprocess
import time
from collections.abc import Sequence
from concurrent.futures import Future, ThreadPoolExecutor, wait
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from urllib.parse import urlsplit

import httpx

from contratos.base import Fonte
from contratos.estados import CodigoEstado
from contratos.resultados import ResultadosEstado
from pipeline.comum.descarga import (
    USER_AGENT,
    Descarga,
    contexto_tls,
    descarregar,
    obter_texto,
)
from pipeline.comum.erros import ErroPipeline
from pipeline.connectors.results.comum import ConectorResultados
from pipeline.connectors.results.manual import FICHEIRO as FICHEIRO_MANUAL
from pipeline.connectors.results.manual import ConectorManual, aceita_manual, ler_ficheiro
from pipeline.connectors.results.registo import CONECTORES, nomes_geo
from pipeline.transform.resultados import ensaio
from pipeline.transform.resultados.montar import Leitura, montar, nacional
from pipeline.transform.resultados.parciais import montar_parciais

registo = logging.getLogger(__name__)

NACIONAL = "nacional.json"
PARCIAIS = "parciais.json"
SAUDE = "saude.json"
FALHAS_ALERTA = 6
"""Falhas seguidas (3 minutos com o intervalo de 30 s) que tornam o estado um alerta."""

SEM_ALTERACAO_ALERTA = 45 * 60
"""Segundos sem alteração da fonte, com a contagem por acabar, que tornam o estado um
alerta. Na noite, os estados atualizam a cada poucos minutos; 45 minutos parados com
secções por apurar quase sempre querem dizer uma fonte presa."""

SAUDE_CICLOS = 10
"""Com ``--publicar``, ``saude.json`` vai para a Release a cada tantos ciclos (5 minutos),
ou logo que um alerta muda."""
PEDIDOS_PARALELOS = 8
"""Pedidos simultâneos à mesma fonte, para os ficheiros de detalhe por condado."""

ORCAMENTO_CICLO = 10.0
"""Segundos que um ciclo espera pelos estados. Um estado que demore mais (fonte lenta,
novas tentativas) continua em fundo e é recolhido no ciclo em que terminar."""

ESPERA_MAXIMA = 5.0
"""Espera máxima entre tentativas dentro de um ciclo. Um ``Retry-After`` maior não é
esperado dentro do ciclo: o estado fica em pausa (``nao_antes``) e os outros seguem."""

PAUSA_MAXIMA = 300.0
"""Teto para a pausa pedida por um ``Retry-After``."""


@dataclass
class EstadoRecolha:
    """O que a recolha guarda entre ciclos, por estado."""

    ultimo: ResultadosEstado | None = None
    leitura: Leitura | None = None
    falhas_seguidas: int = 0
    problemas: list[str] = field(default_factory=list)
    ultimo_sucesso: datetime | None = None
    """Último ciclo em que a fonte respondeu e o ficheiro (novo ou igual) foi válido."""

    ultima_alteracao: datetime | None = None
    """Último ciclo em que a fonte trouxe dados novos."""

    ultimo_erro: str | None = None
    nao_antes: datetime | None = None
    """Hora antes da qual não se volta a pedir (``Retry-After`` de um 429 ou 503)."""

    def apurado(self) -> bool:
        """Todas as corridas com todas as unidades apuradas (a fonte pode parar)."""
        if self.ultimo is None or not self.ultimo.corridas:
            return False
        return all(
            c.unidades_totais is not None and c.unidades_reportadas == c.unidades_totais
            for c in self.ultimo.corridas
        )

    def alerta(self, agora: datetime) -> str | None:
        if self.falhas_seguidas >= FALHAS_ALERTA:
            return f"{self.falhas_seguidas} falhas seguidas: {self.ultimo_erro}"
        if self.ultima_alteracao is not None and not self.apurado():
            parado = (agora - self.ultima_alteracao).total_seconds()
            if parado >= SEM_ALTERACAO_ALERTA:
                return f"sem dados novos há {int(parado // 60)} minutos, com a contagem por acabar"
        return None


@dataclass
class Recolha:
    data: date
    saida: Path
    brutos: Path
    espelho: str | None = None
    publicar: str | None = None
    cliente: httpx.Client = field(
        default_factory=lambda: httpx.Client(
            timeout=httpx.Timeout(15.0, connect=5.0),
            follow_redirects=True,
            headers={"User-Agent": USER_AGENT},
            verify=contexto_tls(),
        )
    )
    estados: dict[CodigoEstado, EstadoRecolha] = field(default_factory=dict)
    orcamento: float = ORCAMENTO_CICLO
    manual: str | None = None
    """URL do ``manual.json`` (resultados introduzidos à mão); ``None`` para não o ler."""
    _executor: ThreadPoolExecutor = field(
        default_factory=lambda: ThreadPoolExecutor(max_workers=16, thread_name_prefix="estado"),
        repr=False,
    )
    sobrepostos: dict[CodigoEstado, EstadoRecolha] = field(default_factory=dict)
    """Entradas manuais nos estados acompanhados só por alguns condados (Texas, Arizona):
    publicam-se à parte (``tx-manual.json``) e substituem, no resumo e nos parciais, as
    corridas desses condados."""

    _em_curso: dict[str, Future[Path | None]] = field(default_factory=dict, repr=False)

    def url(self, url: str) -> str:
        if self.espelho is None:
            return url
        partes = urlsplit(url)
        return f"{self.espelho.rstrip('/')}/{partes.netloc}{partes.path}"

    def obter(self, url: str) -> str:
        return obter_texto(self.cliente, self.url(url))

    def ciclo(self, conectores: Sequence[ConectorResultados]) -> list[Path]:
        """Um ciclo de recolha; devolve os ficheiros publicados que mudaram.

        Cada estado corre na sua linha de execução. O ciclo espera no máximo
        ``orcamento`` segundos; um estado ainda em curso não é lançado de novo e o seu
        resultado entra no ciclo em que terminar."""
        # Primeiro, o que acabou em fundo desde o ciclo anterior (fica livre para relançar).
        alterados = self._recolher_terminados()
        conectores = [*conectores, *self._conectores_manuais(conectores)]
        agora = datetime.now(UTC)
        lancados: list[Future[Path | None]] = []
        for conector in conectores:
            registos = self.sobrepostos if _sobreposto(conector) else self.estados
            estado = registos.setdefault(conector.estado, EstadoRecolha())
            chave = chave_recolha(conector)
            if chave in self._em_curso:
                continue
            if estado.nao_antes is not None and agora < estado.nao_antes:
                continue
            futuro = self._executor.submit(self._processar, conector, estado)
            self._em_curso[chave] = futuro
            lancados.append(futuro)
        # Só se espera pelos lançados agora: um estado que já vinha atrasado não volta a
        # prender o ciclo.
        wait(lancados, timeout=self.orcamento)
        alterados += self._recolher_terminados()
        for uf in self.em_curso():
            registo.warning("%s: a recolha ainda não acabou; segue em fundo", uf)
        if alterados:
            try:
                alterados += [self._nacional(), self._parciais()]
            except Exception:
                # Sem resumo nem parciais novos neste ciclo; os ficheiros dos estados, já
                # validados, seguem. No ciclo seguinte volta a tentar-se.
                registo.exception("Falhou o resumo nacional ou os parciais")
        return alterados

    def _conectores_manuais(
        self, automaticos: Sequence[ConectorResultados]
    ) -> list[ConectorResultados]:
        """Um ``ConectorManual`` por estado com entradas em ``manual.json``. Os estados com
        fonte estadual automática ficam de fora (os números vêm da fonte aberta); nos
        acompanhados só por alguns condados, a entrada manual fica sobreposta."""
        if self.manual is None:
            return []
        destino = self.brutos / "manual" / FICHEIRO_MANUAL
        try:
            self._descarregar(self.manual, destino)
            estados = ler_ficheiro(destino).estados()
        except Exception as erro:  # sem entradas novas, a noite segue
            if destino.exists():
                registo.warning("Entrada manual: %s", erro)
            return []
        tipos = {c.estado: c for c in automaticos}
        ignorados = sorted(uf for uf in estados if uf in tipos and not aceita_manual(tipos[uf]))
        if ignorados:
            registo.warning("Entrada manual ignorada (há fonte automática): %s", ignorados)
        return [
            ConectorManual(uf, self.manual, sobreposto=uf in tipos)
            for uf in sorted(estados - set(ignorados))
        ]

    def _recolher_terminados(self) -> list[Path]:
        alterados: list[Path] = []
        for chave, futuro in list(self._em_curso.items()):
            if futuro.done():
                del self._em_curso[chave]
                if (caminho := futuro.result()) is not None:
                    alterados.append(caminho)
        return alterados

    def em_curso(self) -> set[CodigoEstado]:
        """Estados cuja recolha ainda não terminou (continuam em fundo)."""
        return {
            CodigoEstado(chave[:2].upper())
            for chave, futuro in self._em_curso.items()
            if not futuro.done()
        }

    def _processar(self, conector: ConectorResultados, estado: EstadoRecolha) -> Path | None:
        """Recolhe um estado e atualiza o seu registo; nunca falha."""
        try:
            caminho = self._estado(conector, estado)
        except Exception as erro:
            estado.falhas_seguidas += 1
            estado.ultimo_erro = f"{type(erro).__name__}: {erro}"[:300]
            estado.nao_antes = _nao_antes(erro)
            esperado = isinstance(erro, ErroPipeline | httpx.HTTPError | ValueError)
            nivel = logging.WARNING if estado.falhas_seguidas < 3 else logging.ERROR
            registo.log(nivel, "%s: %s", conector.estado, erro, exc_info=not esperado)
            return None
        agora = datetime.now(UTC)
        estado.falhas_seguidas = 0
        estado.ultimo_erro = None
        estado.nao_antes = None
        estado.ultimo_sucesso = agora
        if caminho is not None:
            estado.ultima_alteracao = agora
        return caminho

    def saude(self, agora: datetime | None = None) -> dict[str, object]:
        """Estado da recolha para o vigia (não é um contrato do site)."""
        agora = agora or datetime.now(UTC)

        def hora(valor: datetime | None) -> str | None:
            return valor.isoformat() if valor else None

        return {
            "gerado_em": agora.isoformat(),
            "data_eleicao": self.data.isoformat(),
            "estados": {
                chave: {
                    "ultimo_sucesso": hora(e.ultimo_sucesso),
                    "ultima_alteracao": hora(e.ultima_alteracao),
                    "falhas_seguidas": e.falhas_seguidas,
                    "ultimo_erro": e.ultimo_erro,
                    "apurado": e.apurado(),
                    "alerta": e.alerta(agora),
                }
                for chave, e in self._registos()
            },
        }

    def escrever_saude(self) -> Path:
        saida = self.saida / SAUDE
        _escrever(saida, json.dumps(self.saude(), ensure_ascii=False, indent=2))
        return saida

    def _registos(self) -> list[tuple[str, EstadoRecolha]]:
        """Todos os registos, com a chave da saúde (``TX``, ``TX-manual``)."""
        return sorted(
            [(uf.value, e) for uf, e in self.estados.items()]
            + [(f"{uf.value}-manual", e) for uf, e in self.sobrepostos.items()]
        )

    def _estado(self, conector: ConectorResultados, estado: EstadoRecolha) -> Path | None:
        uf = chave_recolha(conector)
        pasta = self.brutos / uf / "atual"
        pedidos = conector.pedidos(self.data, self.obter)
        sentinelas = [p for p in pedidos if p.sentinela]
        descargas = [self._descarregar(p.url, pasta / p.ficheiro) for p in sentinelas]
        if estado.ultimo is not None and not any(d.alterado for d in descargas):
            return None
        detalhe = [p for p in pedidos if not p.sentinela]
        with ThreadPoolExecutor(max_workers=PEDIDOS_PARALELOS) as executor:
            descargas += executor.map(
                lambda p: self._descarregar(p.url, pasta / p.ficheiro), detalhe
            )
        agora = datetime.now(UTC)
        try:
            leitura = conector.ler(pasta, self.data)
            resultado = montar(
                estado=conector.estado,
                data_eleicao=self.data,
                leitura=leitura,
                fontes=[
                    Fonte(
                        nome=conector.nome_fonte,
                        url=pedidos[0].url,
                        licenca=conector.licenca,
                        obtida_em=max(d.obtido_em for d in descargas),
                    )
                ],
                nomes_geo=nomes_geo(conector.estado),
                gerado_em=agora,
            )
        except Exception:
            # Sem os ETag guardados, o ciclo seguinte volta a descarregar e a ler tudo; um
            # 304 sobre um ficheiro que não se leu não pode passar por sucesso.
            for meta in pasta.rglob("*.meta.json"):
                meta.unlink(missing_ok=True)
            raise
        if estado.ultimo is not None:
            for p in ensaio.verificar_sequencia([estado.ultimo, resultado]):
                texto = f"{agora:%H:%M:%S} {p.corrida}: {p.descricao}"
                estado.problemas.append(texto)
                registo.warning("%s %s", conector.estado, texto)
        copia = self.brutos / uf / f"{agora:%Y%m%dT%H%M%S.%f}"
        shutil.copytree(pasta, copia, ignore=shutil.ignore_patterns("*.parcial"))
        estado.ultimo = resultado
        estado.leitura = leitura
        saida = self.saida / f"{uf}.json"
        _escrever(saida, resultado.model_dump_json())
        registo.info(
            "%s: %s corridas, %s votos",
            conector.estado,
            len(resultado.corridas),
            sum(c.total for c in resultado.corridas),
        )
        return saida

    def _descarregar(self, url: str, destino: Path) -> Descarga:
        return descarregar(
            self.url(url), destino, cliente=self.cliente, tentativas=2, espera_maxima=ESPERA_MAXIMA
        )

    def _nacional(self) -> Path:
        estados = [
            (r.ultimo, f"{chave.lower()}.json")
            for chave, r in self._registos()
            if r.ultimo is not None
        ]
        resumo = nacional(estados, data_eleicao=self.data)
        saida = self.saida / NACIONAL
        _escrever(saida, resumo.model_dump_json())
        return saida

    def _parciais(self) -> Path:
        agora = datetime.now(UTC)
        prontos = [r for _, r in self._registos() if r.ultimo and r.leitura]
        parciais = montar_parciais(
            [r.leitura for r in prontos if r.leitura is not None],
            ano=self.data.year,
            instante=agora,
            fontes=[f for r in prontos if r.ultimo for f in r.ultimo.metadados.fontes],
            gerado_em=agora,
        )
        texto = parciais.model_dump_json()
        _escrever(self.brutos / "parciais" / f"{agora:%Y%m%dT%H%M%S.%f}.json", texto)
        saida = self.saida / PARCIAIS
        _escrever(saida, texto)
        return saida

    def enviar(self, ficheiros: Sequence[Path]) -> None:
        if not self.publicar or not ficheiros:
            return
        comando = ["gh", "release", "upload", self.publicar, *map(str, ficheiros), "--clobber"]
        resultado = subprocess.run(comando, check=False, capture_output=True, text=True)  # noqa: S603
        if resultado.returncode != 0:
            registo.error("Falhou a publicação: %s", resultado.stderr.strip())


def _sobreposto(conector: ConectorResultados) -> bool:
    return isinstance(conector, ConectorManual) and conector.sobreposto


def chave_recolha(conector: ConectorResultados) -> str:
    """Nome do ficheiro e da pasta de brutos: ``tx``, ou ``tx-manual`` sobreposto."""
    uf = conector.estado.value.lower()
    return f"{uf}-manual" if _sobreposto(conector) else uf


def _nao_antes(erro: BaseException) -> datetime | None:
    """Hora pedida pela fonte num 429 ou 503 com ``Retry-After`` (em segundos)."""
    causa: BaseException | None = erro
    while causa is not None and not isinstance(causa, httpx.HTTPStatusError):
        causa = causa.__cause__
    if causa is None or causa.response.status_code not in {429, 503}:
        return None
    pedido = causa.response.headers.get("retry-after", "").strip()
    if not pedido.isdigit():
        return None
    return datetime.now(UTC) + timedelta(seconds=min(float(pedido), PAUSA_MAXIMA))


def _escrever(caminho: Path, texto: str) -> None:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    temporario = caminho.with_name(caminho.name + ".parcial")
    temporario.write_text(texto, encoding="utf-8")
    temporario.replace(caminho)


def executar(
    recolha: Recolha,
    conectores: Sequence[ConectorResultados],
    *,
    intervalo: float,
    duracao: float | None = None,
    ciclos: int | None = None,
) -> int:
    """Corre ciclos até ``duracao`` segundos ou ``ciclos`` ciclos; devolve os ciclos feitos."""
    inicio = time.monotonic()
    feitos = 0
    alertas_antes: set[str] = set()
    while (ciclos is None or feitos < ciclos) and (
        duracao is None or time.monotonic() - inicio < duracao
    ):
        comeco = time.monotonic()
        alterados = recolha.ciclo(conectores)
        saude = recolha.escrever_saude()
        agora = datetime.now(UTC)
        alertas = {
            uf.value: texto
            for uf, e in recolha.estados.items()
            if (texto := e.alerta(agora)) is not None
        }
        for uf in sorted(set(alertas) - alertas_antes):
            registo.error("ALERTA %s: %s", uf, alertas[uf])
        if set(alertas) != alertas_antes or feitos % SAUDE_CICLOS == 0:
            alterados.append(saude)
        alertas_antes = set(alertas)
        recolha.enviar(alterados)
        feitos += 1
        gasto = time.monotonic() - comeco
        if gasto > intervalo:
            registo.warning("Ciclo de %.1f s, acima do intervalo de %.0f s", gasto, intervalo)
        if ciclos is None or feitos < ciclos:
            time.sleep(max(0.0, intervalo - gasto))
    return feitos


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--data", type=date.fromisoformat, default=date(2026, 11, 3))
    parser.add_argument("--estados", default=",".join(e.value for e in CONECTORES))
    parser.add_argument("--saida", type=Path, default=Path("data/publicado/resultados"))
    parser.add_argument("--brutos", type=Path, default=Path("data/brutos/resultados"))
    parser.add_argument("--intervalo", type=float, default=30.0)
    parser.add_argument("--duracao", type=float, help="segundos; sem valor, corre um ciclo")
    parser.add_argument("--espelho", help="servidor local que substitui as fontes (ensaio)")
    parser.add_argument("--publicar", help="etiqueta da Release para onde enviar os ficheiros")
    parser.add_argument("--manual", help="URL do manual.json com os resultados introduzidos à mão")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)
    conectores = [CONECTORES[CodigoEstado(e.strip().upper())] for e in args.estados.split(",")]
    recolha = Recolha(
        args.data, args.saida, args.brutos, args.espelho, args.publicar, manual=args.manual
    )
    executar(
        recolha,
        conectores,
        intervalo=args.intervalo,
        duracao=args.duracao,
        ciclos=None if args.duracao else 1,
    )


if __name__ == "__main__":
    main()
