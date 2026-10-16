# Pipeline de dados

Pacote Python `pipeline` (Python 3.12, gerido pelo espaço de trabalho uv da raiz). Corre no GitHub Actions: recolhe as fontes oficiais, valida, transforma e publica os dados que o site e a API consomem.

## Organização

```
pipeline/
├── pyproject.toml
├── src/pipeline/
│   ├── connectors/
│   │   ├── early_vote/   # voto antecipado, um módulo por estado (nc.py, ga.py, ...)
│   │   ├── results/      # feeds oficiais de resultados, um módulo por estado
│   │   ├── polls/        # sondagens
│   │   └── fec/          # dados da FEC
│   ├── transform/        # limpeza, agregação, indicadores
│   ├── publish/          # escrita na D1, no espelho e no arquivo
│   └── jobs/             # pontos de entrada (python -m pipeline.jobs.<nome>)
└── tests/                # testes e ficheiros de exemplo (tests/fixtures/)
```

## Convenções

- Importações absolutas (`from pipeline.transform import ...`); o `ruff` proíbe importações relativas.
- Cada estado é um módulo independente com o mesmo contrato, para que acrescentar cobertura seja acrescentar módulos.
- Os dados publicados usam os contratos de `schemas/` (pacote `contratos`); validação com pydantic à entrada e à saída.
- Ficheiros descarregados vão para `data/brutos/` ou `data/cache/` na raiz (ignorados pelo git). Os ficheiros individuais de eleitores nunca são versionados; os ficheiros de exemplo nos testes são sintéticos ou anonimizados.
- Dependências novas acrescentam-se em `pipeline/pyproject.toml` com `uv add --package pipeline <pacote>`, que atualiza o `uv.lock` da raiz.

## Voto antecipado

Metodologia completa em [`docs/metodologia/voto-antecipado.md`](../docs/metodologia/voto-antecipado.md).

```
src/pipeline/
├── comum/                       # categorias, faixas etárias, calendário, leitura e descarga
├── connectors/early_vote/nc/    # Carolina do Norte: boletins, recenseamento, histórico
├── transform/early_vote/        # painel → cubos → indicadores → ficheiro publicado
└── jobs/
    ├── voto_antecipado_nc.py              # atualização de 2026 (a cada 2 h)
    ├── referencia_voto_antecipado_nc.py   # cubos de 2016, 2018, 2022 e 2024 (uma vez)
    ├── voto_antecipado_estado.py          # Pensilvânia e Maine
    ├── referencia_voto_antecipado_estado.py
    ├── voto_antecipado_fl.py              # Florida (arquivo diário próprio)
    ├── voto_antecipado_az.py              # Arizona (fonte não oficial; arquivo diário próprio)
    ├── voto_antecipado_uf.py              # GA, MI, OH, NV, TX via UF Election Lab (não oficial; arquivo diário próprio)
    ├── voto_antecipado_ia.py              # Iowa (PDF diários; --referencia para 2022 e 2024)
    ├── voto_antecipado_co.py              # Colorado (folhas diárias; --referencia para 2022 e 2024)
    └── voto_antecipado_nacional.py        # resumo para a página inicial
```

O fluxo é igual para todos os estados e anos: o conector produz um **painel** (uma linha por eleitor recenseado, só em memória ou em `data/cache/`), que se agrega em **cubos** de contagens sem dados pessoais. Os indicadores (composição, participação, decomposição, esperado, histórico, reserva, geografia e cruzamentos) calculam-se sobre os cubos, e o resultado é validado pelo contrato `VotoAntecipadoEstado`.

Os cubos dos anos de referência estão versionados em `data/reference/nc/` (ver `data/PROVENIENCIA.md`). Para os reconstruir é preciso descarregar cerca de 5 GB:

```sh
uv run python -m pipeline.jobs.referencia_voto_antecipado_nc --anos 2016 2018 2022 2024
uv run python -m pipeline.jobs.voto_antecipado_nc --saida data/publicado/voto-antecipado/nc.json
```

`--sem-descarga` reutiliza os ficheiros já presentes em `data/brutos/nc/`.

### Outros estados e resumo nacional

Pensilvânia e Maine publicam um registo por boletim (sem ficheiro de eleitores), a Florida só totais diários por condado o Iowa relatórios diários em PDF por distrito e condado e o Colorado folhas de cálculo diárias por idade, partido e condado. Usam o contrato `VotoAntecipadoAgregado` e o mesmo fluxo de cubos (`transform/early_vote/agregado.py`); o resumo da página inicial (`VotoAntecipadoNacional`) cita os ficheiros de cada estado. Detalhes e limites em `docs/metodologia/voto-antecipado-estados.md`.

A Geórgia, o Michigan, o Ohio, o Nevada e o Texas, cujos servidores oficiais bloqueiam pedidos automáticos, vêm do UF Election Lab (Universidade da Florida, Michael McDonald), uma fonte **não oficial** com atribuição: um só pedido por execução ao `US.csv` que as páginas do próprio laboratório usam (`connectors/early_vote/uf/`). O job escreve `<estado>.json` só para os estados que já têm votos e nunca para os que têm fonte própria (NC, PA, ME, FL, IA, CO, AZ). Cita a atribuição em `connectors/early_vote/uf/fontes.py`.

