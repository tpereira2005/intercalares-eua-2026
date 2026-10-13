# Metodologia: previsão da Câmara e do Senado

Este documento descreve o modelo próprio do Escrutínio para as eleições de 3 de novembro de 2026 (plano, fase 2). O modelo dá a probabilidade de cada partido controlar a Câmara e o Senado, a distribuição de lugares e uma previsão para cada corrida. Congela-se a **1 de novembro de 2026**, dois dias antes da eleição.

Três regras orientam todas as escolhas:

1. **Simetria.** Nenhum passo depende do partido que favorece. Trocar os partidos em todas as entradas troca exatamente os parâmetros e, dentro do erro de simulação, as probabilidades (há um teste automático para isso).
2. **Só o passado.** Cada previsão usa apenas eleições anteriores. Os backtests de 2018, 2022 e 2024 correm o mesmo código com os dados disponíveis dois dias antes de cada eleição.
3. **Só dados gratuitos e reutilizáveis.** Wikipédia (CC BY-SA 4.0) e o ficheiro `raw_polls.csv` da FiveThirtyEight (CC BY 4.0). Nenhuma API paga.

Todas as margens estão em pontos percentuais do voto total e são sempre **Democrata menos Republicano (D−R)**: positivo favorece o lado democrata, negativo o republicano.

## 1. Dados

| Dado                                                              | Fonte                                                                                                     | Anos        |
| ----------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------- | ----------- |
| Corridas: distrito, Cook PVI, incumbente, candidatos e resultados | Páginas anuais da Wikipédia ("20XX United States House/Senate elections")                                 | 2012 a 2026 |
| Voto popular nacional na Câmara                                   | Caixa de informação das páginas anuais (2012 a 2024); `raw_polls.csv` (1998 a 2010)                       | 1998 a 2024 |
| Sondagens finais do Senado e do voto genérico                     | `raw_polls.csv` da FiveThirtyEight                                                                        | 1998 a 2022 |
| Sondagens do Senado de 2024 e 2026                                | Páginas de cada corrida na Wikipédia (secções "General election" ou "Polling")                            | 2024 e 2026 |
| Voto genérico de 2026                                             | Agregadores citados na página anual de 2026 (DDHQ, NBC, RealClearPolitics, Silver Bulletin, FiftyPlusOne) | 2026        |
| Estados com mapa novo em 2026                                     | Tabela "Summary of mid-decade changes" da página anual de 2026                                            | 2026        |

As tabelas dos anos terminados estão versionadas em `data/reference/modelo/` (ver `data/PROVENIENCIA.md`) e reconstroem-se com `pipeline.jobs.referencia_modelo`. Os dados de 2026 descarregam-se a cada execução, com um User-Agent identificado, espera entre pedidos e cache local.

### Leitura das páginas

As tabelas da Wikipédia mudam de formato entre anos (predefinições diferentes para o PVI, listas de candidatos com e sem `*`, `rowspan` nas sondagens, voto preferencial com duas voltas). O leitor trata cada formato encontrado e os testes guardam um exemplo de cada um. Regras de leitura:

- **Voto preferencial** (Maine e Alasca): a margem usa a primeira volta, comparável às outras corridas; o vencedor é o da última volta.
- **Disputas internas**: quando dois candidatos do mesmo partido têm ambos 20% ou mais (por exemplo Murkowski contra Tshibaka em 2022, ou dois Democratas na Califórnia), a margem D−R não mede a disputa entre partidos e a corrida não entra na estimação.
- **Independentes**: um independente ocupa o lado de um partido quando esse partido não apresenta candidato e o outro sim, ou quando está numa lista explícita (Sanders, King, Osborn, McMullin, Orman e Achilles do lado democrata; Kiley do lado republicano). A regra é a mesma nos dois lados. Os lugares que ganharem contam para a bancada desse lado; as corridas com independentes não entram na estimação dos fundamentos.
- **Corridas decididas**: sem candidato de um dos lados, o vencedor fica certo (ex.: dois Democratas na segunda volta da Califórnia).
- **Vários candidatos do mesmo partido antes da eleição** (primárias abertas como a do Alasca, a Luisiana, homónimos): o candidato desse lado é o incumbente que se recandidata e, a seguir, quem tem artigo na Wikipédia. Depois da eleição é sempre o mais votado.
- **Incumbência**: só conta quando o incumbente é o candidato escolhido do seu lado. Um homónimo (Mike Doyle em 2022) ou um incumbente derrotado na primária que aparece noutra linha (Crowley em 2018) não dão vantagem de incumbência.

