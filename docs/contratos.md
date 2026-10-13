# Contratos de dados

Os contratos definem o formato de todos os dados trocados entre o pipeline (Python), a API e o site (TypeScript).

## Fonte de verdade

`schemas/src/contratos/` contém os modelos pydantic. Todos herdam de `ModeloContrato`, que:

- rejeita campos desconhecidos (uma mudança no formato de uma fonte falha na validação em vez de passar despercebida);
- torna os objetos imutáveis;
- exige datas com fuso horário.

Os docstrings dos campos passam para o JSON Schema e para os comentários dos tipos TypeScript.

## Geração

```sh
pnpm contratos:gerar
```

1. `python -m contratos.exportar` escreve `schemas/json/contratos.schema.json` (modo de serialização, determinístico).
2. `packages/contratos/scripts/gerar.mjs` converte-o em `packages/contratos/src/gerado/contratos.ts`.

Os ficheiros gerados são versionados. Um teste Python e um job do CI falham se estiverem desatualizados.

## Utilização

Python:

```python
from contratos import Fonte, Metadados
```

TypeScript:

```ts
import type { Fonte, Metadados } from "@intercalares/contratos";
```

## Versões

`VERSAO_ESQUEMA` (em `base.py`) segue o versionamento semântico e é gravada em cada ficheiro publicado (`Metadados.versao_esquema`). Sobe a versão maior quando uma alteração quebra leitores existentes.
