# Implantação

O site e a API são um único Worker da Cloudflare, no plano gratuito e **sem cartão**. A publicação é automática: o workflow `.github/workflows/implantacao.yml` corre depois de cada CI verde no `main` e de cada atualização dos dados do voto antecipado (a cada duas horas). Enquanto a conta não estiver ligada, o workflow é saltado sem erro.

## Ligar a conta (uma vez, cerca de 10 minutos)

1. Criar uma conta gratuita em <https://dash.cloudflare.com/sign-up>. Nenhum passo pede cartão; se algum ecrã pedir, não continuar e avisar.
2. No painel, abrir **Workers e Pages** uma vez e aceitar o subdomínio `workers.dev` proposto (gratuito). É aí que o site vai viver.
3. Copiar o **Account ID**, visível na coluna da direita de **Workers e Pages** (ou em _Account Home → ⋯ → Copy account ID_).
4. Criar um token em _My Profile → API Tokens → Create Token → Create Custom Token_, com:
   - _Account → Workers Scripts → Edit_
   - _Account → D1 → Edit_
   - _Account → Account Settings → Read_
   - _Account Resources_: só esta conta. Sem filtro de IP e com validade à escolha.
5. No GitHub, em _Settings → Secrets and variables → Actions_ do repositório:
   - separador **Secrets**: `CLOUDFLARE_API_TOKEN` com o token;
   - separador **Variables**: `CLOUDFLARE_ACCOUNT_ID` com o Account ID.
6. Em _Actions → Implantação → Run workflow_, correr a primeira publicação (ou esperar pela próxima integração).

O token fica só nos segredos do GitHub; nunca no repositório nem em mensagens.

## O que o workflow faz

```sh
pnpm --filter @intercalares/web dados:obter   # descarrega os ficheiros publicados
pnpm build                                     # valida os dados e gera o site estático
node apps/edge/scripts/preparar-d1.mjs         # cria a D1 na primeira vez e escreve o id
pnpm --filter @intercalares/edge exec wrangler d1 migrations apply intercalares-eua-2026 --remote
pnpm --filter @intercalares/edge exec wrangler deploy
```

O `database_id` em `apps/edge/wrangler.jsonc` fica como marcador no repositório: o script procura a base de dados `intercalares-eua-2026` na conta (ou cria-a) e substitui o marcador só na cópia de trabalho do workflow.

O site fica em `https://intercalares-eua-2026.<subdomínio>.workers.dev`. Ficheiros estáticos são gratuitos e ilimitados; o Worker só corre em `/api/*` e no cron, muito abaixo dos 100 000 pedidos diários do plano gratuito.

## Desenvolvimento local

```sh
pnpm --filter @intercalares/web dados:obter
pnpm build
pnpm --filter @intercalares/edge dev
```

O `wrangler dev` simula localmente o Worker, os ficheiros estáticos, os cabeçalhos de `_headers` e a D1. Variáveis locais ficam em `apps/edge/.dev.vars` (ignorado pelo git).
