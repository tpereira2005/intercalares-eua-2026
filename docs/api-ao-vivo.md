# API ao vivo da noite eleitoral

Os workflows da noite (`resultados.yml` e `noite.yml`) publicam a contagem e a projeção nas Releases do GitHub a cada 30 segundos, mas não voltam a implantar o site. Os dados chegam ao browser pela API do Worker.

## Pontos de acesso

| Caminho           | Ficheiros (variáveis em `apps/edge/wrangler.jsonc`)                                                                | Contrato                                                 |
| ----------------- | ------------------------------------------------------------------------------------------------------------------ | -------------------------------------------------------- |
| `/api/resultados` | `URL_PARCIAIS`, `URL_CHAMADAS` e `URL_SAUDE`: `resultados-2026/parciais.json`, `chamadas-2026.json` e `saude.json` | `ResultadosParciais`, `ChamadasRedacoes`, `SaudeRecolha` |
| `/api/noite`      | `URL_PROJECAO_NOITE` e `URL_HISTORICO_NOITE`: `dados-noite/projecao-noite-2026.json` e `historico-noite-2026.json` | `ProjecaoNoite`, `HistoricoNoite`                        |
| `/api/ao-vivo`    | os cinco ficheiros anteriores, num só pedido (o que o site usa)                                                    | os cinco                                                 |

Resposta `200`: `{"origem", "confirmadoEm", "parciais", "chamadas", "saude"}` ou `{"origem", "confirmadoEm", "projecao", "historico"}`, com os ficheiros tal como a fonte os publicou. `historico`, `chamadas` e `saude` são `null` quando faltam. `saude` é o estado da recolha por estado, publicado por Dados; o site usa-o para dizer que a fonte de um estado está atrasada (só a hora da última alteração, nunca o erro técnico). Não confundir com `/api/saude`, a verificação do próprio Worker. `origem` (também no cabeçalho `X-Origem`) é `fonte` (acabado de confirmar), `memoria` (confirmado há menos de 20 s) ou `copia-antiga` (a fonte falhou; serve-se a última cópia válida). `confirmadoEm` é a última vez que a fonte confirmou o ficheiro.

Sem ficheiro publicado: `404`. Fonte em baixo e nenhuma cópia: `503`.

### `/api/ao-vivo`

Corpo `200`: `{"resultados": <corpo de /api/resultados ou null>, "noite": <corpo de /api/noite ou null>, "intervaloS": 60}`. Cada parte é exatamente o que a rota própria devolveria (os textos dos ficheiros não são serializados de novo) e fica `null` se essa parte ainda não existe. Estado: `200` se pelo menos uma parte tem dados; `404` se nenhuma foi publicada; `503` nos restantes casos (fonte em baixo sem cópia). `Cache-Control: public, max-age=15` no `200`; `X-Origem` é a pior das duas origens (`memoria` < `fonte` < `copia-antiga`).

`intervaloS` é o intervalo de consulta sugerido ao browser, em segundos. Vem da variável do Worker `INTERVALO_S` (em `apps/edge/wrangler.jsonc`, `"60"`), limitada a 30-600; em falta ou inválida dá 60. Subir para 120 fora dos picos duplica a capacidade em leitores (ver [teste-carga-noite.md](teste-carga-noite.md)) sem nova implantação do site, só do Worker. `/api/resultados` e `/api/noite` mantêm-se para o espelho e para clientes antigos.

## Como funciona

