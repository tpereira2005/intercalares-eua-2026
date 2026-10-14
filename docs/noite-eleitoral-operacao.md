# Noite eleitoral: guião de operação

Guião curto para a noite de 3 para 4 de novembro de 2026: o que lançar, a que horas de Lisboa e o que fazer quando algo falha. A metodologia está em [`metodologia/resultados.md`](metodologia/resultados.md) (recolha) e [`metodologia/noite-eleitoral.md`](metodologia/noite-eleitoral.md) (projeção).

## Horas

A 3 de novembro, Lisboa está em UTC+0 (a hora de inverno começa a 25 de outubro) e a costa leste dos EUA em UTC−5 (a 1 de novembro). As horas de Lisboa são iguais às UTC.

| Lisboa (= UTC)  | O que acontece                                                                                                        |
| --------------- | --------------------------------------------------------------------------------------------------------------------- |
| 22:00 (dia 3)   | O vigia começa a correr sozinho, a cada 10 minutos                                                                    |
| **22:30**       | **Lançar a recolha e a projeção** (abaixo)                                                                            |
| 23:00           | Primeiros fechos de urnas (partes do Indiana e do Kentucky; nenhum estado acompanhado)                                |
| 00:00 (dia 4)   | Fecham a Geórgia e a maior parte da Florida; 00:30, a Carolina do Norte; 01:00, o oeste da Florida e o Texas (Harris) |
| 05:00           | Fecha o Alasca                                                                                                        |
| ~04:15 e ~10:00 | A recolha e a projeção relançam-se sozinhas (jobs de 5h45 encadeados)                                                 |
| 16:00           | Fim da cadeia (`ate`); a contagem por correspondência continua nos dias seguintes                                     |

## Antes da noite (de 26 de outubro a 2 de novembro)

1. O workflow **Resultados** (ensaio semanal) está verde em NC, FL, GA, AK e TX. SC e IA falham com o desafio do AWS WAF; se passarem, o bloqueio acabou e podem entrar na lista de estados.
2. O job **Fontes de 2026** desse workflow mostra os endereços de 2026: NCSBE (`er.ncsbe.gov/enr/20261103`), Florida, Geórgia (`2026NovGen`), Alasca (`enr26/results/GA_ENR_Precinct_State_of_Alaska.csv`) e Harris (`Data/1126`). Um 404 antes da noite é normal; um desafio anti-robô não é.
3. A previsão está **congelada** (1 de novembro) na Release `dados-previsao`: a projeção recusa uma previsão por congelar.
4. A API ao vivo responde: `/api/resultados` e `/api/noite` no site (ver `docs/api-ao-vivo.md`). Antes da noite, um `404` é normal. É por aí que o site mostra resultados novos sem nova implantação.

## Lançar (22:30)

Em _Actions_ no GitHub, ou com o `gh`:

```sh
gh workflow run resultados.yml -f modo=noite -f data=2026-11-03 \
  -f ate=2026-11-04T16:00 -f estados=NC,FL,GA,AK,TX
gh workflow run noite.yml -f modo=noite -f ate=2026-11-04T16:00
```

A recolha pede as fontes a cada 30 segundos e envia para a Release `resultados-2026` os ficheiros que mudaram (`<estado>.json`, `nacional.json`, `parciais.json`), mais o `saude.json` a cada 5 minutos ou quando um alerta muda. A projeção lê o `parciais.json` a cada 30 segundos e publica na Release `dados-noite`.

## Latência

Medida no ensaio de 13 de outubro com os ficheiros reais de 2024 de NC, FL, GA, AK e TX (Harris) servidos por um espelho local:

| Etapa                                              | Tempo                                                              |
| -------------------------------------------------- | ------------------------------------------------------------------ |
| Fonte muda → recolha dá por isso                   | até 30 s (15 s em média)                                           |
| Ciclo da recolha (5 estados, NC com 101 ficheiros) | menos de 1 s no espelho; com a rede real, alguns segundos          |
| Envio para a Release                               | alguns segundos (um `gh release upload` por ciclo com alterações)  |
| Projeção dá pelo `parciais.json` novo              | até 30 s (15 s em média)                                           |
| Um passo da projeção (NC, GA e FL)                 | cerca de 1 s                                                       |
| Release → site                                     | até 20 s no Worker, mais até 60 s até o browser voltar a consultar |

Da fonte à Release: cerca de 20 a 40 segundos para os resultados e de 40 a 80 segundos para a projeção.

## O que fazer se algo falhar

O vigia abre (ou comenta) um issue **"Vigia da noite eleitoral"** com a tabela de cada estado. Uma falha de um estado nunca para os outros, e o último ficheiro válido desse estado continua publicado; nada inválido chega à Release.

| Sinal                                                         | Causa provável                                                               | O que fazer                                                                                                                                     |
| ------------------------------------------------------------- | ---------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------- |
| `XX: N falhas seguidas: ErroBloqueio ...`                     | A fonte passou a pedir um desafio anti-robô                                  | Não contornar. Relançar a recolha sem esse estado (`-f estados=...`); o site mostra a previsão para essas corridas                              |
| `XX: N falhas seguidas: HTTPStatusError 404`                  | Endereço de 2026 diferente do previsto                                       | Abrir a página oficial do estado, encontrar o ficheiro novo, corrigir o conector num PR pequeno e relançar                                      |
| `XX: N falhas seguidas: ErroFormatoFonte ...`                 | A fonte mudou de formato ou publicou um ficheiro partido                     | Ver as cópias da fonte no artefacto `noite-<id>` do job. Se for passageiro, resolve-se sozinho; se for formato novo, corrigir o conector num PR |
| `XX: N falhas seguidas` com 429 ou 5xx                        | Fonte sobrecarregada                                                         | Nada: a recolha repete com recuo e respeita o `Retry-After`. Se durar mais de 15 minutos, comparar com o site oficial do estado                 |
| `XX: sem dados novos há N minutos, com a contagem por acabar` | Fonte presa, ou pausa normal (madrugada, correspondência só no dia seguinte) | Comparar com o site oficial do estado. Se o site oficial avançou e o nosso não, ver os registos do job                                          |
| `A recolha parou: saude.json com N minutos`                   | Job cancelado, limite do Actions, cadeia de relançamentos partida            | Ver _Actions → Resultados_. Relançar com o comando acima (o `ate` mantém-se)                                                                    |
| Projeção sem novidades em `dados-noite`                       | Job da projeção parado                                                       | Ver _Actions → Projeção da noite_ e relançar `noite.yml` com o mesmo `ate`                                                                      |

Depois da noite, quando tudo estiver apurado, o vigia deixa de avisar sozinho; para o desligar antes de 5 de novembro, `gh workflow disable vigia-noite.yml`.
