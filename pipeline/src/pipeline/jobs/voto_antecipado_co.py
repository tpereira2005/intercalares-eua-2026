"""Atualiza o voto antecipado do Colorado (folhas diárias do Secretary of State).

Uso::

    uv run python -m pipeline.jobs.voto_antecipado_co --saida data/publicado/voto-antecipado/co.json
    uv run python -m pipeline.jobs.voto_antecipado_co --referencia 2022 2024

Cada folha diária (ver ``pipeline.connectors.early_vote.co``) tem os totais acumulados por
faixa etária e partido, e por condado e partido, separados entre correio e presencial. A
série de 2026 junta todas as folhas publicadas até hoje; os anos de referência ficam em
``data/reference/co/idade_<ano>.csv`` e ``condados_<ano>.csv``, lidos das folhas de 2022 e
2024. Uma folha que falhe a validação fica de fora e as outras continuam: o ficheiro
publicado usa sempre a última folha válida.

Enquanto não houver nenhuma folha de 2026, o job avisa e termina sem escrever nada.
"""

import argparse
import logging
import time
from datetime import date, timedelta
from pathlib import Path

import httpx
import polars as pl

from contratos.base import Fonte
from contratos.estados import CodigoEstado
from contratos.voto_antecipado_agregado import VotoAntecipadoAgregado
from pipeline.comum.calendario import EleicaoGeral, eleicao_geral
from pipeline.comum.condados import nomes
from pipeline.comum.descarga import Descarga, descarregar
from pipeline.comum.erros import ErroDescarga, ErroFormatoFonte
from pipeline.connectors.early_vote.co import fontes
from pipeline.connectors.early_vote.co.ler import (
    ESQUEMA_CONDADOS,
    ESQUEMA_IDADE,
    Relatorio,
    ler_folha,
)
from pipeline.transform.early_vote import agregado

registo = logging.getLogger(__name__)

ANO = 2026
ANOS_BASE = (2022, 2024)
NOTAS = {2024: ("Eleição presidencial: comparar sobretudo o ritmo, não o nível.",)}
JANELA_DIAS = 30
"""Dias antes da eleição em que se procuram folhas (as primeiras saem a 14 ou 15 dias)."""

PAUSA = 0.5
"""Segundos entre pedidos à fonte."""

AVISOS = (
    "O Colorado envia o boletim por correio a todos os eleitores ativos: não há pedidos. "
    "Presencial: voto nos centros de voto do condado.",
    "Fonte: a folha de cálculo diária do Secretary of State (a mesma informação do resumo "
    "em PDF), com os boletins devolvidos até às 23h59 do dia anterior. Antes de publicar, "
    "conferimos que partidos, faixas, géneros e condados somam os totais da folha; uma "
    "folha que falhe fica de fora.",
    "Faixas etárias de dez anos, as da fonte (25-34, 35-44, 45-54, 55-64): não são as "
    "faixas dos outros estados, salvo 18-24, 65-74 e 75+.",
    "Os relatórios saem só nos dias úteis; ao fim de semana, a série repete o último.",
)


def eleicao(ano: int) -> EleicaoGeral:
    return eleicao_geral("CO", ano, NOTAS.get(ano, ()))


def pasta(raiz: Path, tipo: str) -> Path:
    return raiz / "data" / tipo / "co"


def _juntar(relatorios: list[Relatorio]) -> tuple[pl.DataFrame, pl.DataFrame]:
    idade = pl.concat([r.idade for r in relatorios]) if relatorios else None
    condados = pl.concat([r.condados for r in relatorios]) if relatorios else None
    return (
        idade if idade is not None else pl.DataFrame(schema=ESQUEMA_IDADE),
        condados if condados is not None else pl.DataFrame(schema=ESQUEMA_CONDADOS),
    )


def _ler(d: Descarga, dados_ate: date) -> Relatorio | None:
    try:
        return ler_folha(d.caminho, dados_ate)
    except ErroFormatoFonte as erro:
        registo.warning("Colorado: folha de %s recusada (%s)", dados_ate, erro)
        return None


def referencia(raiz: Path, anos: list[int]) -> None:
    """Lê as folhas diárias de cada ano de referência, até ao dia da eleição."""
    destino = pasta(raiz, "reference")
    destino.mkdir(parents=True, exist_ok=True)
    with httpx.Client(timeout=httpx.Timeout(60.0, read=300.0)) as cliente:
        for ano in anos:
            e = eleicao(ano)
            relatorios = []
            for i in range(JANELA_DIAS, -1, -1):
                dia = e.data - timedelta(days=i)
                for url in fontes.candidatos(dia):
                    caminho = pasta(raiz, "brutos") / str(ano) / url.rsplit("/", 1)[-1]
                    time.sleep(PAUSA)
                    try:
                        d = descarregar(url, caminho, cliente=cliente, tentativas=2)
                    except ErroDescarga:
                        continue
                    if (r := _ler(d, dia)) is not None:
                        relatorios.append(r)
                    break
            idade, condados = _juntar(relatorios)
            idade.write_csv(destino / f"idade_{ano}.csv")
            condados.write_csv(destino / f"condados_{ano}.csv")
            registo.info("Colorado %s: %s folhas", ano, len(relatorios))


