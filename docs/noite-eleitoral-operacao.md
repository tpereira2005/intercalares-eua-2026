# Noite eleitoral: guião de operação

Guião curto para a noite de 3 para 4 de novembro de 2026: o que lançar, a que horas de Lisboa e o que fazer quando algo falha. A metodologia está em [`metodologia/resultados.md`](metodologia/resultados.md) (recolha) e [`metodologia/noite-eleitoral.md`](metodologia/noite-eleitoral.md) (projeção).

## Horas

A 3 de novembro, Lisboa está em UTC+0 (a hora de inverno começa a 25 de outubro) e a costa leste dos EUA em UTC−5 (a 1 de novembro). As horas de Lisboa são iguais às UTC.

| Lisboa (= UTC)  | O que acontece                                                                                                                                                                                   |
| --------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| 22:00 (dia 3)   | O vigia começa a correr sozinho, a cada 10 minutos                                                                                                                                               |
| **22:30**       | **Lançar a recolha e a projeção** (abaixo)                                                                                                                                                       |
| 23:00           | Primeiros fechos de urnas (partes do Indiana e do Kentucky; nenhum estado acompanhado)                                                                                                           |
| 00:00 (dia 4)   | Fecham a Geórgia, a Virgínia e a maior parte da Florida; 00:30, a Carolina do Norte; 01:00, o oeste da Florida e o Texas (Harris); 02:00, o Nebraska e o Arizona (Maricopa); 04:00, a Califórnia |
| 05:00           | Fecha o Alasca                                                                                                                                                                                   |
| ~04:15 e ~10:00 | A recolha e a projeção relançam-se sozinhas (jobs de 5h45 encadeados)                                                                                                                            |
| 16:00           | Fim da cadeia (`ate`); a contagem por correspondência continua nos dias seguintes                                                                                                                |

## Antes da noite (de 26 de outubro a 2 de novembro)

1. O workflow **Resultados** (ensaio semanal) está verde em NC, FL, GA, AK, TX e VA (o Nebraska, a Califórnia e Maricopa não têm ensaio: as fontes só mostram a eleição em curso ou não ligam os ficheiros antigos). SC e IA falham com o desafio do AWS WAF; se passarem, o bloqueio acabou e podem entrar na lista de estados.
2. O job **Fontes de 2026** desse workflow mostra os endereços de 2026: NCSBE (`er.ncsbe.gov/enr/20261103`), Florida, Geórgia (`2026NovGen`), Virgínia (`2026-November-General`), Nebraska (`resultsCSV.aspx?type=SW` e `type=CG`), Alasca (`enr26/results/GA_ENR_Precinct_State_of_Alaska.csv`) Harris (`Data/1126`), Califórnia (`media.sos.ca.gov/media/us-rep.json` e `governor.json`) e Maricopa (a ligação `2026 November General Election Results.txt` em `elections.maricopa.gov/results-and-data/election-results.html`; o ficheiro tem cerca de 30 MB). Um 404 antes da noite é normal; um desafio anti-robô não é (o `elections.maricopa.gov` já mostrou um na página inicial, mas não na de resultados nem no ficheiro).
3. A previsão está **congelada** (1 de novembro) na Release `dados-previsao`: a projeção recusa uma previsão por congelar.
4. A API ao vivo responde: `/api/resultados` e `/api/noite` no site (ver `docs/api-ao-vivo.md`). Antes da noite, um `404` é normal. É por aí que o site mostra resultados novos sem nova implantação.

## Lançar (22:30)

Em _Actions_ no GitHub, ou com o `gh`:

