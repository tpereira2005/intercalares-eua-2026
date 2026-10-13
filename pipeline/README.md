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

## Comandos

```sh
uv sync --all-packages
uv run pytest pipeline/tests
uv run ruff check pipeline && uv run mypy
```
