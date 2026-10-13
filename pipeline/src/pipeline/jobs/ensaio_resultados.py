"""Ensaio geral da noite eleitoral com os resultados oficiais de 2022 e 2024.

Uso::

    uv run python -m pipeline.jobs.ensaio_resultados --estado NC --data 2022-11-08

Descarrega os ficheiros finais da eleição indicada (no formato que a fonte usa na noite),
reconstrói uma noite com ``--passos`` retratos (ver ``ensaio.progressao``) e passa cada
retrato pela mesma montagem e validação da recolha ao vivo. Falha se:

- algum retrato não validar contra o contrato;
- algum total descer entre retratos (``ensaio.verificar_sequencia``);
- o último retrato não coincidir com o resultado oficial lido diretamente;
- um passo demorar mais de ``--orcamento`` segundos (o ciclo real tem 30 s para tudo).

Com ``--parciais PASTA`` escreve também os instantes no formato do estimador ao vivo
(``instantes/0001.json``... e ``final.json``, contrato ``ResultadosParciais``), marcados
como reconstruídos, para a repetição do Modelo C.
"""

import argparse
import logging
import sys
import time
from datetime import UTC, date, datetime, timedelta
from datetime import time as hora
from pathlib import Path
from zoneinfo import ZoneInfo

import httpx

from contratos.base import Fonte
from contratos.estados import CodigoEstado
from pipeline.comum.descarga import USER_AGENT, contexto_tls, descarregar, obter_texto
from pipeline.connectors.results.registo import CONECTORES, DISTRITOS, nomes_geo
from pipeline.transform.resultados import ensaio
from pipeline.transform.resultados.montar import montar, nacional
from pipeline.transform.resultados.parciais import montar_parciais

FECHO_URNAS = hora(19, 30)
"""Hora (costa leste) do primeiro retrato reconstruído; os seguintes vêm de 10 em 10 min."""

registo = logging.getLogger(__name__)


def executar(
    estado: CodigoEstado,
    data: date,
    pasta: Path,
    *,
    passos: int,
    orcamento: float,
    descarregar_: bool = True,
    parciais: Path | None = None,
) -> list[str]:
    conector = CONECTORES[estado]
    fonte_url = "https://example.invalid/"
    if descarregar_:
        with httpx.Client(
            timeout=60,
            follow_redirects=True,
            headers={"User-Agent": USER_AGENT},
            verify=contexto_tls(),
        ) as cliente:

            def obter(url: str) -> str:
                return obter_texto(cliente, url)

            pedidos = conector.pedidos(data, obter)
            for p in pedidos:
                descarregar(p.url, pasta / p.ficheiro, cliente=cliente)
            fonte_url = pedidos[0].url
    fonte = Fonte(
        nome=conector.nome_fonte,
        url=fonte_url,
        licenca=conector.licenca,
        obtida_em=datetime.now(UTC),
    )
    final = conector.ler(pasta, data)

    oficial = montar(
        estado=estado, data_eleicao=data, leitura=final, fontes=[fonte], nomes_geo=nomes_geo(estado)
    )
    falhas: list[str] = []
    distritos = {c.distrito for c in oficial.corridas if c.cargo == "camara"}
    # Nos estados com um só lugar, o distrito é 0 (``XX-00``).
    esperados = {0} if DISTRITOS[estado] == 1 else set(range(1, DISTRITOS[estado] + 1))
    em_falta = sorted(esperados - distritos)
    if em_falta and not final.cobertura_condados:
        registo.warning("%s: distritos sem corrida no feed: %s", estado, em_falta)
    retratos = []
    maximo = 0.0
    inicio_noite = datetime.combine(data, FECHO_URNAS, ZoneInfo("America/New_York"))
    for i, leitura in enumerate(ensaio.progressao(final, passos)):
        if parciais is not None:
            instante = inicio_noite + timedelta(minutes=10 * i)
            texto = montar_parciais(
                [leitura], ano=data.year, instante=instante, fontes=[fonte], reconstruido=True
            ).model_dump_json()
            (parciais / "instantes").mkdir(parents=True, exist_ok=True)
            (parciais / "instantes" / f"{i + 1:04d}.json").write_text(texto, encoding="utf-8")
            if i == passos - 1:
                (parciais / "final.json").write_text(texto, encoding="utf-8")
        inicio = time.monotonic()
        retrato = montar(
            estado=estado, data_eleicao=data, leitura=leitura, fontes=[fonte],
            nomes_geo=nomes_geo(estado),
        )  # fmt: skip
        retrato.model_dump_json()
        nacional([(retrato, f"{estado.value.lower()}.json")], data_eleicao=data).model_dump_json()
        gasto = time.monotonic() - inicio
        maximo = max(maximo, gasto)
        if gasto > orcamento:
            falhas.append(f"passo {i}: {gasto:.2f} s, acima do orçamento de {orcamento} s")
        retratos.append(retrato)
    falhas += [
        f"passo {p.indice} {p.corrida}: {p.descricao}" for p in ensaio.verificar_sequencia(retratos)
    ]
    ultimo = {c.id: (c.total, [x.votos for x in c.candidatos]) for c in retratos[-1].corridas}
    esperado = {c.id: (c.total, [x.votos for x in c.candidatos]) for c in oficial.corridas}
    if ultimo != esperado:
        falhas.append("o último retrato não coincide com o resultado oficial")
    registo.info(
        "%s %s: %s corridas, %s passos, passo mais lento %.3f s, %s votos no fim",
        estado,
        data,
        len(oficial.corridas),
        len(retratos),
        maximo,
        sum(c.total for c in oficial.corridas),
    )
    return falhas


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--estado", required=True)
    parser.add_argument("--data", type=date.fromisoformat, required=True)
    parser.add_argument("--pasta", type=Path, help="por omissão data/brutos/ensaio/<uf>/<data>")
    parser.add_argument("--passos", type=int, default=20)
    parser.add_argument("--orcamento", type=float, default=5.0)
    parser.add_argument("--sem-descarga", action="store_true")
    parser.add_argument("--parciais", type=Path, help="pasta para os instantes do Modelo C")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)
    estado = CodigoEstado(args.estado.upper())
    pasta = args.pasta or Path("data/brutos/ensaio") / estado.value.lower() / f"{args.data}"
    falhas = executar(
        estado,
        args.data,
        pasta,
        passos=args.passos,
        orcamento=args.orcamento,
        descarregar_=not args.sem_descarga,
        parciais=args.parciais,
    )
    for falha in falhas:
        registo.error(falha)
    sys.exit(1 if falhas else 0)


if __name__ == "__main__":
    main()