```sh
gh workflow run resultados.yml -f modo=noite -f data=2026-11-03 \
  -f ate=2026-11-04T16:00 -f estados=NC,FL,GA,AK,TX,VA,NE,AZ,CA
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

## Entrada manual

Os estados que recusam pedidos automáticos (Pensilvânia, Michigan, Ohio, Nevada, Carolina do Sul, Iowa, entre outros) entram à mão, com os totais copiados da página oficial do estado. Só para as corridas que interessam: Senado, governador e distritos disputados.

No GitHub (site ou aplicação do telemóvel): **Actions → Resultado manual → Run workflow**, com:

| Campo        | Exemplo                                                        |
| ------------ | -------------------------------------------------------------- |
| `corrida`    | `PA-S` (Senado), `MI-G` (governador), `PA-07` (distrito 7)     |
| `candidatos` | `Nome A (D): 1.234.567; Nome B (R): 1.200.000; Outros: 30.000` |
| `apuramento` | `87%`, ou `1234/2000` se a página mostrar secções              |
| `fonte`      | o endereço da página oficial de onde se copiaram os números    |
| `apagar`     | marcar só para retirar uma corrida introduzida por engano      |

O workflow valida tudo antes de escrever (um erro deixa o ficheiro como estava) e atualiza `manual.json` na Release `resultados-2026`. A recolha lê-o a cada ciclo: a corrida aparece no `nacional.json` e no `parciais.json` no ciclo seguinte (`manual: true` e `corridas_manuais`), e o site mostra o selo "introduzido manualmente". Para atualizar uma corrida, volta-se a lançar com os números novos; um total que desce dá um aviso no resumo do workflow (pode ser uma correção da página oficial).

Estados com fonte estadual automática (NC, FL, GA, AK, VA, NE e CA) são recusados: aí os números vêm da fonte aberta. O Texas e o Arizona aceitam entradas manuais, porque a recolha automática só tem Harris e Maricopa. Aí a entrada fica sobreposta: publica-se em `tx-manual.json` (ou `az-manual.json`) e, nessa corrida, o total do estado substitui os condados no resumo nacional e nos parciais. As outras corridas continuam a vir dos condados. Exemplo: `TX-S` à mão, `TX-07` de Harris.

## Ensaio com falhas

`pipeline.jobs.ensaio_noite` corre o ciclo real da recolha contra um espelho local com os ficheiros finais de 2022 ou 2024 e um calendário de falhas. São sete: fonte em baixo (404), erro do servidor (5xx), 429 com `Retry-After`, ficheiro truncado, resposta vazia, fonte lenta (22 s, acima do tempo limite) e desafio anti-robô. No fim de cada ciclo verifica doze invariantes. O código de saída é 1 se algum falhar. Com `--manual`, o espelho serve também um `manual.json` que cresce em quatro entradas, como na noite: o Senado da Pensilvânia e, com o Texas na lista, o do Texas, sobreposto a Harris. O décimo segundo invariante confirma que cada entrada chega a `parciais.json` com o selo, sem corridas repetidas no resumo nacional.

```sh
uv run python -m pipeline.jobs.ensaio_noite --data 2024-11-05 --manual --relatorio ensaio-2024.md
uv run python -m pipeline.jobs.ensaio_noite --data 2022-11-08 --estados NC,GA,TX --duracao 180
```

A 14 de outubro de 2026, a primeira volta encontrou quatro defeitos, todos corrigidos:

- **Fonte lenta prendia todos os estados.** Os estados eram recolhidos em série, e uma fonte lenta atrasava os outros até 22 s. Agora correm em paralelo, e o ciclo espera no máximo 10 s (`ORCAMENTO_CICLO`). Um estado mais lento continua em fundo e entra no ciclo em que acabar.
- **429 com `Retry-After` bloqueava o ciclo.** Agora a recolha repete uma vez, com uma espera de 5 s no máximo. Um `Retry-After` maior põe só esse estado em pausa, durante 5 minutos no máximo.
- **Ficheiro mal lido passava por bom no ciclo seguinte.** Quando um ficheiro se descarregava mas não se conseguia ler, o 304 seguinte contava como sucesso. Agora a recolha esquece o ETag e volta a descarregar e a ler o ficheiro.
- **Duas cópias da fonte no mesmo segundo colidiam.** As pastas em `brutos/` passaram a ter microssegundos no nome.

Na segunda volta passaram todos os invariantes, nos dois anos:

| Ensaio                           | Ciclos | Ciclo mais longo | Alteração na fonte → `parciais.json` |
| -------------------------------- | -----: | ---------------: | ------------------------------------ |
| 2024: NC, FL, GA, AK e TX, 300 s |     60 |            1,7 s | mediana 0,7 s, máximo 4,3 s          |
| 2022: NC, GA e TX, 180 s         |     36 |            1,7 s | mediana 2,0 s, máximo 4,1 s          |

A 15 de outubro, o ensaio de 2024 com `--manual` (60 ciclos) passou os doze invariantes: as quatro entradas manuais de PA-S e TX-S chegaram todas aos parciais, o ciclo mais longo durou 1,7 s e a latência dos estados manteve-se (mediana 0,7 s, máximo 4,3 s).

Antes das correções, o ciclo mais longo era de 22 s e a pior latência de 17 s (2024) e de 23 s (2022).

## O que fazer se algo falhar

O vigia abre (ou comenta) um issue **"Vigia da noite eleitoral"** com a tabela de cada estado. Uma falha de um estado nunca para os outros, e o último ficheiro válido desse estado continua publicado; nada inválido chega à Release.

| Sinal                                                         | Causa provável                                                               | O que fazer                                                                                                                                                                                                       |
| ------------------------------------------------------------- | ---------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `XX: N falhas seguidas: ErroBloqueio ...`                     | A fonte passou a pedir um desafio anti-robô                                  | Não contornar. Relançar a recolha sem esse estado (`-f estados=...`); o site mostra a previsão para essas corridas                                                                                                |
| `XX: N falhas seguidas: HTTPStatusError 404`                  | Endereço de 2026 diferente do previsto                                       | Abrir a página oficial do estado, encontrar o ficheiro novo, corrigir o conector num PR pequeno e relançar                                                                                                        |
| `XX: N falhas seguidas: ErroFormatoFonte ...`                 | A fonte mudou de formato ou publicou um ficheiro partido                     | Ver as cópias da fonte no artefacto `noite-<id>` do job. Se for passageiro, resolve-se sozinho; se for formato novo, corrigir o conector num PR                                                                   |
| `XX: N falhas seguidas` com 429 ou 5xx                        | Fonte sobrecarregada                                                         | Nada: a recolha repete uma vez e, com um `Retry-After` longo, deixa esse estado em pausa o tempo pedido (até 5 minutos) sem atrasar os outros. Se durar mais de 15 minutos, comparar com o site oficial do estado |
| `XX: sem dados novos há N minutos, com a contagem por acabar` | Fonte presa, ou pausa normal (madrugada, correspondência só no dia seguinte) | Comparar com o site oficial do estado. Se o site oficial avançou e o nosso não, ver os registos do job                                                                                                            |
| `A recolha parou: saude.json com N minutos`                   | Job cancelado, limite do Actions, cadeia de relançamentos partida            | Ver _Actions → Resultados_. Relançar com o comando acima (o `ate` mantém-se)                                                                                                                                      |
| Projeção sem novidades em `dados-noite`                       | Job da projeção parado                                                       | Ver _Actions → Projeção da noite_ e relançar `noite.yml` com o mesmo `ate`                                                                                                                                        |

Depois da noite, quando tudo estiver apurado, o vigia deixa de avisar sozinho; para o desligar antes de 5 de novembro, `gh workflow disable vigia-noite.yml`.

## Reserva local

Se o GitHub Actions deixar de correr (falha do serviço, limite de minutos), a recolha e a projeção podem correr num computador com `uv` e o `gh` com sessão iniciada. O script publica nas mesmas Releases e relança cada processo se parar, até à hora indicada:

```sh
pipeline/scripts/noite-reserva.sh --verificar             # confere os requisitos
pipeline/scripts/noite-reserva.sh --ate 2026-11-04T16:00  # hora UTC
```

Nunca correm dois publicadores ao mesmo tempo: o script recusa arrancar se houver execuções de `resultados.yml` ou `noite.yml` em curso (cancelar primeiro, ou `--forcar`). A reserva usa as mesmas fontes que o Actions; não serve para recolher estados que bloqueiam pedidos automáticos.
