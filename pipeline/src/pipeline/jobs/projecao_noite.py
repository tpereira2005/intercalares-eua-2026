"""Corre o Modelo C na noite eleitoral e publica a projeção para o site.

Uso na noite de 3 de novembro, com a previsão congelada e o ``parciais.json`` que a
recolha de resultados publica na Release ``resultados-2026``::

    uv run python -m pipeline.jobs.projecao_noite --previsao previsao-2026.json \\
        --parciais https://github.com/<repo>/releases/download/resultados-2026/parciais.json \\
        --duracao 20700 --publicar dados-noite

A cada ``--intervalo`` segundos pede o ``parciais.json`` (pedido condicional). Quando
chega um instante novo, calcula a projeção (``ProjecaoNoite``), acrescenta-a ao histórico
da noite (``HistoricoNoite``), verifica os dois ficheiros e só então os escreve em
``--saida`` e, com ``--publicar``, os envia para a Release indicada. Um ciclo que falha
(fonte em baixo, ficheiro inválido) não apaga nada: fica publicado o último ficheiro
válido.

Ensaio ao vivo com uma noite antiga publicada pela recolha (por exemplo, a Release
``resultados-ensaio`` com a noite de 2024), a partir da previsão do backtest desse ano::

    uv run python -m pipeline.jobs.projecao_noite --backtest 2024 \\
        --parciais https://github.com/<repo>/releases/download/resultados-ensaio/parciais.json \\
        --duracao 3600 --publicar resultados-ensaio

Ensaio com noites reconstruídas pelo ensaio da recolha de resultados (o ponto de partida
é então a previsão do backtest desse ano, como em ``repeticao_noite``)::

    uv run python -m pipeline.jobs.ensaio_resultados --estado NC --data 2024-11-05 \\
        --parciais ensaio/NC-2024
    uv run python -m pipeline.jobs.projecao_noite --ensaio ensaio/NC-2024 \\
        --saida data/publicado/noite
"""

import argparse
import logging
import math
import subprocess
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import httpx

from contratos.base import Fonte
from contratos.noite import HistoricoNoite, ProjecaoNoite
from contratos.previsao import PrevisaoCongresso
from contratos.resultados import ResultadosParciais
from pipeline.comum.descarga import USER_AGENT, descarregar
from pipeline.comum.erros import ErroPipeline
from pipeline.jobs.avaliacao_previsao import DESEMPATE
from pipeline.jobs.referencia_noite import URL as URL_REFERENCIA
from pipeline.jobs.repeticao_noite import sequencia
from pipeline.modelo import carregar as carga
from pipeline.modelo.noite.entrada import Base, de_parciais, ler_referencia
from pipeline.modelo.noite.historico import acrescentar
from pipeline.modelo.noite.projecao import SIMULACOES, projetar
from pipeline.modelo.noite.repeticao import juntar
from pipeline.modelo.previsao import prever
from pipeline.modelo.publicar import montar

registo = logging.getLogger(__name__)

PROJECAO = "projecao-noite-{ano}.json"
HISTORICO = "historico-noite-{ano}.json"
PASTA_REFERENCIA = Path("data/reference/modelo")
URL_PREVISAO = (
    "https://github.com/tpereira2005/intercalares-eua-2026/releases/download/"
    "dados-previsao/previsao-{ano}.json"
)
TOLERANCIA = 1e-9


class ProjecaoIncoerente(ErroPipeline):
    """A projeção falhou uma verificação e não deve ser publicada."""


def ano_referencia(ano: int) -> int:
    """A presidencial anterior: 2024 para 2026, 2020 para 2022 e 2024."""
    return ano - (ano % 4 or 4)


def verificar(projecao: ProjecaoNoite, previsao: PrevisaoCongresso) -> None:
    """Verificações que o contrato não vê; uma falha impede a publicação."""
    problemas: list[str] = []
    ids = [c.id for c in projecao.corridas]
    if sorted(ids) != sorted(c.id for c in previsao.corridas):
        problemas.append("as corridas não são as da previsão")
    for resumo in (projecao.camara, projecao.senado):
        soma = resumo.prob_controlo_d + resumo.prob_controlo_r
        if soma > 1 + TOLERANCIA:
            problemas.append(f"{resumo.camara}: probabilidades de controlo somam {soma:.4f}")
        total = sum(p.probabilidade for p in resumo.distribuicao)
        if not math.isclose(total, 1.0, abs_tol=1e-6):
            problemas.append(f"{resumo.camara}: a distribuição de lugares soma {total:.6f}")
        if not resumo.lugares_d_p10 <= resumo.lugares_d_mediana <= resumo.lugares_d_p90:
            problemas.append(f"{resumo.camara}: percentis de lugares fora de ordem")
    for c in projecao.corridas:
        if not c.margem_p10 <= c.margem_projetada <= c.margem_p90:
            problemas.append(f"{c.id}: margem projetada fora do intervalo de 80%")
    if problemas:
        raise ProjecaoIncoerente("; ".join(problemas))