### Verificações antes de publicar

Cada execução diária verifica a previsão antes de a gravar e não publica se encontrar um erro (o ficheiro anterior fica no ar):

- o incumbente concorre mas o candidato escolhido do seu lado é outro;
- a média de sondagens afasta-se mais de 25 pontos dos fundamentos (entre 15 e 25 pontos é um aviso no registo);
- uma probabilidade acima de 99% contra fundamentos que favorecem o outro lado por mais de 3 pontos, com menos de 4 institutos (com mais é um aviso).

As regras olham só para distâncias e sinais, por isso tratam os dois partidos da mesma forma.

## 2. Fundamentos

Para cada câmara estima-se, por mínimos quadrados com os anos anteriores:

```
margem − N_ano = efeito_ano + inclinação × PVI + incumbência × inc (+ persistência × resíduo anterior)
```

- `N_ano` é o voto popular nacional na Câmara (D−R).
- `PVI` é o Cook PVI em pontos de margem (o dobro do valor publicado, D+ positivo).
- `inc` vale +1 se o incumbente democrata se recandidata, −1 se for republicano e 0 em lugar aberto.
- **Persistência** (só na Câmara): fração do desvio do mesmo incumbente no ciclo anterior que se mantém, apenas quando o distrito não foi redesenhado entre os dois ciclos.
- O intercepto é a média dos efeitos de ano; o seu desvio-padrão entre anos (`desvio_ano`) mede a incerteza na tradução do ambiente nacional para os distritos.
- Os desvios-padrão de cada corrida e de cada região do Census estimam-se com as corridas previstas a menos de 30 pontos, que são as que decidem lugares.

Valores estimados para 2026 (treino com 2012 a 2024):

| Parâmetro          | Câmara | Senado |
| ------------------ | -----: | -----: |
| Inclinação do PVI  |   0,90 |   0,83 |
| Incumbência (pts)  |    6,4 |    6,0 |
| Persistência       |   0,53 |      0 |
| Desvio do ano      |    1,5 |    1,9 |
| Desvio da região   |    1,6 |    2,0 |
| Desvio da corrida  |    7,6 |    7,7 |
| Corridas no treino |  2 663 |    191 |

## 3. Ambiente nacional

O centro das simulações é a margem nacional no voto genérico:

- em 2026, a **média simples dos agregadores públicos** citados na Wikipédia;
- nos backtests de 2018 e 2022, a nossa média das sondagens do voto genérico de `raw_polls.csv`;
- no backtest de 2024 não há sondagens do voto genérico nesse ficheiro, por isso o ambiente lê-se das sondagens do Senado: cada corrida dá uma leitura (média − fundamentos sem ambiente) e combina-se pela precisão. A incerteza soma o erro comum das sondagens do Senado.

O erro do ambiente é a **raiz do erro quadrático médio** das médias do voto genérico face ao resultado, de 1998 até ao ciclo anterior (3,2 pontos para 2026). **Não se corrige o sinal** do erro histórico: o desvio médio dos últimos ciclos não é estável de ciclo para ciclo, e corrigi-lo seria escolher um lado. O erro entra só como dimensão da incerteza, igual nos dois sentidos.

## 4. Sondagens do Senado

A média de cada corrida usa os mesmos pesos para todas as corridas e para o voto genérico:

- recência: metade do peso a cada 14 dias, numa janela de 60 dias até ao corte (exclusive);
- amostra: raiz de n/600, com n limitado a 2 000;
- população: eleitores prováveis 1, registados 0,8, adultos 0,6, desconhecida 0,9; da mesma sondagem fica só a população preferida;
- sondagens de partidos ou campanhas (de qualquer lado): metade do peso;
- cada instituto conta uma vez (o peso divide-se pelo número de sondagens do instituto na janela);
- só entram perguntas com os dois candidatos reais da corrida.

