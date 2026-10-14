# API ao vivo da noite eleitoral

Os workflows da noite (`resultados.yml` e `noite.yml`) publicam a contagem e a projeção nas Releases do GitHub a cada 30 segundos, mas não voltam a implantar o site. Os dados chegam ao browser pela API do Worker.

## Pontos de acesso

| Caminho           | Ficheiros (variáveis em `apps/edge/wrangler.jsonc`)                                                                | Contrato                          |
| ----------------- | ------------------------------------------------------------------------------------------------------------------ | --------------------------------- |
| `/api/resultados` | `URL_PARCIAIS`: `resultados-2026/parciais.json`                                                                    | `ResultadosParciais`              |
| `/api/noite`      | `URL_PROJECAO_NOITE` e `URL_HISTORICO_NOITE`: `dados-noite/projecao-noite-2026.json` e `historico-noite-2026.json` | `ProjecaoNoite`, `HistoricoNoite` |

Resposta `200`: `{"origem", "confirmadoEm", "parciais"}` ou `{"origem", "confirmadoEm", "projecao", "historico"}`, com os ficheiros tal como a fonte os publicou. `historico` é `null` quando falta. `origem` (também no cabeçalho `X-Origem`) é `fonte` (acabado de confirmar), `memoria` (confirmado há menos de 20 s) ou `copia-antiga` (a fonte falhou; serve-se a última cópia válida). `confirmadoEm` é a última vez que a fonte confirmou o ficheiro.

Sem ficheiro publicado: `404`. Fonte em baixo e nenhuma cópia: `503`.

## Como funciona

- **Cache.** Cada isolate do Worker guarda em memória a última cópia válida de cada ficheiro e só volta à fonte passados 20 segundos, com `If-None-Match` e `If-Modified-Since` e o User-Agent `Escrutinio/0.1`. Pedidos simultâneos partilham uma só ida à fonte. As respostas levam `Cache-Control: public, max-age=15`. Não se usa a Cache API da Cloudflare: não funciona em `*.workers.dev`.
- **Validação.** Cada ficheiro novo é validado contra o esquema dos contratos antes de ser servido; um ficheiro inválido nunca chega ao browser e fica a cópia anterior. Como os Workers não permitem `eval`, os validadores do ajv são gerados antes, em `apps/edge/src/gerado/validadores.js` (`pnpm --filter @intercalares/edge validadores:gerar` depois de `pnpm contratos:gerar`; um teste falha se estiverem desatualizados).
- **Falhas.** Uma fonte que falha não volta a ser consultada antes de 20 segundos, para não receber um pedido por visita.
- **Browser.** A página `/resultados` mostra primeiro o retrato incluído no build. Depois consulta as duas rotas logo ao abrir e a cada 60 segundos, só com o separador visível, e reconstrói as vistas com as mesmas funções do build (`lib/ao-vivo/estado.ts`). Se a API falhar, fica o que está no ecrã e a página diz de que hora é. Enquanto a API responder `404` (antes da noite), consulta a cada 10 minutos.

## Limites do plano gratuito

O plano gratuito dos Workers dá 100 000 pedidos por dia ao código do Worker e 10 ms de CPU por pedido. Os ficheiros estáticos não contam. Cada visitante com a página da noite aberta faz 2 pedidos por minuto (120 por hora), o que chega para cerca de 800 horas de visita por dia. Se o limite for ultrapassado, a API deixa de responder até à meia-noite UTC, e a página continua a mostrar o último retrato que recebeu (ou o do build). A CPU só pesa quando um ficheiro muda: ler e validar a projeção (160 KB) leva cerca de 2 ms.

## Ensaio local

Com o site construído (`pnpm --filter @intercalares/web build`):

```sh
cd apps/edge
R=https://github.com/tpereira2005/intercalares-eua-2026/releases/download/dados-noite
pnpm exec wrangler dev --var URL_PROJECAO_NOITE:$R/projecao-noite-2024.json \
  --var URL_HISTORICO_NOITE:$R/historico-noite-2024.json
```

e abrir `/resultados/`: a linha por baixo do retrato passa de "A procurar dados mais recentes" para "Atualiza sozinha a cada minuto".