@dataclass
class Noite:
    """Estado do job entre ciclos: a previsão de partida e o último histórico válido."""

    previsao: PrevisaoCongresso
    referencia: dict[str, dict[str, Base]]
    fontes: tuple[Fonte, ...]
    saida: Path
    desempate: str
    historico: HistoricoNoite | None = None
    publicar: str | None = None
    simulacoes: int = SIMULACOES
    ultimo: datetime | None = None

    @property
    def caminhos(self) -> tuple[Path, Path]:
        ano = self.previsao.ano
        return self.saida / PROJECAO.format(ano=ano), self.saida / HISTORICO.format(ano=ano)

    def processar(self, parciais: ResultadosParciais) -> list[Path]:
        """Projeta um instante; devolve os ficheiros escritos (nenhum se não for novo)."""
        if parciais.ano != self.previsao.ano:
            msg = f"resultados de {parciais.ano} com previsão de {self.previsao.ano}"
            raise ProjecaoIncoerente(msg)
        if self.ultimo is not None and parciais.instante <= self.ultimo:
            return []
        projecao = projetar(
            self.previsao,
            de_parciais(parciais),
            self.referencia,
            fontes=self._fontes(parciais),
            gerado_em=datetime.now(UTC),
            desempate=self.desempate,
            simulacoes=self.simulacoes,
            reconstruido=parciais.reconstruido,
        )
        verificar(projecao, self.previsao)
        historico = acrescentar(self.historico, projecao)
        projecao_json, historico_json = self.caminhos
        _escrever(projecao_json, projecao.model_dump_json())
        _escrever(historico_json, historico.model_dump_json())
        self.historico = historico
        self.ultimo = parciais.instante
        registo.info(
            "%s: %d corridas com votos; Câmara P(D)=%.3f, Senado P(D)=%.3f, desvio %+.1f",
            parciais.instante.isoformat(timespec="seconds"),
            sum(c.votos_contados > 0 for c in projecao.corridas),
            projecao.camara.prob_controlo_d,
            projecao.senado.prob_controlo_d,
            projecao.desvio_nacional.media,
        )
        return [projecao_json, historico_json]

    def _fontes(self, parciais: ResultadosParciais) -> tuple[Fonte, ...]:
        vistas: set[tuple[str, str]] = set()
        fontes: list[Fonte] = []
        for f in (*self.fontes, *parciais.metadados.fontes):
            chave = (f.nome, str(f.url))
            if chave not in vistas:
                vistas.add(chave)
                fontes.append(f)
        return tuple(fontes)

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


def fontes_base(ano: int, corte: str, *, backtest: bool, agora: datetime) -> tuple[Fonte, ...]:
    ref = ano_referencia(ano)
    previsao = Fonte(
        nome=(
            f"Escrutínio: previsão do backtest de {ano}"
            if backtest
            else f"Escrutínio: previsão da Câmara e do Senado (corte de {corte})"
        ),
        url=(
            "https://github.com/tpereira2005/intercalares-eua-2026"
            if backtest
            else URL_PREVISAO.format(ano=ano)
        ),
        obtida_em=agora,
    )
    referencia = Fonte(
        nome=f"Tony McGovern: resultados presidenciais de {ref} por condado",
        url=URL_REFERENCIA.format(ano=ref),
        licenca="MIT",
        obtida_em=agora,
    )
    return previsao, referencia


def preparar(
    previsao: PrevisaoCongresso,
    saida: Path,
    *,
    backtest: bool = False,
    historico: Path | None = None,
    publicar: str | None = None,
    simulacoes: int = SIMULACOES,
) -> Noite:
    agora = datetime.now(UTC)
    referencia = ler_referencia(
        PASTA_REFERENCIA / f"presidencial_condados_{ano_referencia(previsao.ano)}.csv"
    )
    anterior = None
    if historico is not None and historico.exists():
        anterior = HistoricoNoite.model_validate_json(historico.read_text(encoding="utf-8"))
        registo.info("Histórico anterior com %d pontos", len(anterior.pontos))
    return Noite(
        previsao=previsao,
        referencia=referencia,
        fontes=fontes_base(
            previsao.ano, previsao.corte.isoformat(), backtest=backtest, agora=agora
        ),
        saida=saida,
        desempate=DESEMPATE[previsao.ano],
        historico=anterior,
        publicar=publicar,
        simulacoes=simulacoes,
        ultimo=anterior.pontos[-1].instante if anterior else None,
    )


def previsao_backtest(ano: int) -> PrevisaoCongresso:
    """A previsão do backtest de ``ano``, a mesma que estaria congelada nesse ano."""
    agora = datetime.now(UTC)
    fonte = Fonte(
        nome="Referência do modelo (backtest)",
        url="https://github.com/tpereira2005/intercalares-eua-2026",
        obtida_em=agora,
    )
    return montar(prever(carga.carregar(), ano), fontes=[fonte], gerado_em=agora)