O erro de uma média estima-se com as corridas de 1998 até ao ciclo anterior: `erro² ≈ base² + por_instituto² / institutos`, mais um erro comum a todas as corridas do ano, ligado em parte ao erro do voto genérico (coeficiente `ligacao_nacional`, 0,49 para 2026).

Fundamentos e sondagens combinam-se com pesos inversamente proporcionais às respetivas variâncias. Com os erros estimados para 2026, as sondagens pesam cerca de 42% numa corrida com um só instituto, 65% com três e 82% com quinze. Sem sondagens, fica só a previsão por fundamentos.

## 5. Simulação

20 000 cenários com semente fixa. Em cada cenário sorteiam-se, por esta ordem:

1. um erro nacional comum às duas câmaras (t de Student com 5 graus de liberdade, para caudas mais pesadas do que a normal);
2. um erro na tradução do ambiente para os distritos, por câmara;
3. um choque por região do Census (Nordeste, Centro-Oeste, Sul, Oeste), partilhado pelas duas câmaras;
4. o erro próprio de cada corrida.

No Senado, as corridas com sondagens recebem ainda a parte do erro comum das sondagens desse ano que não acompanha o erro do voto genérico (secção 4), na proporção do peso das sondagens.

Na Câmara, a maioria é 218 de 435. No Senado, somam-se os lugares que não vão a votos (47 democratas e independentes que votam com eles, 53 republicanos antes da eleição); com 50 lugares para cada lado desempata o vice-presidente (republicano no Congresso eleito em 2026).

O ficheiro publicado traz também o **limiar nacional**: a margem no voto genérico a partir da qual o lado democrata passa a favorito ao controlo de cada câmara. Abaixo dele o favorito é o lado republicano, o que permite ler os dois cenários com o mesmo destaque.

## 6. Voto antecipado

O voto antecipado **não altera a previsão** (peso 0). O rastreador tem ciclos comparáveis de poucos estados, e três ou quatro eleições por estado não chegam para estimar quanto um desvio no voto antecipado se traduz em margem final sem sobreajustar. O plano prevê que o sinal entre só na medida em que a metodologia o justifique; por agora é um diagnóstico mostrado ao lado da previsão, nunca dentro dela.

## 7. Backtests

O mesmo código, com o corte dois dias antes de cada eleição e parâmetros estimados só com os anos anteriores:

| Ano  | Câmara | Ambiente previsto / real | P(controlo D) | Lugares D: mediana [p10, p90] | Reais | Corridas erradas | Brier | Viés nas competitivas | Cobertura 80% |
| ---- | ------ | ------------------------ | ------------: | ----------------------------- | ----: | ---------------: | ----: | --------------------: | ------------: |
| 2018 | Câmara | D+7,6 / D+8,6            |           72% | 224 [210, 240]                |   235 |        27 de 412 | 0,045 |                  −3,4 |           88% |
| 2018 | Senado | D+7,6 / D+8,6            |           10% | 48 [44, 50]                   |    47 |          2 de 34 | 0,050 |                  +1,1 |           91% |
| 2022 | Câmara | D−0,7 / R+2,7            |           34% | 213 [198, 227]                |   213 |        18 de 412 | 0,029 |                  +1,2 |           91% |
| 2022 | Senado | D−0,7 / R+2,7            |           49% | 49 [47, 53]                   |    51 |          2 de 33 | 0,030 |                  −0,9 |           76% |
| 2024 | Câmara | D+2,0 / R+2,6            |           49% | 217 [201, 234]                |   215 |         9 de 406 | 0,017 |                  +2,4 |           92% |
| 2024 | Senado | D+2,0 / R+2,6            |           13% | 48 [45, 51]                   |    47 |          1 de 33 | 0,033 |                  +2,7 |           97% |

Notas de leitura:

