# Arquitetura

Resumo técnico da plataforma. As razões de cada escolha estão em [decisoes/](decisoes/).

## Componentes

| Componente    | Tecnologia                                                                | Onde                            | Papel                                                               |
| ------------- | ------------------------------------------------------------------------- | ------------------------------- | ------------------------------------------------------------------- |
| Site          | Next.js (App Router, `output: "export"`), React, TypeScript, Tailwind CSS | `apps/web`                      | Páginas estáticas em PT-PT, reconstruídas quando os dados mudam     |
| Worker        | Cloudflare Workers, Hono                                                  | `apps/edge`                     | Serve os ficheiros estáticos, a API `/api/*` e o cron de vigilância |
| Base de dados | Cloudflare D1                                                             | binding `DB`                    | Snapshots correntes para a API ao vivo                              |
| Pipeline      | Python 3.12, httpx, polars, pydantic                                      | `pipeline`                      | Recolha, validação, transformação e publicação no GitHub Actions    |
| Contratos     | pydantic → JSON Schema → TypeScript                                       | `schemas`, `packages/contratos` | Formato único dos dados entre Python e TypeScript                   |
| Espelho       | GitHub Pages                                                              | (Fase 3)                        | Snapshot de emergência se a API atingir o limite diário             |

## Pedidos

O Worker usa o mecanismo de ficheiros estáticos da Cloudflare com `run_worker_first: ["/api/*"]`:

- Tudo o que não é `/api/*` é servido diretamente como ficheiro estático, sem executar código e sem contar para o limite de 100 000 pedidos diários do plano gratuito.
- `/api/*` executa a aplicação Hono (`apps/edge/src/app.ts`), que responde em JSON com cabeçalhos de segurança e cache explícita.
- Os cabeçalhos de segurança das páginas (CSP, HSTS e outros) estão em `apps/web/public/_headers`.

## Fluxo de dados

1. O cron da Cloudflare (a cada minuto) dispara e vigia os workflows de recolha do GitHub, que têm atrasos frequentes no agendamento próprio.
2. O pipeline descarrega as fontes com pedidos condicionais, valida-as contra os contratos e calcula os agregados.
3. Os resultados vão para a D1 (dados correntes), para o repositório ou as Releases (histórico) e, a partir da Fase 3, para o espelho.
4. O browser lê a API com atualização periódica; as páginas em si nunca dependem da API para carregar.

### Voto antecipado no site

As páginas `/`, `/mapa` e `/voto-antecipado/<uf>/` são geradas no build a partir dos ficheiros `VotoAntecipadoEstado` que o pipeline publica numa Release pública fixa do repositório (`dados-voto-antecipado`), um por estado (`nc.json`, `ga.json`, ...):

1. `pnpm --filter @intercalares/web dados:obter` lista a Release e descarrega cada ficheiro de estado para `apps/web/dados/voto-antecipado/` (ignorado pelo git). `URL_DADOS_VOTO_ANTECIPADO` aceita outras origens separadas por vírgulas (endereços ou ficheiros locais).
2. No build, `lib/voto-antecipado/carregar.ts` valida cada ficheiro contra `schemas/json/contratos.schema.json`. Um ficheiro inválido faz falhar o build; sem ficheiros, as páginas mostram "em preparação". `DADOS_VOTO_ANTECIPADO` muda a pasta lida.
3. `lib/voto-antecipado/vista.ts` reduz cada ficheiro ao que os gráficos mostram (cerca de 70 KB), sem metodologia nova: os indicadores vêm calculados pelo pipeline (`docs/metodologia/voto-antecipado.md`).

Os testes usam `apps/web/test/fixtures/voto-antecipado-sintetico.json`, gerado com eleitores aleatórios por `apps/web/test/fixtures/gerar.py`; esse ficheiro nunca é publicado no site.

Um estado novo só precisa de publicar o seu ficheiro na Release: ganha uma página, um quadrado colorido no mapa e uma linha em "Estados acompanhados" no início, sem alterações no site.

## Limites do plano gratuito

| Recurso                              | Limite                                                 | Comportamento ao exceder                |
| ------------------------------------ | ------------------------------------------------------ | --------------------------------------- |
| Ficheiros estáticos                  | Ilimitados                                             | Não se aplica                           |
| Pedidos ao Worker                    | 100 000 por dia (reposição à meia-noite UTC)           | Erro até à reposição; nunca há cobrança |
| D1                                   | 5 GB, 100 000 escritas e 5 milhões de leituras por dia | Erro até à reposição                    |
| GitHub Actions (repositório público) | Minutos ilimitados, 6 h por job                        | Jobs em fila                            |

Nenhum serviço tem cartão associado, por isso não há risco de cobrança.
