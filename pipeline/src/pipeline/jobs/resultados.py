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
ficheiro válido continua publicado e nada inválido é escrito. A cada ciclo, ``saude.json``
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
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
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
            timeout=httpx.Timeout(20.0),
            follow_redirects=True,
            headers={"User-Agent": USER_AGENT},
            verify=contexto_tls(),
        )
    )
    estados: dict[CodigoEstado, EstadoRecolha] = field(default_factory=dict)

    def url(self, url: str) -> str:
        if self.espelho is None:
            return url
        partes = urlsplit(url)
        return f"{self.espelho.rstrip('/')}/{partes.netloc}{partes.path}"

    def obter(self, url: str) -> str:
        return obter_texto(self.cliente, self.url(url))

    def ciclo(self, conectores: Sequence[ConectorResultados]) -> list[Path]:
        """Um ciclo de recolha; devolve os ficheiros publicados que mudaram."""
        alterados: list[Path] = []
        for conector in conectores:
            estado = self.estados.setdefault(conector.estado, EstadoRecolha())
            try:
                caminho = self._estado(conector, estado)
            except Exception as erro:
                estado.falhas_seguidas += 1
                estado.ultimo_erro = f"{type(erro).__name__}: {erro}"[:300]
                esperado = isinstance(erro, ErroPipeline | httpx.HTTPError | ValueError)
                nivel = logging.WARNING if estado.falhas_seguidas < 3 else logging.ERROR
                registo.log(nivel, "%s: %s", conector.estado, erro, exc_info=not esperado)
                continue
            agora = datetime.now(UTC)
            estado.falhas_seguidas = 0
            estado.ultimo_erro = None
            estado.ultimo_sucesso = agora
            if caminho is not None:
                estado.ultima_alteracao = agora
                alterados.append(caminho)
        if alterados:
            try:
                alterados += [self._nacional(), self._parciais()]
            except Exception:
                # Sem resumo nem parciais novos neste ciclo; os ficheiros dos estados, já
                # validados, seguem. No ciclo seguinte volta a tentar-se.
                registo.exception("Falhou o resumo nacional ou os parciais")
        return alterados

    def saude(self, agora: datetime | None = None) -> dict[str, object]:
        """Estado da recolha para o vigia (não é um contrato do site)."""
        agora = agora or datetime.now(UTC)

        def hora(valor: datetime | None) -> str | None:
            return valor.isoformat() if valor else None

        return {
            "gerado_em": agora.isoformat(),
            "data_eleicao": self.data.isoformat(),
            "estados": {
                uf.value: {
                    "ultimo_sucesso": hora(e.ultimo_sucesso),
                    "ultima_alteracao": hora(e.ultima_alteracao),
                    "falhas_seguidas": e.falhas_seguidas,
                    "ultimo_erro": e.ultimo_erro,
                    "apurado": e.apurado(),
                    "alerta": e.alerta(agora),
                }
                for uf, e in sorted(self.estados.items())
            },
        }

    def escrever_saude(self) -> Path:
        saida = self.saida / SAUDE
        _escrever(saida, json.dumps(self.saude(), ensure_ascii=False, indent=2))
        return saida

    def _estado(self, conector: ConectorResultados, estado: EstadoRecolha) -> Path | None:
        uf = conector.estado.value.lower()
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
        if estado.ultimo is not None:
            for p in ensaio.verificar_sequencia([estado.ultimo, resultado]):
                texto = f"{agora:%H:%M:%S} {p.corrida}: {p.descricao}"
                estado.problemas.append(texto)
                registo.warning("%s %s", conector.estado, texto)
        copia = self.brutos / uf / f"{agora:%Y%m%dT%H%M%S}"
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
        return descarregar(self.url(url), destino, cliente=self.cliente, tentativas=2)

    def _nacional(self) -> Path:
        estados = [
            (r.ultimo, f"{uf.value.lower()}.json")
            for uf, r in sorted(self.estados.items())
            if r.ultimo is not None
        ]
        resumo = nacional(estados, data_eleicao=self.data)
        saida = self.saida / NACIONAL
        _escrever(saida, resumo.model_dump_json())
        return saida

    def _parciais(self) -> Path:
        agora = datetime.now(UTC)
        prontos = [r for _, r in sorted(self.estados.items()) if r.ultimo and r.leitura]
        parciais = montar_parciais(
            [r.leitura for r in prontos if r.leitura is not None],
            ano=self.data.year,
            instante=agora,
            fontes=[f for r in prontos if r.ultimo for f in r.ultimo.metadados.fontes],
            gerado_em=agora,
        )
        texto = parciais.model_dump_json()
        _escrever(self.brutos / "parciais" / f"{agora:%Y%m%dT%H%M%S}.json", texto)
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
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)
    conectores = [CONECTORES[CodigoEstado(e.strip().upper())] for e in args.estados.split(",")]
    recolha = Recolha(args.data, args.saida, args.brutos, args.espelho, args.publicar)
    executar(
        recolha,
        conectores,
        intervalo=args.intervalo,
        duracao=args.duracao,
        ciclos=None if args.duracao else 1,
    )


if __name__ == "__main__":
    main()
