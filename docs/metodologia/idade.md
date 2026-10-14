# Metodologia: sinal etário do voto antecipado

Este é o modelo da secção 6.4 do plano: até que ponto o perfil do voto antecipado (idade e partido de registo) diz algo sobre a margem final. É um **diagnóstico mostrado, com peso zero na previsão**. Os backtests abaixo explicam porquê.

Só a Carolina do Norte tem os ficheiros completos para o fazer de ponta a ponta: eleitores, boletins e histórico de voto de cada eleição desde 2016. O código está em `pipeline/src/pipeline/modelo/idade.py`, o job em `pipeline.jobs.idade_nc` e o contrato é `DiagnosticoIdade` (`schemas/src/contratos/idade.py`).

## 1. Grupos

São 21 grupos: sete faixas etárias (18-24, 25-29, 30-39, 40-49, 50-64, 65-74, 75+) vezes três partidos de registo (democrata, republicano e não filiado). Os poucos eleitores de outros partidos juntam-se aos não filiados, e os de idade desconhecida ficam de fora.

## 2. Eleitorado final projetado

O voto antecipado de cada grupo até `d` dias antes da eleição multiplica-se pela razão entre o eleitorado final e o voto antecipado até ao mesmo dia nas eleições do mesmo tipo. Para 2026, essas eleições são as intercalares de 2018 e 2022. O eleitorado final de cada ano vem de `cubo_final_{ano}.parquet` e inclui toda a gente que votou, antecipadamente ou no dia.

Nos backtests, a composição projetada fica mais perto da final do que a da eleição anterior a partir de duas semanas antes. A tabela mostra o erro da composição em pontos de quota (metade da soma das diferenças absolutas):

| Dias antes | 2018 (com 2022) | 2022 (com 2018) | 2024 (com 2016 e 2020) | Composição da eleição anterior |
| ---------: | --------------: | --------------: | ---------------------: | -----------------------------: |
|         14 |             4,1 |             4,3 |                    5,3 |                      5,0 a 6,6 |
|          7 |             3,2 |             3,4 |                    2,6 |                      5,0 a 6,6 |
|          3 |             1,9 |             1,9 |                    1,3 |                      5,0 a 6,6 |

Três semanas antes, o voto antecipado presencial ainda não começou, e a projeção não vale mais do que a composição anterior.

## 3. Margem de cada grupo

A margem D-R de cada grupo estima-se por regressão ecológica nos 100 condados, com os resultados presidenciais de 2020 e 2024 (tonmcg, licença MIT) e a composição do eleitorado final de cada condado. O modelo é `logit q = μ_partido + a_faixa`, em que `q` é a parte democrata dos dois partidos. A penalização puxa os efeitos para zero, o que mantém as margens entre −100 e +100 e é simétrico entre partidos. Há seis versões: dois anos e três penalizações (0,5, 2 e 8). A central é 2024 com penalização 2, e as outras dão a incerteza.

Na versão central, os democratas registados votam D+94 a D+95, os republicanos R+97 e os não filiados entre D+1 e D+11, mais democratas entre os mais novos. A regressão ecológica não vê a raça nem o voto cruzado dentro do condado. Por isso estes números são aproximados: provavelmente exageram a lealdade dos democratas registados nas zonas rurais do leste. O efeito publicado depende sobretudo da diferença entre democratas e republicanos e muda pouco entre versões (ver o intervalo).

## 4. Inclinação da participação e o sinal

A inclinação `T = Σ (v_g − r_g) · m_g` mede quantos pontos de margem o eleitorado puxa face aos eleitores registados desse ano. `v` são as quotas dos votantes, `r` as dos registados e `m` as margens dos grupos. Comparar com os registados do próprio ano retira a deriva do registo partidário. Entre 2016 e 2024, a vantagem democrata no registo caiu de 9 para 1 ponto: muitos democratas conservadores passaram a não filiados ou republicanos, o que muda a composição sem mudar o voto.

Inclinação real do eleitorado final (margens centrais):

| Ano | 2016 | 2018 | 2020 | 2022 | 2024 |
| --- | ---: | ---: | ---: | ---: | ---: |
| `T` | −3,4 | −2,4 | −2,9 | −5,0 | −3,2 |

O sinal publicado é `T` projetado para 2026 menos `T` de 2022, a intercalar anterior. Um valor positivo quer dizer que o eleitorado de 2026 puxa mais para os democratas do que o de 2022, face aos registados de cada ano.

## 5. Backtests e intervalo

Cada ano projeta-se com as eleições do mesmo tipo, sem ele próprio (as intercalares só têm uma referência cada uma). Inclinação real e projetada, em pontos:

| Dias antes |        2016 |        2018 |        2020 |        2022 |         2024 | Erro quadrático médio |
| ---------: | ----------: | ----------: | ----------: | ----------: | -----------: | --------------------: |
|         14 | −3,4 / +0,1 | −2,4 / −5,7 | −2,9 / +3,5 | −5,0 / −1,9 | −3,2 / −11,8 |                   5,4 |
|          7 | −3,4 / −1,6 | −2,4 / −4,4 | −2,9 / +0,1 | −5,0 / −3,0 |  −3,2 / −7,4 |                   2,8 |
|          3 | −3,4 / −2,0 | −2,4 / −4,4 | −2,9 / −1,9 | −5,0 / −3,0 |  −3,2 / −5,3 |                   1,7 |

O intervalo de 80% junta esse erro, no mesmo dia, com a dispersão entre as seis versões das margens.

Leitura:

- **O sentido acerta mais vezes do que a magnitude.** Entre as duas intercalares, a inclinação foi 2,6 pontos mais republicana em 2022 do que em 2018. A projeção a 7 dias deu a diferença com o sentido certo, mas só com cerca de um quarto do tamanho, porque a curva de chegada da única referência puxa a projeção para essa referência.
- **As presidenciais de 2020 e 2024 são más referências** para o momento do voto, por causa da pandemia e da mudança para o voto antecipado presencial. Daí os erros grandes a 14 dias.
- Com duas referências intercalares (2018 e 2022), a projeção de 2026 deve ser mais estável, mas isso não se pode testar antes da eleição.

Com estes números, o sinal não tem lugar na previsão: um erro de 2 a 3 pontos na inclinação, a uma semana da eleição, é da mesma ordem do próprio sinal. Fica como diagnóstico mostrado, com o intervalo e os backtests no próprio ficheiro.

## 6. Simetria

O modelo trata os partidos da mesma forma: as penalizações são simétricas em torno de zero e não há constantes por partido. `pipeline/tests/modelo/test_sinal_idade.py` troca democratas e republicanos em todos os cubos e as margens dos condados, e verifica que o sinal, o intervalo e as margens dos grupos trocam de sinal exatamente.

## 7. Publicação

`pipeline.jobs.idade_nc` corre a seguir ao job do voto antecipado da Carolina do Norte, com o cubo demográfico de 2026 que esse job grava. Escreve `idade-nc.json`. O dia dos dados é o último com voto antecipado no cubo. Com menos de 10 000 votos antecipados não escreve nada.