- O viés é a média de (previsto − real) nas corridas com margem prevista abaixo de 15 pontos. Mudou de sinal entre ciclos (−3,4 a favor do lado republicano em 2018, +2,4 e +2,7 a favor do lado democrata em 2024), o que confirma que não há base para impor uma correção num sentido.
- Em 2024 o ambiente vem das sondagens do Senado, que erraram para o lado democrata; o modelo ficou praticamente empatado na Câmara e deu 73% aos Republicanos no Senado (P(D) + P(R) < 1 nesse ano porque o desempate dependia da eleição presidencial do mesmo dia).
- A cobertura do intervalo de 80% fica entre 76% e 97%: a incerteza está bem calibrada na Câmara e algo larga no Senado.

## 8. Sensibilidade

`pipeline.jobs.sensibilidade_previsao` volta a correr a previsão de 2026 e os três backtests mudando uma escolha de cada vez. Nada aqui altera a previsão publicada: os ajustes (`Ajustes` em `modelo/previsao.py`) são neutros por omissão, e um teste confirma que o resultado é idêntico.

- **Ambiente nacional.** Desloca-se sempre nos dois sentidos, com o mesmo valor.
- **Backtests.** As variantes do ambiente não se avaliam nos backtests: deslocar o ambiente num ano passado só mediria o erro real desse ano.
- **Colunas dos backtests.** O Brier e a cobertura são médias de 2018, 2022 e 2024.

Corte de 13 de outubro de 2026:

| Variante                                   | Câmara P(D) | Lugares D (p10–p90) | Senado P(D) | Lugares D (p10–p90) | Brier Câmara | Brier Senado | Cobertura 80% Câmara | Cobertura 80% Senado |
| ------------------------------------------ | ----------: | ------------------: | ----------: | ------------------: | -----------: | -----------: | -------------------: | -------------------: |
| Modelo publicado                           |         97% |       242 (225–263) |         73% |          52 (48–56) |        0,030 |        0,038 |                  90% |                  88% |
| Ambiente −3 pontos                         |         87% |       231 (216–249) |         65% |          52 (48–55) |            — |            — |                    — |                    — |
| Ambiente −2 pontos                         |         92% |       234 (219–253) |         68% |          52 (48–55) |            — |            — |                    — |                    — |
| Ambiente −1 ponto                          |         95% |       238 (222–258) |         70% |          52 (48–56) |            — |            — |                    — |                    — |
| Ambiente +1 ponto                          |         98% |       246 (228–268) |         75% |          52 (49–56) |            — |            — |                    — |                    — |
| Ambiente +2 pontos                         |         99% |       251 (232–274) |         77% |          53 (49–56) |            — |            — |                    — |                    — |
| Ambiente +3 pontos                         |         99% |       255 (235–279) |         79% |          53 (49–56) |            — |            — |                    — |                    — |
| Ambiente sem os agregadores                |         87% |       235 (215–260) |         67% |          52 (48–56) |            — |            — |                    — |                    — |
| Erro do ambiente × 0,75                    |         98% |       242 (227–260) |         73% |          52 (49–56) |        0,030 |        0,038 |                  90% |                  87% |
| Erro do ambiente × 1,25                    |         95% |       242 (222–267) |         72% |          52 (48–56) |        0,031 |        0,038 |                  91% |                  89% |
| Erro do ambiente × 1,5                     |         92% |       242 (220–271) |         71% |          52 (48–56) |        0,031 |        0,038 |                  92% |                  90% |
| t com 3 graus de liberdade                 |         97% |       242 (226–261) |         73% |          52 (48–56) |        0,030 |        0,038 |                  90% |                  88% |
| t com 30 graus de liberdade (quase normal) |         97% |       242 (224–265) |         72% |          52 (48–56) |        0,030 |        0,038 |                  90% |                  88% |
| Erro de cada corrida × 0,75                |         96% |       239 (223–260) |         70% |          52 (49–55) |        0,031 |        0,039 |                  83% |                  87% |
| Erro de cada corrida × 1,25                |         97% |       245 (227–266) |         74% |          53 (48–56) |        0,031 |        0,038 |                  95% |                  87% |
| Erro das sondagens × 0,75                  |         97% |       242 (225–263) |         78% |          53 (49–56) |        0,030 |        0,036 |                  90% |                  78% |
| Erro das sondagens × 1,5                   |         97% |       242 (225–263) |         67% |          52 (48–55) |        0,031 |        0,042 |                  91% |                  95% |
| Meia-vida das sondagens de 7 dias          |         97% |       242 (226–262) |         73% |          52 (48–56) |        0,030 |        0,039 |                  90% |                  88% |
| Meia-vida das sondagens de 28 dias         |         97% |       242 (225–264) |         72% |          52 (48–56) |        0,031 |        0,037 |                  90% |                  88% |
| Sem sondagens do Senado (só fundamentos)   |         97% |       242 (225–263) |         62% |          51 (48–54) |        0,030 |        0,057 |                  90% |                  86% |

