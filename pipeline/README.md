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
    ├── referencia_voto_antecipado_nc.py   # cubos de 2018, 2022 e 2024 (uma vez)
    ├── voto_antecipado_estado.py          # Pensilvânia e Maine
    ├── referencia_voto_antecipado_estado.py
    ├── voto_antecipado_fl.py              # Florida (arquivo diário próprio)
    └── voto_antecipado_nacional.py        # resumo para a página inicial
```

O fluxo é igual para todos os estados e anos: o conector produz um **painel** (uma linha por eleitor recenseado, só em memória ou em `data/cache/`), que se agrega em **cubos** de contagens sem dados pessoais. Os indicadores (composição, participação, decomposição, esperado, histórico, reserva, geografia e cruzamentos) calculam-se sobre os cubos, e o resultado é validado pelo contrato `VotoAntecipadoEstado`.

Os cubos dos anos de referência estão versionados em `data/reference/nc/` (ver `data/PROVENIENCIA.md`). Para os reconstruir é preciso descarregar cerca de 5 GB:

```sh
uv run python -m pipeline.jobs.referencia_voto_antecipado_nc --anos 2018 2022 2024
uv run python -m pipeline.jobs.voto_antecipado_nc --saida data/publicado/voto-antecipado/nc.json
```

`--sem-descarga` reutiliza os ficheiros já presentes em `data/brutos/nc/`.

### Outros estados e resumo nacional

Pensilvânia e Maine publicam um registo por boletim (sem ficheiro de eleitores) e a Florida só totais diários por condado. Usam o contrato `VotoAntecipadoAgregado` e o mesmo fluxo de cubos (`transform/early_vote/agregado.py`); o resumo da página inicial (`VotoAntecipadoNacional`) cita os ficheiros de cada estado. Detalhes e limites em `docs/metodologia/voto-antecipado-estados.md`.

```sh
uv run python -m pipeline.jobs.referencia_voto_antecipado_estado --estado PA   # cubos de referência
uv run python -m pipeline.jobs.voto_antecipado_estado --estado PA --saida data/publicado/voto-antecipado/pa.json
uv run python -m pipeline.jobs.voto_antecipado_fl --saida data/publicado/voto-antecipado/fl.json \
  --arquivo data/publicado/voto-antecipado/historico-fl-2026.csv
uv run python -m pipeline.jobs.voto_antecipado_nacional --pasta data/publicado/voto-antecipado
```

## Comandos

```sh
uv sync --all-packages
uv run pytest pipeline/tests
uv run ruff check pipeline && uv run mypy
```
