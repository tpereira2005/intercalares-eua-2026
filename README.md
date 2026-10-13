# Intercalares EUA 2026

Plataforma de análise, acompanhamento e previsão das eleições intercalares dos Estados Unidos de 3 de novembro de 2026: voto antecipado com análise demográfica (com a idade como prioridade), previsões para a Câmara e o Senado, e resultados em tempo real na noite eleitoral.

Todo o site está em português de Portugal. Os dados vêm exclusivamente de fontes oficiais e gratuitas, e toda a infraestrutura funciona a custo zero.

## Estado

Fase 0 (fundações). O plano completo de desenvolvimento, com as fases e as decisões tomadas, está no ficheiro do projeto `plano-intercalares-2026.md` (versão 3).

## Arquitetura

```
Fontes oficiais ──▶ GitHub Actions (Python: recolha, validação, modelos)
                          │
                          ├──▶ Cloudflare D1 (snapshots) ──▶ Worker /api (cache) ──▶ browser
                          ├──▶ GitHub Pages (espelho de emergência) ───────────────▶ browser
                          └──▶ Repositório / Releases (histórico)
Cron da Cloudflare (1 min) ──▶ dispara e vigia os workflows do GitHub
```

Um único Worker da Cloudflare serve o site (export estático do Next.js, pedidos gratuitos e ilimitados) e a API em `/api/*`. Ver [docs/arquitetura.md](docs/arquitetura.md).

## Estrutura

| Pasta                | Conteúdo                                                                         |
| -------------------- | -------------------------------------------------------------------------------- |
| `apps/web`           | Site em Next.js (App Router, export estático), TypeScript estrito, Tailwind CSS  |
| `apps/edge`          | Cloudflare Worker em TypeScript (Hono): ficheiros estáticos, API ao vivo, cron   |
| `packages/contratos` | Tipos TypeScript gerados a partir dos contratos de dados                         |
| `schemas`            | Contratos de dados em pydantic, a única fonte de verdade, e o JSON Schema gerado |
| `pipeline`           | Pipeline de dados em Python: conectores, transformação, publicação, jobs         |
| `data`               | Dados de referência pequenos e o registo de proveniência                         |
| `docs`               | Arquitetura, contratos, implantação e registos de decisões                       |

## Requisitos

- Node.js 22 (ver `.nvmrc`) e pnpm 10 (`corepack enable`)
- [uv](https://docs.astral.sh/uv/), que instala automaticamente o Python 3.12

## Primeiros passos

```sh
pnpm install
uv sync --all-packages

pnpm dev                  # site em http://localhost:3000
pnpm build                # export estático e verificação do Worker
pnpm --filter @intercalares/edge dev   # Worker com o site e a API em http://localhost:8787
```

## Verificações

```sh
pnpm verificar            # ESLint, Prettier, tipos e testes TypeScript
uv run ruff check . && uv run ruff format --check . && uv run mypy && uv run pytest
pnpm contratos:gerar      # depois de alterar um contrato em schemas/
```

O CI corre tudo isto em cada pull request, confirma que os contratos gerados estão atualizados e procura segredos no histórico.

## Princípios

- **Custo zero.** Nenhum serviço pago e nenhum cartão associado a nenhum serviço.
- **Rigor e transparência.** Cada número leva à fonte e à metodologia; os modelos são validados com backtests simétricos e congelados antes da eleição.
- **Privacidade.** Os ficheiros individuais de eleitores são processados no pipeline e nunca entram no repositório; só se publicam agregados.
- **Feito de raiz.** Todo o código é escrito para este projeto.

Para contribuir (pessoas ou agentes), lê o [AGENTS.md](AGENTS.md).

## Licença

Código sob a licença [MIT](LICENSE). Os dados de terceiros mantêm as licenças das fontes, registadas em [data/PROVENIENCIA.md](data/PROVENIENCIA.md).