def ensaio(
    pastas: Sequence[Path],
    saida: Path,
    *,
    passos: int,
    simulacoes: int = SIMULACOES,
    publicar: str | None = None,
) -> Noite:
    """Corre a noite reconstruída pelo ensaio da recolha, passo a passo."""
    sequencias = [sequencia(p, "ensaio", passos, 0) for p in pastas]
    previsao = previsao_backtest(sequencias[0][-1].ano)
    noite = preparar(previsao, saida, backtest=True, publicar=publicar, simulacoes=simulacoes)
    for i in range(max(len(s) for s in sequencias)):
        noite.processar(juntar([s[min(i, len(s) - 1)] for s in sequencias]))
    noite.enviar(noite.caminhos)
    return noite


def ler_parciais(origem: str, cache: Path, cliente: httpx.Client) -> ResultadosParciais | None:
    """Lê o ``parciais.json`` de um endereço (pedido condicional) ou de um ficheiro.

    Devolve ``None`` quando o endereço responde que nada mudou.
    """
    if origem.startswith(("https://", "http://")):
        descarga = descarregar(origem, cache, cliente=cliente, tentativas=2, espera_inicial=1.0)
        if not descarga.alterado:
            return None
        caminho = cache
    else:
        caminho = Path(origem)
    return ResultadosParciais.model_validate_json(caminho.read_bytes())


def executar(
    noite: Noite,
    obter: Callable[[], ResultadosParciais | None],
    *,
    intervalo: float,
    duracao: float | None,
) -> int:
    """Ciclos até ``duracao`` segundos (um só ciclo sem duração); devolve os publicados."""
    inicio = time.monotonic()
    publicados = 0
    while True:
        comeco = time.monotonic()
        try:
            parciais = obter()
            if parciais is not None:
                ficheiros = noite.processar(parciais)
                noite.enviar(ficheiros)
                publicados += bool(ficheiros)
        except (ErroPipeline, httpx.HTTPError, ValueError) as erro:
            registo.error("Ciclo falhou, fica publicado o último ficheiro válido: %s", erro)
        if duracao is None or time.monotonic() - inicio >= duracao:
            return publicados
        time.sleep(max(0.0, intervalo - (time.monotonic() - comeco)))


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    entrada = parser.add_mutually_exclusive_group(required=True)
    entrada.add_argument("--parciais", help="endereço ou ficheiro do parciais.json")
    entrada.add_argument("--ensaio", type=Path, nargs="+", help="pastas do ensaio da recolha")
    partida = parser.add_mutually_exclusive_group()
    partida.add_argument("--previsao", type=Path, help="ficheiro PrevisaoCongresso de partida")
    partida.add_argument(
        "--backtest",
        type=int,
        choices=[a for a in sorted(DESEMPATE) if a < carga.ANO_ATUAL],
        help="parte da previsão do backtest deste ano (ensaio ao vivo com uma noite antiga)",
    )
    parser.add_argument(
        "--aceitar-provisoria",
        action="store_true",
        help="aceita uma previsão ainda não congelada (ensaios antes de 1 de novembro)",
    )
    parser.add_argument("--saida", type=Path, default=Path("data/publicado/noite"))
    parser.add_argument("--historico", type=Path, help="histórico da noite a continuar")
    parser.add_argument("--intervalo", type=float, default=30.0)
    parser.add_argument("--duracao", type=float, help="segundos; sem valor, corre um ciclo")
    parser.add_argument("--publicar", help="etiqueta da Release para onde enviar os ficheiros")
    parser.add_argument("--passos", type=int, default=12)
    parser.add_argument("--simulacoes", type=int, default=SIMULACOES)
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)

    if args.ensaio:
        ensaio(
            args.ensaio,
            args.saida,
            passos=args.passos,
            simulacoes=args.simulacoes,
            publicar=args.publicar,
        )
        return
    if args.backtest is not None:
        previsao = previsao_backtest(args.backtest)
    elif args.previsao is not None:
        previsao = PrevisaoCongresso.model_validate_json(args.previsao.read_text(encoding="utf-8"))
        if not previsao.congelada and not args.aceitar_provisoria:
            parser.error(f"a previsão de partida (corte {previsao.corte}) não está congelada")
    else:
        parser.error("--previsao ou --backtest é obrigatório com --parciais")
    noite = preparar(
        previsao,
        args.saida,
        backtest=args.backtest is not None,
        historico=args.historico,
        publicar=args.publicar,
        simulacoes=args.simulacoes,
    )
    cache = Path("data/cache/noite/parciais.json")
    with httpx.Client(
        timeout=httpx.Timeout(20.0), follow_redirects=True, headers={"User-Agent": USER_AGENT}
    ) as cliente:
        executar(
            noite,
            lambda: ler_parciais(args.parciais, cache, cliente),
            intervalo=args.intervalo,
            duracao=args.duracao,
        )


if __name__ == "__main__":
    main()