- **Cache.** Cada isolate do Worker guarda em memória a última cópia válida de cada ficheiro e só volta à fonte passados 20 segundos, com `If-None-Match` e `If-Modified-Since` e o User-Agent `Escrutinio/0.1`. Pedidos simultâneos partilham uma só ida à fonte. As respostas levam `Cache-Control: public, max-age=15`. Não se usa a Cache API da Cloudflare: não funciona em `*.workers.dev`.
- **Validação.** Cada ficheiro novo é validado contra o esquema dos contratos antes de ser servido; um ficheiro inválido nunca chega ao browser e fica a cópia anterior. Como os Workers não permitem `eval`, os validadores do ajv são gerados antes, em `apps/edge/src/gerado/validadores.js` (`pnpm --filter @intercalares/edge validadores:gerar` depois de `pnpm contratos:gerar`; um teste falha se estiverem desatualizados).
- **Cópia antiga sem esperar (stale-while-revalidate).** Passados os 20 segundos, o pedido à fonte (limite de 4 s) é renovado em segundo plano: se já há cópia, a resposta espera no máximo 1,5 s pela renovação e, se ela não chegar, sai com a cópia que expirou (`memoria`, ou `copia-antiga` se a última tentativa falhou) enquanto a renovação continua com `ctx.waitUntil`. Sem nenhuma cópia, espera pela fonte. Assim uma fonte pendurada já não atrasa 7 s os visitantes.
- **Falhas.** Uma fonte que falha não volta a ser consultada antes de 20 segundos, para não receber um pedido por visita.
- **Browser.** A página `/resultados` mostra primeiro o retrato incluído no build. Depois consulta `/api/ao-vivo` (um só pedido) logo ao abrir e ao ritmo de `intervaloS` (60 segundos por omissão, entre 30 s e 10 min), com variação aleatória de ±10 %, só com o separador visível, e reconstrói as vistas com as mesmas funções do build (`lib/ao-vivo/estado.ts`). Se a API falhar (erro, limite atingido ou sem rede), lê o espelho de emergência (ver abaixo); se também falhar, fica o que está no ecrã e a página diz de que hora é. Enquanto a consulta falha ou só o espelho responde, o intervalo duplica a cada falha seguida até 5 minutos e volta ao normal quando a API responde. Enquanto a API responder `404` (antes da noite), consulta a cada 10 minutos.

## Limites do plano gratuito

O plano gratuito dos Workers dá 100 000 pedidos por dia ao código do Worker e 10 ms de CPU por pedido. Os ficheiros estáticos não contam. Cada visitante com a página da noite aberta faz 1 pedido por minuto (60 por hora), o que chega para cerca de 1 666 horas de visita por dia. Se o limite for ultrapassado, a API deixa de responder até à meia-noite UTC e a página passa para o espelho de emergência, com um aviso discreto. A CPU só pesa quando um ficheiro muda: ler e validar a projeção (160 KB) leva cerca de 2 ms. O ensaio de carga, as contas do orçamento (cerca de 208 leitores simultâneos durante toda a noite, o dobro com `INTERVALO_S=120`) e as propostas de mitigação estão em [teste-carga-noite.md](teste-carga-noite.md).

## Chamadas das redações

O Escrutínio não declara vencedores. Quando uma redação chama uma corrida, regista-se à mão em GitHub > Actions > "Chamadas das redações" > Run workflow (também funciona na aplicação do GitHub no telemóvel), com a corrida tal como aparece na previsão (`PA-07`, `OH-S-especial`), o lado, a redação, a ligação para a página da chamada e, se possível, a hora publicada. A mesma ação, com "retirar", apaga uma chamada. O workflow confirma que a corrida existe na previsão e que o ficheiro cumpre o contrato `ChamadasRedacoes` antes de o publicar em `resultados-2026/chamadas-2026.json`; a página mostra-o no minuto seguinte, ao lado da contagem, com a ligação para a fonte.

## Espelho de emergência

O workflow `espelho-noite.yml` corre a cada 10 minutos entre 3 e 10 de novembro (UTC) e à mão. Descarrega os mesmos ficheiros das Releases, valida-os contra os contratos e publica no GitHub Pages, na forma das respostas da API e com `origem: "espelho"`:

- `https://tpereira2005.github.io/intercalares-eua-2026/espelho/resultados.json`
- `https://tpereira2005.github.io/intercalares-eua-2026/espelho/noite.json`

Publica sempre também `espelho/estado.json`, com a hora da cópia e os ficheiros incluídos. Antes da noite é o único ficheiro, e serve para confirmar que o Pages está a funcionar.

O browser só lá vai quando a API falha; um `404` da API (nada publicado) não conta como falha. O Pages serve os ficheiros com `Access-Control-Allow-Origin: *` e não tem limite de pedidos que se aplique aqui. A variável `NEXT_PUBLIC_URL_ESPELHO`, no build, troca o endereço.

Requer o Pages ativo, com a origem "GitHub Actions" (Settings > Pages). Para montar a cópia localmente:

```sh
cd apps/web
node --experimental-strip-types scripts/espelho-noite.ts <pasta-com-os-ficheiros> <saida>
```

## Ensaio local

Com o site construído (`pnpm --filter @intercalares/web build`):

```sh
cd apps/edge
R=https://github.com/tpereira2005/intercalares-eua-2026/releases/download/dados-noite
pnpm exec wrangler dev --var URL_PROJECAO_NOITE:$R/projecao-noite-2024.json \
  --var URL_HISTORICO_NOITE:$R/historico-noite-2024.json
```

e abrir `/resultados/`: a linha por baixo do retrato passa de "A procurar dados mais recentes" para "Atualiza sozinha a cada minuto".