```sh
uv run python -m pipeline.jobs.referencia_voto_antecipado_estado --estado PA   # cubos de referência
uv run python -m pipeline.jobs.voto_antecipado_estado --estado PA --saida data/publicado/voto-antecipado/pa.json
uv run python -m pipeline.jobs.voto_antecipado_fl --saida data/publicado/voto-antecipado/fl.json \
  --arquivo data/publicado/voto-antecipado/historico-fl-2026.csv
uv run python -m pipeline.jobs.voto_antecipado_az --saida data/publicado/voto-antecipado/az.json \
  --arquivo data/publicado/voto-antecipado/historico-az-2026.csv
uv run python -m pipeline.jobs.voto_antecipado_uf --pasta data/publicado/voto-antecipado \
  --arquivo data/publicado/voto-antecipado/historico-uf-2026.csv
uv run python -m pipeline.jobs.voto_antecipado_nacional --pasta data/publicado/voto-antecipado
```

### Resultados da noite eleitoral

Conectores em `connectors/results/` (Carolina do Norte, Florida, Geórgia, Alasca, pelo sistema Clarity Carolina do Sul e Iowa, o condado de Harris no Texas e o de Maricopa no Arizona, com cobertura parcial, a Califórnia e Washington), contratos `ResultadosEstado`, `ResultadosNacional` e `ResultadosParciais` (entrada do Modelo C). Metodologia e limites em `docs/metodologia/resultados.md`.

```sh
uv run python -m pipeline.jobs.resultados --duracao 600            # recolha a cada 30 s
uv run python -m pipeline.jobs.vigia --saude data/publicado/resultados/saude.json  # alertas da noite
uv run python -m pipeline.jobs.ensaio_resultados --estado NC --data 2022-11-08 --parciais ensaio/nc-2022
uv run python -m pipeline.jobs.resultados_avaliacao --pasta data/publicado/resultados --saida resultados-2026.csv
```

## Previsão

Modelo próprio para a Câmara e o Senado (metodologia em [`docs/metodologia/previsao.md`](../docs/metodologia/previsao.md)) e projeção da noite eleitoral (Modelo C, em [`docs/metodologia/noite-eleitoral.md`](../docs/metodologia/noite-eleitoral.md)).

```text
src/pipeline/
├── modelo/
│   ├── fontes/          # Wikipédia (wikitexto, corridas, sondagens) e raw_polls.csv da 538
│   ├── dados.py         # corrida → linha do modelo (lados, independentes, corridas decididas)
│   ├── estimacao.py     # fundamentos e erro das sondagens, só com anos anteriores
│   ├── media.py         # média ponderada de sondagens
│   ├── simulacao.py     # Monte Carlo com erros nacionais, regionais e por corrida
│   ├── previsao.py      # orquestração (a mesma função serve 2026 e os backtests)
│   ├── publicar.py      # contrato PrevisaoCongresso e backtests
│   ├── verificacoes.py  # verificações de coerência antes de publicar
│   ├── historico.py     # histórico diário para os gráficos de evolução
│   ├── publicar_sondagens.py # sondagens e médias para a página de sondagens
│   ├── cenarios.py      # grelha de cenários do ambiente nacional (mesmo simulador)
│   ├── alteracoes.py    # registo público das alterações do método
│   ├── avaliacao.py     # scorecard da previsão congelada (Brier, log-loss, calibração)
│   ├── idade.py         # sinal etário do voto antecipado (diagnóstico, peso zero)
│   └── noite/           # Modelo C: corrida a corrida, ordem de contagem por modo, câmaras, histórico da noite e repetições
└── jobs/
    ├── previsao.py           # previsão de 2026 (diária até ao congelamento a 1 de novembro)
    ├── referencia_modelo.py  # tabelas de 2012 a 2024 em data/reference/modelo (uma vez)
    ├── referencia_noite.py   # presidenciais por condado (2020 e 2024) para o Modelo C
    ├── repeticao_noite.py    # repetição das noites de 2022 e 2024 com o Modelo C
    ├── projecao_noite.py     # Modelo C na noite eleitoral (e ensaio com 2024)
    ├── sensibilidade_previsao.py # análise de sensibilidade (uma escolha do modelo de cada vez)
    ├── idade_nc.py           # sinal etário da Carolina do Norte (docs/metodologia/idade.md)
    └── avaliacao_previsao.py # avaliação da previsão congelada (depois da eleição)
```

```sh
uv run python -m pipeline.jobs.referencia_modelo
uv run python -m pipeline.jobs.previsao --saida data/publicado/previsao/2026.json \
    --cenarios data/publicado/previsao/cenarios-2026.json \
    --sensibilidade data/publicado/previsao/sensibilidade-2026.json \
    --alteracoes data/publicado/previsao/alteracoes-2026.json
uv run python -m pipeline.jobs.ensaio_resultados --estado NC --data 2022-11-08 --parciais data/brutos/repeticao/NC-2022
uv run python -m pipeline.jobs.repeticao_noite --ano 2022 --ordem modos --parciais data/brutos/repeticao/NC-2022
uv run python -m pipeline.jobs.projecao_noite --ensaio data/brutos/repeticao/NC-2022 --saida data/publicado/noite
```

Na noite eleitoral, o workflow `noite.yml` corre `projecao_noite` em paralelo com a recolha de resultados e publica `projecao-noite-2026.json` e `historico-noite-2026.json` na Release `dados-noite` (ver a secção 6 de `docs/metodologia/noite-eleitoral.md`).

## Comandos

```sh
uv sync --all-packages
uv run pytest pipeline/tests
uv run ruff check pipeline && uv run mypy
```
