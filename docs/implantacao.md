# Implantação

O Worker ainda não está publicado. Esta página descreve o que falta e como será feito, sempre a custo zero.

## Pré-requisitos (uma vez)

1. Criar uma conta gratuita na Cloudflare, **sem associar cartão**.
2. Criar um token de API com permissões mínimas: _Workers Scripts: Edit_ e _D1: Edit_, limitado à conta.
3. Guardar no repositório, em _Settings → Secrets and variables → Actions_:
   - `CLOUDFLARE_API_TOKEN` (segredo)
   - `CLOUDFLARE_ACCOUNT_ID` (variável)
4. Criar a base de dados: `pnpm --filter @intercalares/edge exec wrangler d1 create intercalares-eua-2026` e substituir o `database_id` marcador em `apps/edge/wrangler.jsonc`.

## Publicação

Será feita por um workflow do GitHub Actions a cada integração no `main`, depois de o CI passar:

```sh
pnpm build
pnpm --filter @intercalares/edge exec wrangler d1 migrations apply intercalares-eua-2026 --remote
pnpm --filter @intercalares/edge exec wrangler deploy
```

O site fica em `https://intercalares-eua-2026.<subdomínio>.workers.dev`.

## Desenvolvimento local

```sh
pnpm build
pnpm --filter @intercalares/edge dev
```

O `wrangler dev` simula localmente o Worker, os ficheiros estáticos, os cabeçalhos de `_headers` e a D1. Variáveis locais ficam em `apps/edge/.dev.vars` (ignorado pelo git).
