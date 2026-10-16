# Teste de carga da noite eleitoral

Ensaio local do Worker (`apps/edge`) para a noite de 3 para 4 de novembro de 2026: quantos pedidos à fonte, como se comporta quando a fonte falha e quantos leitores cabem nos 100 000 pedidos diários do plano gratuito.

## Método

Script: `apps/edge/scripts/teste-carga.mjs` (só Node, sem dependências novas).

```sh
cd apps/edge
node scripts/teste-carga.mjs --browsers 500 --intervalo 60
```

O script arranca:

- uma **fonte falsa** local que serve os ficheiros de exemplo do site (`apps/web/test/fixtures/resultados/parciais.json` e `chamadas.json`, `noite/projecao.json` e `historico.json`), com `ETag` que muda de 30 em 30 s (200 e 304, como a publicação real) e modos `ok`, `500`, `429` e `pendurado` (nunca responde);
- o **Worker real** em `wrangler dev --local`, sem nada remoto, com as quatro variáveis `URL_*` apontadas para a fonte falsa;
- N **browsers simulados** com fase aleatória, cada um a pedir `/api/ao-vivo` a cada 60 s, como o site (`lib/ao-vivo/use-ao-vivo.ts`).

O tempo não é comprimido: os 20 s de frescura, os 4 s de limite do pedido à fonte e os 1,5 s de espera máxima do Worker são os reais. O ensaio completo demora cerca de 8 minutos e termina com código 1 se alguma verificação falhar. Nada toca em serviços externos nem no Worker de produção.

Cenários:

0. **Arranque a frio com a fonte em baixo** (sem nenhuma cópia).
1. **Carga contínua**, 6 minutos, 500 browsers, com a fonte a mudar: 0-120 s boa, 120-180 s `500`, 180-240 s `429`, 240-300 s pendurada (o Worker serve a cópia antiga ao fim de 1,5 s), 300-360 s boa outra vez.
2. **Rajada**: os 500 browsers pedem `/api/ao-vivo` no mesmo instante, três vezes (simula o fecho das urnas e toda a gente a atualizar).

## Resultados medidos (500 browsers, uma execução)

> Medidos antes das propostas 1 a 4 abaixo: cada browser pedia `/api/resultados` e `/api/noite` (1 000 pedidos/min ao Worker) e o limite da fonte era de 8 s. O script já usa `/api/ao-vivo` e os novos limites; as tabelas de pedidos e de latência abaixo devem ser refeitas com uma nova execução; o orçamento de pedidos mais abaixo já está recalculado.

Máquina de ensaio: sandbox com `workerd` local e o cliente de teste na mesma máquina.

**Pedidos à fonte por minuto** (contados no servidor falso, 4 ficheiros):

| Minuto | Estado da fonte | Pedidos à fonte       | Pedidos ao Worker |
| ------ | --------------- | --------------------- | ----------------- |
| 1      | boa             | 10                    | ~1000             |
| 2      | boa             | 12 (8 × 200, 4 × 304) | ~1000             |
| 3      | 500             | 12                    | ~1000             |
| 4      | 429             | 12                    | ~1000             |
| 5      | pendurada       | 12                    | ~1000             |
| 6      | boa             | 8                     | ~1000             |

O limite teórico é 4 ficheiros × 3 por minuto = 12. Ficou em 12 com 500 browsers (1 000 pedidos/min ao Worker): **o consumo da fonte depende do tempo de frescura, não do número de clientes**. Na rajada, 1 000 pedidos simultâneos geraram exatamente 4 idas à fonte, nas três rondas.

**Falhas da fonte** (5 936 pedidos em 6 minutos):

- Todos responderam `200` com `Cache-Control: public, max-age=15` e os campos esperados.
- Com a fonte em `500`, `429` ou pendurada, 2 422 de 2 422 respostas vieram com `X-Origem: copia-antiga` e `confirmadoEm` parado na última confirmação boa. Nenhum cliente viu o erro.
- A fonte em erro é consultada uma vez por ficheiro a cada 20 s (12/min), nunca por visita.
- Quando a fonte voltou, todas as respostas seguintes vieram de `fonte` ou `memoria` (468 de 468).
- Arranque a frio com a fonte em `500`: `503` com `Cache-Control: no-store`; 21 s depois, com a fonte boa, recupera sozinho.

**Latência** (local; só serve para comparar fases, não é a de produção):