Leitura:

- **A Câmara depende quase só do ambiente nacional.** Cada ponto no voto genérico vale cerca de 4 lugares na mediana. Os Democratas deixam de ser favoritos abaixo de D+1,0 (o limiar nacional publicado), e o ambiente atual é D+8,4. Mesmo com um ambiente 3 pontos pior ou um erro nacional 50% maior, a probabilidade fica entre 87% e 92%.
- **O Senado depende sobretudo das sondagens de cada corrida.** Sem elas, só com fundamentos, a probabilidade cai de 73% para 62%. Dar-lhes mais confiança (erro × 0,75) sobe-a para 78%; dar-lhes menos (× 1,5) desce-a para 67%.
- **A fonte do ambiente é a escolha que mais pesa na Câmara.** Os agregadores dão D+8,4. A Wikipédia de 2026 não lista sondagens individuais do voto genérico, por isso, sem os agregadores, o ambiente ler-se-ia nas sondagens do Senado (D+6,6, como no backtest de 2024): 87% na Câmara e 67% no Senado. Os agregadores ficam, por serem a medida direta do voto genérico. A leitura pelo Senado erra mais (secção 3) e, em 2024, errou para o lado democrata.
- **As caudas e a recência pesam pouco.** A t de Student com 3 ou 30 graus de liberdade e a meia-vida de 7 ou 28 dias mudam as probabilidades no máximo 1 ponto.
- **Os parâmetros publicados não se afinam com estes números.** Nenhuma variante melhora o Brier dos backtests de forma consistente nas duas câmaras. As diferenças (0,036 a 0,042 no Senado) cabem no ruído de três eleições. Escolher a variante com o melhor Brier seria ajustar o modelo a 2018, 2022 e 2024. A cobertura de 88% a 90% confirma que os intervalos já são, se algo, um pouco largos.

## 10. Congelamento

A previsão congela com os dados até 31 de outubro: o corte é 1 de novembro de 2026, exclusive para as sondagens. Nesse dia:

1. A execução agendada (06h41 UTC) corre com corte de 1 de novembro e marca o ficheiro como `congelada`. O histórico ganha o último dia, também marcado.
2. Antes de publicar, o workflow exige que o ficheiro do último dia seja `congelada` com corte de 1 de novembro, e que o último dia do histórico também o seja.
3. A partir de 2 de novembro, a execução agendada não faz nada, e uma versão congelada já publicada nunca é substituída.

Se a execução de 1 de novembro falhar (Wikipédia em baixo, por exemplo), uma execução à mão depois dessa data ainda publica a versão congelada, com o corte em 1 de novembro, mas só enquanto a Release não tiver nenhuma. Nesse caso, os agregadores do voto genérico são lidos no momento dessa execução (ver as limitações). As sondagens continuam limitadas às terminadas antes do corte.

O job da noite eleitoral (`docs/metodologia/noite-eleitoral.md`) só aceita uma previsão `congelada`.

O ciclo completo foi testado localmente a 13 de outubro:

1. A previsão com `--corte 2026-11-01` sai `congelada`, com corte de 1 de novembro, e acrescenta um dia congelado ao histórico. Um corte posterior fica limitado a 1 de novembro.
2. O job da noite aceita esse ficheiro sem `--aceitar-provisoria` e recusa a previsão diária.
3. A lógica de janela e de validação do workflow foi verificada com um `gh` simulado, para os dias 31 de outubro, 1 e 2 de novembro, com e sem versão congelada publicada.

## 9. Histórico diário

