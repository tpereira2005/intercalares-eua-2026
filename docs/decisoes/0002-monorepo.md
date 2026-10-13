# 0002. Monorepo com pnpm e uv

- Estado: aceite
- Data: 13 de outubro de 2026

## Decisão

Um único repositório com dois espaços de trabalho:

- **pnpm** (Node 22) para `apps/web`, `apps/edge` e `packages/*`. TypeScript 6 em modo estrito, ESLint 10 com `typescript-eslint`, Prettier, Vitest.
- **uv** (Python 3.12) para `schemas` e `pipeline`, com `ruff`, `mypy --strict` e `pytest`. Os modelos (Fase 2) entram como novo membro.

Os contratos de dados são definidos uma vez em pydantic e gerados para TypeScript (ver `docs/contratos.md`).

## Porquê

- Uma alteração a um contrato, ao pipeline e ao site revê-se e testa-se num único PR.
- Ferramentas nativas de cada linguagem, rápidas e com ficheiros de bloqueio reprodutíveis.
- Sem orquestrador de builds (Turborepo, Nx): o `pnpm -r` em ordem topológica chega para o tamanho atual.

## Notas

- O TypeScript fica na versão 6 porque o `typescript-eslint` ainda não suporta a 7.
- O Worker depende do pacote do site para que o `pnpm -r build` gere o export estático antes de validar o Worker.