| Fase            | p50     | p95      | p99      | máx.     |
| --------------- | ------- | -------- | -------- | -------- |
| Fonte boa       | 13,5 ms | 382 ms   | 1 345 ms | 2 826 ms |
| Fonte em 500    | 12,2 ms | 25 ms    | 41 ms    | 55 ms    |
| Fonte em 429    | 13,0 ms | 23 ms    | 36 ms    | 66 ms    |
| Fonte pendurada | 17,6 ms | 7 014 ms | 7 945 ms | 8 301 ms |
| Todas (5 936)   | 13,6 ms | 513 ms   | 6 661 ms | 8 301 ms |

A cauda da "fonte boa" é o primeiro minuto (arranque a frio e primeiros descarregamentos). A cauda da "fonte pendurada" é real: os pedidos que chegam quando a cópia expira ficam à espera dos 8 s do limite antes de receberem a cópia antiga (ver propostas).

Rajada de 1 000 pedidos simultâneos: 4,6 a 7,4 s até o último responder (p50 3,2 a 5,7 s). Este valor é dominado pelo `workerd` local e pelo cliente de teste a abrir 1 000 ligações na mesma máquina; na Cloudflare os pedidos repartem-se por vários isolates. Serve para confirmar que nenhum pedido falha, não para prever tempos.

## Orçamento de pedidos

O que conta como pedido do Worker, com esta configuração (`apps/edge/wrangler.jsonc`): `assets.run_worker_first` é `["/api/*"]`, por isso só `/api/*` entra no código do Worker; os ficheiros estáticos do site (páginas, JS, CSS) são servidos pelos Workers Static Assets e, segundo a documentação da Cloudflare, não contam como pedidos do Worker no plano gratuito. Isto não se pode medir em local e ainda não foi confirmado no painel de produção. As idas à fonte (`fetch` para o GitHub) são subpedidos e não contam para os 100 000.

Contas, com 1 pedido por leitor por minuto (`/api/ao-vivo`, depois das propostas 1 a 4; antes eram 2, um por rota) e só com o separador visível:

- Um leitor gasta 60 pedidos por hora. Os 100 000 pedidos diários dão **1 666 horas de leitor por dia**.
- O contador diário zera às 00:00 UTC, no meio da noite. A janela das 23:00 UTC (3 de novembro) às ~08:00 UTC (4 de novembro) divide-se em 1 h no dia 3 e 8 h no dia 4. O dia 4 é o que aperta:

| Cenário (dia 4 de novembro, UTC)                  | Leitores simultâneos que cabem |
| ------------------------------------------------- | ------------------------------ |
| Constantes durante as 8 h (00:00 a 08:00)         | 208                            |
| Constantes durante as 4 h de pico (00:00 a 04:00) | 416                            |
| Constantes durante 1 h                            | 1 666                          |
| Visitantes de 30 min cada, ao longo do dia        | cerca de 3 330 visitantes      |

Com `INTERVALO_S=120` (um pedido a cada 2 minutos) tudo isto volta a duplicar: 416 leitores nas 8 h, 832 nas 4 h, 3 333 numa hora.

- Margem a descontar: a primeira consulta ao abrir a página, recarregamentos, `/api/saude` da monitorização e as consultas de 10 minutos antes de haver dados. Contar com 10 % a menos.
- O `Cache-Control: public, max-age=15` quase não poupa pedidos: o intervalo é de 60 s ou mais, por isso só ajuda recarregamentos e vários separadores do mesmo browser em menos de 15 s. Não se usa a Cache API (não funciona em `*.workers.dev`), e uma cache da Cloudflare à frente do Worker, no mesmo domínio, não evita a invocação.
- Ao passar o limite, a API deixa de responder até às 00:00 UTC e a página passa para o espelho do GitHub Pages (atualizado a cada 10 minutos). A noite não "cai", mas fica menos fresca.

Conclusão: com as regras atuais cabem **cerca de 200 leitores simultâneos durante toda a noite**, ou 400 a 450 se a atenção se concentrar nas primeiras 3 a 4 horas (o dobro com `INTERVALO_S=120`). Acima disso aplicam-se as propostas abaixo. Convém decidir antes do dia 3 qual a audiência esperada.

## Limites do ensaio

