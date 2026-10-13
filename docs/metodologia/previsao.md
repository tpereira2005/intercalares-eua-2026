# Metodologia: previsão da Câmara e do Senado

Este documento descreve o modelo próprio do Escrutínio para as eleições de 3 de novembro de 2026 (plano, fase 2). O modelo dá a probabilidade de cada partido controlar a Câmara e o Senado, a distribuição de lugares e uma previsão para cada corrida. Congela-se a **1 de novembro de 2026**, dois dias antes da eleição.

Três regras orientam todas as escolhas:

1. **Simetria.** Nenhum passo depende do partido que favorece. Trocar os partidos em todas as entradas troca exatamente os parâmetros e, dentro do erro de simulação, as probabilidades (há um teste automático para isso).
2. **Só o passado.** Cada previsão usa apenas eleições anteriores. Os backtests de 2018, 2022 e 2024 correm o mesmo código com os dados disponíveis dois dias antes de cada eleição.
3. **Só dados gratuitos e reutilizáveis.** Wikipédia (CC BY-SA 4.0) e o ficheiro `raw_polls.csv` da FiveThirtyEight (CC BY 4.0). Nenhuma API paga.

Todas as margens estão em pontos percentuais do voto total e são sempre **Democrata menos Republicano (D−R)**: positivo favorece o lado democrata, negativo o republicano.

## 1. Dados

| Dado                                                                  | Fonte                                                                                  | Anos         |
| --------------------------------------------------------------------- | -------------------------------------------------------------------------------------- | ------------ |
| Corridas: distrito, Cook PVI, incumbente, candidatos e resultados     | Páginas anuais da Wikipédia ("20XX United States House/Senate elections")              | 2012 a 2026  |
| Voto popular nacional na Câmara                                       | Caixa de informação das páginas anuais (2012 a 2024); `raw_polls.csv` (1998 a 2010)    | 1998 a 2024  |
| Sondagens finais do Senado e do voto genérico                         | `raw_polls.csv` da FiveThirtyEight                                                     | 1998 a 2022  |
| Sondagens do Senado de 2024 e 2026                                    | Páginas de cada corrida na Wikipédia (secções "General election" ou "Polling")         | 2024 e 2026  |
| Voto genérico de 2026                                                 | Agregadores citados na página anual de 2026 (DDHQ, NBC, RealClearPolitics, Silver Bulletin, FiftyPlusOne) | 2026 |
| Estados com mapa novo em 2026                                         | Tabela "Summary of mid-decade changes" da página anual de 2026                         | 2026         |

As tabelas dos anos terminados estão versionadas em `data/reference/modelo/` (ver `data/PROVENIENCIA.md`) e reconstroem-se com `pipeline.jobs.referencia_modelo`. Os dados de 2026 descarregam-se a cada execução, com um User-Agent identificado, espera entre pedidos e cache local.

### Leitura das páginas

As tabelas da Wikipédia mudam de formato entre anos (predefinições diferentes para o PVI, listas de candidatos com e sem `*`, `rowspan` nas sondagens, voto preferencial com duas voltas). O leitor trata cada formato encontrado e os testes guardam um exemplo de cada um. Regras de leitura:

- **Voto preferencial** (Maine e Alasca): a margem usa a primeira volta, comparável às outras corridas; o vencedor é o da última volta.
- **Disputas internas**: quando dois candidatos do mesmo partido têm ambos 20% ou mais (por exemplo Murkowski contra Tshibaka em 2022, ou dois Democratas na Califórnia), a margem D−R não mede a disputa entre partidos e a corrida não entra na estimação.
- **Independentes**: um independente ocupa o lado de um partido quando esse partido não apresenta candidato e o outro sim, ou quando está numa lista explícita (Sanders, King, Osborn, McMullin, Orman e Achilles do lado democrata; Kiley do lado republicano). A regra é a mesma nos dois lados. Os lugares que ganharem contam para a bancada desse lado; as corridas com independentes não entram na estimação dos fundamentos.
- **Corridas decididas**: sem candidato de um dos lados, o vencedor fica certo (ex.: dois Democratas na segunda volta da Califórnia).

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

| Parâmetro           | Câmara | Senado |
| ------------------- | -----: | -----: |
| Inclinação do PVI   |   0,90 |   0,83 |
| Incumbência (pts)   |    6,4 |    6,0 |
| Persistência        |   0,53 |      0 |
| Desvio do ano       |    1,5 |    1,9 |
| Desvio da região    |    1,6 |    2,0 |
| Desvio da corrida   |    7,6 |    7,7 |
| Corridas no treino  |  2 663 |    191 |

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

Fundamentos e sondagens combinam-se com pesos inversamente proporcionais às respetivas variâncias. Numa corrida com 15 institutos, as sondagens pesam cerca de 94%; sem sondagens, fica só a previsão por fundamentos.

## 5. Simulação

