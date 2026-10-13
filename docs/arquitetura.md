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

### Previsão no site

A página `/previsao/` lê dois ficheiros da Release `dados-previsao`, que o workflow Previsão substitui uma vez por dia até ao congelamento (1 de novembro de 2026):

1. `dados:obter` descarrega `previsao-2026.json` (contrato `PrevisaoCongresso`) e `historico-previsao-2026.json` (`HistoricoPrevisao`) para `apps/web/dados/previsao/2026.json` e `historico-2026.json`. `URL_DADOS_PREVISAO` e `URL_HISTORICO_PREVISAO` aceitam outras origens; `DADOS_PREVISAO` muda a pasta lida no build.
2. `lib/previsao/carregar.ts` valida os dois contra o esquema. Sem previsão, a página mostra "em preparação"; sem histórico, só o painel da evolução fica em preparação. Um ficheiro inválido faz falhar o build.
3. `lib/previsao/vista.ts` só seleciona e ordena: probabilidades, margens e intervalos vêm do modelo (`docs/metodologia/previsao.md`). As categorias de leitura (sólida, provável, inclinada, renhida) e o intervalo de 80% do ambiente nacional (t de Student com 5 graus de liberdade, como na simulação) são os únicos cálculos do site.

A implantação corre depois de cada execução bem-sucedida do workflow Previsão, para o site mostrar a atualização do dia. As tabelas de corridas são componentes de cliente para o HTML levar só os dados de cada linha; os distritos além dos 25 mais renhidos só se desenham quando se pedem.

### Noite eleitoral no site

A página `/resultados/` lê o retrato da contagem que a recolha da noite publica na Release `resultados-2026` (asset `parciais.json`, contrato `ResultadosParciais`; ver `docs/metodologia/resultados.md`):

1. `dados:obter` descarrega-o para `apps/web/dados/resultados/parciais.json`. `URL_DADOS_RESULTADOS` aceita outra origem; `DADOS_RESULTADOS` muda o ficheiro lido no build.
2. `lib/resultados/carregar.ts` valida-o contra o esquema. Sem ficheiro, a página mostra "em preparação"; um ficheiro inválido faz falhar o build.
3. `lib/resultados/vista.ts` soma os votos das unidades de cada corrida e calcula a margem contada, (D − R) / total, e as secções apuradas quando todas as unidades as indicam. Não há projeções nem chamadas de vencedor. Cada corrida aparece ao lado da previsão do mesmo identificador.
4. Cobertura ao vivo prevista: Carolina do Norte, Florida, Geórgia (só o total), Carolina do Sul e Iowa. As restantes corridas ao Senado e os distritos não sólidos aparecem numa tabela à parte, só com a previsão e a nota "sem dados ao vivo".
5. Um ficheiro de ensaio (`reconstruido: true`, ou de um ano diferente do da previsão) leva o selo "Ensaio" e um aviso, e não se cruza com a previsão de 2026.

A projeção do modelo (Release `dados-noite`, `projecao-noite-2026.json` e `historico-noite-2026.json`, contratos `ProjecaoNoite` e `HistoricoNoite`; ver `docs/metodologia/noite-eleitoral.md`) entra na mesma página:

1. `dados:obter` descarrega-os para `apps/web/dados/noite/projecao.json` e `historico.json` (`URL_PROJECAO_NOITE`, `URL_HISTORICO_NOITE`; `DADOS_NOITE` muda a pasta lida). `lib/noite/carregar.ts` valida-os.
2. O painel "Quem controla o Congresso" mostra, por câmara, a probabilidade de controlo, a previsão de partida, os lugares (mediana e intervalo de 80%), a distribuição e a evolução ao longo da noite. Nas tabelas, cada corrida mostra a probabilidade e a margem projetadas, com a previsão de partida por baixo.
3. Um ficheiro reconstruído (ensaio) ou que parte de uma previsão não congelada leva sempre selo e aviso. A projeção só se junta à contagem do mesmo ano e da mesma natureza. A página inicial mostra um destaque só com uma projeção real.

A forma de atualizar a página durante a noite (a cada 30 segundos) está por decidir: hoje, a página só muda quando o site é reconstruído.

### Cartões e SEO

Cada página declara título, descrição, endereço canónico e cartão para redes sociais com `lib/metadados.ts`. Os cartões (1200 × 630) são gerados no build por `app/cartoes/[cartao]/route.tsx` como `/cartoes/<nome>.png`, com as letras e as cores do sistema visual: início, secções, previsão (probabilidades de controlo) e um por estado do voto antecipado. Mudam a cada reconstrução, como as páginas. `robots.txt` e `sitemap.xml` também são gerados no build. O endereço do site vem de `lib/site.ts`; `URL_SITE` substitui-o quando houver um domínio próprio.

## Limites do plano gratuito

| Recurso                              | Limite                                                 | Comportamento ao exceder                |
| ------------------------------------ | ------------------------------------------------------ | --------------------------------------- |
| Ficheiros estáticos                  | Ilimitados                                             | Não se aplica                           |
| Pedidos ao Worker                    | 100 000 por dia (reposição à meia-noite UTC)           | Erro até à reposição; nunca há cobrança |
| D1                                   | 5 GB, 100 000 escritas e 5 milhões de leituras por dia | Erro até à reposição                    |
| GitHub Actions (repositório público) | Minutos ilimitados, 6 h por job                        | Jobs em fila                            |

Nenhum serviço tem cartão associado, por isso não há risco de cobrança.