- A cache é por isolate. Na Cloudflare há vários isolates (por localização e por carga), cada um com a sua cópia, pelo que as idas à fonte são 12 por minuto **por isolate**, não no total. O ensaio local tem um só. Continua a não depender do número de leitores, mas não é um número único.
- A fonte falsa não reproduz o redirecionamento das Releases do GitHub (`objects.githubusercontent.com`) nem confirma que `If-None-Match` é respeitado aí; se não for, cada ida à fonte descarrega o ficheiro inteiro (160 KB na projeção), e a CPU de 10 ms por pedido deve ser confirmada em produção.
- A latência do `workerd` local e do cliente na mesma máquina não representa a rede real.
- Cada browser simulado começa com fase aleatória; o site real tem sincronização natural em torno do fecho das urnas e das chamadas, mais próxima da rajada.

## Propostas

1. **Uma só rota para a página da noite** (implementada): `GET /api/ao-vivo` devolve resultados e projeção juntos (`docs/api-ao-vivo.md`). Passa de 2 para 1 pedido por minuto e duplica a capacidade. `/api/resultados` e `/api/noite` mantêm-se para o espelho e para clientes antigos.
2. **Intervalo adaptativo** (implementada como _intervalo ajustável pela variável `INTERVALO_S` do Worker_): `/api/ao-vivo` devolve `intervaloS` (30 a 600, 60 por omissão) e o site segue-o. Fora dos picos, `INTERVALO_S=120` duplica outra vez a capacidade; muda-se no Worker, sem reconstruir o site.
3. **Espalhar e recuar** (implementada): variação aleatória de ±10 % no intervalo e recuo exponencial (duplica a cada falha seguida, até 5 minutos) quando a API falha ou só o espelho responde, para não haver sincronização e para o espelho não levar uma rajada quando a quota acaba.
4. **Cópia antiga sem esperar** (_stale-while-revalidate_, implementada): com cópia em memória, o Worker espera no máximo 1,5 s pela renovação e serve a cópia que expirou, que continua a renovar-se com `ctx.waitUntil`; `LIMITE_PEDIDO_MS` desceu de 8 s para 4 s. Elimina a cauda de 7 s com a fonte pendurada (medida antes, no ensaio acima, com 8 s).
5. **Espelho como primeira escolha para parte dos visitantes** (por exemplo metade, por sorteio) quando a audiência passar das 100 pessoas. O Pages não tem a quota do Worker, mas só se atualiza a cada 10 minutos.
6. **Aviso de capacidade**: responder `429` com `Retry-After` perto da quota em vez de falhar de repente. Pede um contador, que o plano gratuito só dá com D1 ou KV.
7. **Confirmar em produção**, antes da noite, no painel da Cloudflare, que um carregamento de página não conta como pedido do Worker e que a Release responde 304 a `If-None-Match`.

Subir para o plano pago está fora de questão (ver "Custo zero" em `AGENTS.md`).

## Ensaio na Cloudflare

O ensaio local não mede a rede nem a cache reais. Para isso há o workflow manual **Ensaio de carga** (`.github/workflows/ensaio-carga.yml`), marcado para 28 de outubro com a thread de Dados, que publica a noite de 2024 numa Release de ensaio (`pipeline.jobs.ensaio_noite --manual`).

1. **implantar**: publica um segundo Worker, `intercalares-eua-2026-ensaio`, no mesmo subdomínio workers.dev e no plano gratuito. É o mesmo código e o mesmo site, mas sem cron nem D1, com `AMBIENTE=ensaio`, e lê `parciais.json`, `saude.json`, `chamadas-2026.json`, `projecao-noite-2024.json` e `historico-noite-2024.json` da Release indicada (por omissão `resultados-ensaio`, onde o Modelo publica também a projeção de ensaio; o ano dos nomes da projeção muda com `ano_noite`). A configuração é gerada por `apps/edge/scripts/configurar-ensaio.mjs`, que recusa a Release de produção.
2. **carga**: `apps/edge/scripts/carga-remota.mjs` simula N leitores com a página da noite aberta, cada um a pedir `/api/ao-vivo` uma vez por minuto, com fase aleatória. Calcula o total antes de começar e recusa-se a passar de 30 000 pedidos, porque o limite de 100 000 pedidos diários é da conta inteira e partilhado com a produção. Só aceita o endereço do Worker de ensaio. O resumo (estados, mediana, p95, p99) fica no resumo do job. Falha com mais de 1% de erros ou com um p95 acima de 1,5 s.
3. **remover**: apaga o Worker de ensaio.

Exemplo: 400 leitores durante 60 minutos dão 24 000 pedidos, cerca de um quarto do orçamento diário. Não correr no dia da eleição nem na véspera.