20 000 cenários com semente fixa. Em cada cenário sorteiam-se, por esta ordem:

1. um erro nacional comum às duas câmaras (t de Student com 5 graus de liberdade, para caudas mais pesadas do que a normal);
2. um erro na tradução do ambiente para os distritos, por câmara;
3. um choque por região do Census (Nordeste, Centro-Oeste, Sul, Oeste), partilhado pelas duas câmaras;
4. o erro próprio de cada corrida.

Na Câmara, a maioria é 218 de 435. No Senado, somam-se os lugares que não vão a votos (47 democratas e independentes que votam com eles, 53 republicanos antes da eleição); com 50 lugares para cada lado desempata o vice-presidente (republicano no Congresso eleito em 2026).

O ficheiro publicado traz também o **limiar nacional**: a margem no voto genérico a partir da qual o lado democrata passa a favorito ao controlo de cada câmara. Abaixo dele o favorito é o lado republicano, o que permite ler os dois cenários com o mesmo destaque.

## 6. Voto antecipado

O voto antecipado **não altera a previsão** (peso 0). O rastreador tem ciclos comparáveis de poucos estados, e três ou quatro eleições por estado não chegam para estimar quanto um desvio no voto antecipado se traduz em margem final sem sobreajustar. O plano prevê que o sinal entre só na medida em que a metodologia o justifique; por agora é um diagnóstico mostrado ao lado da previsão, nunca dentro dela.

## 7. Backtests

O mesmo código, com o corte dois dias antes de cada eleição e parâmetros estimados só com os anos anteriores:

| Ano  | Câmara | Ambiente previsto / real | P(controlo D) | Lugares D: mediana [p10, p90] | Reais | Corridas erradas | Brier | Viés nas competitivas | Cobertura 80% |
| ---- | ------ | ------------------------ | ------------: | ----------------------------- | ----: | ---------------: | ----: | --------------------: | ------------: |
| 2018 | Câmara | D+7,6 / D+8,6            |           72% | 224 [210, 240]                |   235 |       27 de 412  | 0,045 |                 −3,4  |           88% |
| 2018 | Senado | D+7,6 / D+8,6            |           10% | 48 [44, 50]                   |    47 |        2 de 34   | 0,050 |                 +1,1  |           91% |
| 2022 | Câmara | D−0,7 / R+2,7            |           34% | 213 [198, 227]                |   213 |       18 de 412  | 0,029 |                 +1,2  |           91% |
| 2022 | Senado | D−0,7 / R+2,7            |           49% | 49 [47, 53]                   |    51 |        2 de 33   | 0,030 |                 −0,9  |           76% |
| 2024 | Câmara | D+2,0 / R+2,6            |           49% | 217 [201, 234]                |   215 |        9 de 406  | 0,017 |                 +2,4  |           92% |
| 2024 | Senado | D+2,0 / R+2,6            |           13% | 48 [45, 51]                   |    47 |        1 de 33   | 0,033 |                 +2,7  |           97% |

Notas de leitura:

- O viés é a média de (previsto − real) nas corridas com margem prevista abaixo de 15 pontos. Mudou de sinal entre ciclos (−3,4 a favor do lado republicano em 2018, +2,4 e +2,7 a favor do lado democrata em 2024), o que confirma que não há base para impor uma correção num sentido.
- Em 2024 o ambiente vem das sondagens do Senado, que erraram para o lado democrata; o modelo ficou praticamente empatado na Câmara e deu 73% aos Republicanos no Senado (P(D) + P(R) < 1 nesse ano porque o desempate dependia da eleição presidencial do mesmo dia).
- A cobertura do intervalo de 80% fica entre 76% e 97%: a incerteza está bem calibrada na Câmara e algo larga no Senado.

## 8. Limitações conhecidas

- O PVI e as listas de candidatos vêm da Wikipédia. Os testes guardam os formatos conhecidos e uma linha que não se consegue ler é registada, mas um erro de edição na página pode passar.
- As sondagens de 2026 são as que a Wikipédia lista; algumas corridas seguras não têm nenhuma e ficam só com fundamentos.
- Os estados redesenhados em 2026 perdem a persistência do ciclo anterior, porque o desvio do incumbente era medido noutro distrito.
- Os agregadores do voto genérico são lidos tal como estão na página no momento da execução. Antes do congelamento, cada execução diária usa os valores desse dia.

## 9. Reprodução

```sh
uv run python -m pipeline.jobs.referencia_modelo        # tabelas de 2012 a 2024 (uma vez)
uv run python -m pipeline.jobs.previsao --saida data/publicado/previsao/2026.json
```

`--corte AAAA-MM-DD` fixa a data de corte (nunca depois de 1 de novembro de 2026) e `--sem-descarga` usa só as páginas já guardadas em `data/brutos/modelo/`. O resultado valida o contrato `PrevisaoCongresso` (`schemas/src/contratos/previsao.py`).