Cada execução do workflow acrescenta a previsão do dia a `historico-previsao-2026.json` (contrato `HistoricoPrevisao`), publicado na mesma Release: resumo das duas câmaras, ambiente nacional e probabilidade e margem prevista de cada uma das 470 corridas (435 distritos e 35 corridas ao Senado, incluindo as especiais da Florida e do Ohio). Uma data de corte repetida substitui a anterior. O histórico só cresce até ao congelamento.

## 11. Avaliação da previsão congelada

Depois da eleição, `pipeline.jobs.avaliacao_previsao` avalia o ficheiro congelado a 1 de novembro (exatamente o que esteve no site) face aos resultados (contrato `AvaliacaoPrevisao`):

- **Brier**: média de (probabilidade − resultado)². 0 é perfeito; 0,25 é atirar uma moeda.
- **Log-loss**: média de −ln(probabilidade dada ao vencedor), com as probabilidades limitadas a [10⁻⁶, 1 − 10⁻⁶]. Pune mais a confiança errada.
- **Calibração**: as corridas agrupam-se pela probabilidade do favorito (50-60%, 60-70%, ..., 95-100%) e compara-se com a frequência com que o favorito ganhou. Usar o favorito, e não o lado democrata, torna a tabela igual se os partidos forem trocados.
- **Margens**: erro absoluto médio, viés (prevista − real) e cobertura do intervalo de 80%.
- **Controlo**: probabilidade dada a quem ficou com cada câmara e lugares previstos contra reais.

Só entram as corridas disputadas (as decididas à partida não dizem nada sobre o modelo). Durante a contagem lenta, as corridas sem vencedor ficam listadas como por decidir e fora das métricas, e os lugares reais só aparecem quando todas estiverem decididas.

O mesmo código avalia os backtests (`--backtest 2018`, `2022` ou `2024`):

| Ano  | Câmara: Brier / log-loss | Câmara: lugares D previstos / reais | Senado: Brier / log-loss | Senado: lugares D previstos / reais |
| ---- | ------------------------ | ----------------------------------- | ------------------------ | ----------------------------------- |
| 2018 | 0,046 / 0,142            | 224 / 235                           | 0,050 / 0,151            | 48 / 47                             |
| 2022 | 0,030 / 0,097            | 213 / 213                           | 0,029 / 0,103            | 49 / 51                             |
| 2024 | 0,017 / 0,068            | 217 / 215                           | 0,033 / 0,115            | 48 / 47                             |

Na Câmara, a calibração por faixa fica perto da diagonal nos três anos (por exemplo, em 2022 os favoritos com 80-90% ganharam 90% das vezes e os de 90-95% ganharam 96%).

## 12. Limitações conhecidas

- O PVI e as listas de candidatos vêm da Wikipédia. Os testes guardam os formatos conhecidos e uma linha que não se consegue ler é registada, mas um erro de edição na página pode passar.
- As sondagens de 2026 são as que a Wikipédia lista; algumas corridas seguras não têm nenhuma e ficam só com fundamentos.
- Os estados redesenhados em 2026 perdem a persistência do ciclo anterior, porque o desvio do incumbente era medido noutro distrito.
- Os agregadores do voto genérico são lidos tal como estão na página no momento da execução. Antes do congelamento, cada execução diária usa os valores desse dia.

## 13. Reprodução

```sh
uv run python -m pipeline.jobs.referencia_modelo        # tabelas de 2012 a 2024 (uma vez)
uv run python -m pipeline.jobs.previsao --saida data/publicado/previsao/2026.json \
  --historico data/publicado/previsao/historico-previsao-2026.json
uv run python -m pipeline.jobs.avaliacao_previsao --backtest 2022 --saida avaliacao-2022.json
uv run python -m pipeline.jobs.sensibilidade_previsao --saida sensibilidade.json --markdown sensibilidade.md
```

`--corte AAAA-MM-DD` fixa a data de corte (nunca depois de 1 de novembro de 2026) e `--sem-descarga` usa só as páginas já guardadas em `data/brutos/modelo/`. O resultado valida o contrato `PrevisaoCongresso` (`schemas/src/contratos/previsao.py`).