def ler_referencia(raiz: Path, ano: int) -> tuple[pl.DataFrame, pl.DataFrame] | None:
    idade = pasta(raiz, "reference") / f"idade_{ano}.csv"
    condados = pasta(raiz, "reference") / f"condados_{ano}.csv"
    if not (idade.exists() and condados.exists()):
        return None
    return (
        pl.read_csv(idade, schema=ESQUEMA_IDADE),
        pl.read_csv(condados, schema=ESQUEMA_CONDADOS),
    )


def folhas_2026(raiz: Path, cliente: httpx.Client) -> list[tuple[Descarga, Relatorio]]:
    """Todas as folhas válidas de 2026, pelos comunicados da página de imprensa.

    Os comunicados e as folhas ficam em ``data/brutos/co/2026`` e voltam a pedir-se com
    pedidos condicionais, por isso uma execução sem novidades quase só recebe 304.
    """
    brutos = pasta(raiz, "brutos") / str(ANO)
    indice = descarregar(fontes.INDICE, brutos / "index.html", cliente=cliente)
    html = indice.caminho.read_text(encoding="utf-8", errors="replace")
    validas: dict[date, tuple[Descarga, Relatorio]] = {}
    for url in fontes.comunicados(html, eleicao(ANO).data):
        time.sleep(PAUSA)
        try:
            pagina = descarregar(url, brutos / url.rsplit("/", 1)[-1], cliente=cliente)
            texto = pagina.caminho.read_text(encoding="utf-8", errors="replace")
            folha = fontes.folha_do_comunicado(texto, url)
            dados_ate = fontes.data_da_folha(folha) if folha else None
            if folha is None or dados_ate is None:
                continue
            time.sleep(PAUSA)
            d = descarregar(folha, brutos / folha.rsplit("/", 1)[-1], cliente=cliente)
        except ErroDescarga as erro:
            registo.warning("Colorado: %s falhou (%s)", url, erro)
            continue
        if (r := _ler(d, dados_ate)) is not None:
            validas[dados_ate] = (d, r)
    return [validas[k] for k in sorted(validas)]


def montar(
    atual: tuple[pl.DataFrame, pl.DataFrame],
    bases: dict[int, tuple[pl.DataFrame, pl.DataFrame]],
    fontes_: list[Fonte],
    avisos_extra: list[str],
) -> VotoAntecipadoAgregado:
    anos = [a for a in ANOS_BASE if a in bases]
    avisos = list(AVISOS) + avisos_extra
    em_falta = [a for a in ANOS_BASE if a not in bases]
    if em_falta:
        avisos.append(
            f"Sem comparação com {', '.join(map(str, em_falta))}: retratos de referência em falta."
        )
    idade, condados = atual
    dados_ate: date = idade["dados_ate"].max()  # type: ignore[assignment]
    return agregado.montar(
        estado=CodigoEstado.CO,
        atual=agregado.cubos_de_retratos(idade, eleicao(ANO)),
        bases=[agregado.cubos_de_retratos(bases[a][0], eleicao(a)) for a in anos],
        dados_ate=dados_ate,
        dimensoes=("faixa", "partido", "modalidade", "condado"),
        modalidades=("correio", "presencial"),
        fontes=fontes_,
        nomes_condados=nomes("CO"),
        avisos=avisos,
        granularidade="condado",
        geografia_de=[
            agregado.cubos_de_retratos(condados, eleicao(ANO)),
            *(agregado.cubos_de_retratos(bases[a][1], eleicao(a)) for a in anos),
        ],
    )


def _fonte(d: Descarga) -> Fonte:
    return Fonte(nome=fontes.NOME_FONTE, url=d.url, licenca=fontes.LICENCA, obtida_em=d.obtido_em)


def executar(raiz: Path, saida: Path) -> bool:
    """Escreve ``saida``; devolve ``False`` (sem escrever) se ainda não há folhas de 2026."""
    bases = {a: t for a in ANOS_BASE if (t := ler_referencia(raiz, a)) is not None}
    with httpx.Client(timeout=httpx.Timeout(60.0, read=300.0)) as cliente:
        try:
            validas = folhas_2026(raiz, cliente)
        except ErroDescarga as erro:
            registo.warning("Colorado: sem a página de imprensa (%s)", erro)
            return False
    if not validas:
        registo.warning("Colorado: ainda sem folhas válidas de %s", ANO)
        return False
    ultima, _ = validas[-1]
    publicado = montar(_juntar([r for _, r in validas]), bases, [_fonte(ultima)], [])
    saida.parent.mkdir(parents=True, exist_ok=True)
    saida.write_text(publicado.model_dump_json(), encoding="utf-8")
    registo.info(
        "Escrito %s: dados até %s (%s dias antes), %s votos",
        saida,
        publicado.dados_ate,
        publicado.dias_antes,
        publicado.ciclos[0].votos,
    )
    return True


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--raiz", type=Path, default=Path.cwd(), help="raiz do repositório")
    parser.add_argument("--saida", type=Path, help="ficheiro JSON a escrever")
    parser.add_argument(
        "--referencia", type=int, nargs="+", help="reconstruir os retratos destes anos"
    )
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    if args.referencia:
        referencia(args.raiz, args.referencia)
    if args.saida:
        executar(args.raiz, args.saida)


if __name__ == "__main__":
    main()
