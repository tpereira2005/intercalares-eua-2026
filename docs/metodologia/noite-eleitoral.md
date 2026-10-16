# Metodologia: projeção da noite eleitoral (Modelo C)

O Modelo C atualiza a previsão congelada (`PrevisaoCongresso`, ver `previsao.md`) com os votos que vão sendo contados na noite de 3 de novembro e nos dias seguintes. Publica uma `ProjecaoNoite` por instante de resultados. Nesse ficheiro estão:

- a margem projetada de cada corrida, com o intervalo de 80% e a probabilidade de vitória;
- a fração estimada já contada;
- a probabilidade de controlo e a distribuição de lugares de cada câmara.

O código está em `pipeline/src/pipeline/modelo/noite/`.

## 1. Entradas

- **Resultados parciais** (`ResultadosParciais`, da recolha de resultados).
  - Há uma linha por corrida e por unidade: um condado, ou `total` quando a fonte só dá o total.
  - Cada linha traz os votos do lado democrata, do lado republicano e dos outros candidatos.
  - Quando a fonte as publica, traz também as secções reportadas.
- **Previsão congelada.** Dá a margem prevista e o intervalo de 80% de cada corrida, e o desvio do ambiente nacional e das regiões.
- **Eleição de referência por condado.** É a presidencial anterior (`data/reference/modelo/presidencial_condados_<ano>.csv`, compilada por Tony McGovern, licença MIT).
  - Em 2026 usa-se 2024.
  - Nas repetições de 2022 e 2024 usa-se 2020.
  - Dá a base partidária de cada condado e o voto esperado.

## 2. Uma corrida

Cada unidade `u` tem uma margem de referência `b_u` e um voto esperado `E_u`. Ao fim da contagem, a sua margem é `F_u = b_u + s + e_u`:

- `s` é o desvio da corrida face à referência;
- `e_u` é o desvio próprio do condado (desvio-padrão de 6 pontos; entre presidenciais é de 3 a 5).

Enquanto só está contada uma fração `c_u` da unidade, a parte contada e a que falta diferem:

```
contada:    m_u = F_u + (1 − c_u) · D_u
por contar: r_u = F_u − c_u · D_u
```

`D_u` é a inclinação do voto contado primeiro. Tem uma parte comum à corrida (desvio-padrão de 25 pontos por unidade de fração por contar) e uma parte própria do condado (15 pontos). As duas partes têm **média zero**: o modelo não presume que o voto tardio favorece um partido. Admite apenas que a diferença existe e que desaparece quando a unidade fica completa.

Os valores vêm de 2022. Nesse ano, na Carolina do Norte, na Geórgia e na Carolina do Sul, o voto antecipado e o voto por correspondência ficaram 15 a 45 pontos ao lado do resultado final, umas vezes para um lado e outras para o outro. Sem a parte própria de cada condado, a variação da fração contada entre condados deixaria extrapolar a margem final com uma confiança que os dados não justificam.

**Voto esperado.** Usa-se, por esta ordem:

1. A fração do voto esperado, se a fonte a publicar.
2. As secções reportadas, se a unidade estiver completa. Mesmo assim, presume-se que ainda faltam 2% (provisórios, correio tardio).
3. Caso contrário, a participação face à referência vezes os votos de referência. A participação parte de 0,72 num ano intercalar (2022/2020: 0,71) e aprende-se com as unidades completas.

Sem fração declarada, uma unidade nunca passa dos 90% contados. Os distritos da Câmara sem referência própria somam as partes de condados numa unidade `total` e usam as secções reportadas.

**Estimação.** O prior de `s` vem da previsão congelada: a média é a margem prevista menos a base dos condados, e a variância é a da previsão menos a parte explicada pelos condados. Tudo é linear e normal, por isso a margem final condicionada a `s` e às contagens é normal. A média e a variância calculam-se de forma exata, com a fórmula de Sherman–Morrison para a inclinação comum.

Um condado cujo desvio está a mais de 3 desvios-padrão da mediana pesa menos (ponderação de Huber). Assim, um condado trocado na fonte ou um lote mal lançado não arrasta a corrida.

**Volume do que falta.** Soma-se ainda a incerteza no volume do que falta (15%). Só pesa quando o que falta vota de forma diferente do que já foi contado, e desaparece no início e no fim da contagem.

**Ordem de contagem por estado** (`noite/modos.py`). Alguns estados publicam o voto antecipado de cada condado inteiro logo a seguir ao fecho das urnas, antes do voto do dia da eleição: Carolina do Norte, Geórgia, Florida, Texas e Ohio. Ficam de fora os que contam o correio depois (Pensilvânia, Arizona, Michigan, Wisconsin, Nevada, entre outros) e aqueles em que a ordem não é clara (Carolina do Sul, Iowa). Nesses estados, quando a fonte separa os votos por modo, sabe-se que parte de cada condado já chegou e que parte falta, e o modelo usa isso em vez da inclinação genérica `D_u`:

```
antecipado:        F_u + (1 − π_u) · G_u
resto contado:     F_u − π_u · G_u + (1 − x_u) · λ_u
resto por contar:  F_u − π_u · G_u − x_u · λ_u
```

- `π_u` é a parte antecipada do voto esperado e `x_u` a parte do resto (dia da eleição, provisórios) já contada. As três partes somam `E_u · F_u`.
- `G_u = Δ + Δ_u` é a diferença entre o voto antecipado e o resto: uma parte comum à corrida (desvio-padrão de 25 pontos) e uma parte própria do condado (10 pontos). As duas têm **média zero**: o modelo não sabe à partida que partido ganha o voto antecipado; aprende-o com os condados que já têm os dois modos. Nas repetições de 2022 e 2024, a diferença foi de 0 a 25 pontos na Carolina do Norte, na Geórgia e na Carolina do Sul, para os dois lados, e variou 5 a 10 pontos entre condados da mesma corrida.
- `λ_u` é a inclinação das secções do dia da eleição que chegam primeiro (8 pontos por unidade de fração por contar).
- `π_u` depende do voto esperado, e este da participação estimada. Um erro na participação desloca todos os condados no mesmo sentido, por isso entra como mais um fator comum (desvio de 15%), com efeito `π_u · Ĝ`, em que `Ĝ` é a diferença média já observada entre os dois modos.
- Quando todas as secções de um condado reportaram, o pouco que falta (correio tardio, provisórios) conta como a margem final do condado, sem a diferença entre modos.

O condicionamento é gaussiano e exato, com as mesmas saídas do caso geral (média `alfa + beta · s`, desvio `gama` e a estimativa de `s` só com as contagens) e a mesma ponderação robusta, aplicada dentro de cada modo. Só se usa quando **todas** as unidades com votos são condados com referência própria, com voto antecipado e com os modos a somar o total. Um distrito feito de partes de condados, ou o total de uma corrida, junta condados que já reportaram com outros que não, e a parte antecipada do que falta deixa de se conhecer; nesses casos, e em qualquer estado fora da lista, fica o modelo geral. Na noite de 2026 isto aplica-se às corridas estaduais da Carolina do Norte e, na parte acompanhada, do Texas (Harris): a Geórgia e o Alasca só dão os modos no total, a Florida não os dá, e a Carolina do Sul e o Iowa bloqueiam o GitHub Actions.

**Estados com cobertura parcial.** Em alguns estados só há fonte oficial aberta para alguns condados (por exemplo, a Harris no Texas). Os `ResultadosParciais` dizem-no em `cobertura_parcial`: os outros condados não estão por apurar, estão fora da recolha. O modelo trata estes estados assim:

- **Corrida estadual.** Os condados acompanhados entram como os outros. Os restantes ficam no voto esperado do estado, previstos pelo desvio da corrida, por isso a fração contada é só a parte acompanhada e a corrida nunca se dá por completa. No ensaio de 2024, com a Harris inteira contada (D+11), o TX-S ficou com 14% contado e uma projeção de R+5,9 (resultado: R+8,5), porque a Harris é mais democrata do que o estado.
- **Distritos da Câmara.** As partes de condados de um distrito não dizem quanto falta do distrito, porque o distrito pode sair da zona acompanhada. Os votos contados aparecem, mas o distrito fica sem voto esperado e só aprende pelos fatores comuns (o desvio nacional e o da região).
- **Avaliação.** Nas repetições, as corridas destes estados não entram nas métricas: a soma dos condados acompanhados não é o resultado.

As regras olham só para a cobertura, nunca para o partido, e um teste confirma que trocar os partidos troca a análise.

## 3. As câmaras

A estrutura de erros entre corridas é **exatamente a da previsão congelada** (secção 5 de `previsao.md`), reconstruída a partir dos parâmetros publicados no próprio ficheiro da previsão. A margem final de cada corrida é

```
margem = centro + L · F + erro próprio
```

`F` são os fatores comuns da previsão:

- o erro nacional, uma t de Student com 5 graus de liberdade e o desvio-padrão do ambiente;
- o erro do ano na Câmara;
- o erro do ano nos fundamentos do Senado;
- o erro comum das sondagens do Senado que não acompanha o voto genérico;
- um choque por região do Census, partilhado pelas duas câmaras.

As cargas `L` são as da simulação da previsão:

- na Câmara, 1 no erro nacional, no erro do ano e na região;
- no Senado, dependem do peso `w` das sondagens da corrida: `(1 − w) + w × ligação` no erro nacional, `1 − w` no erro do ano, `w` no erro das sondagens e 1 na região.

O centro e o erro próprio também são os da previsão.

Por isso, **antes de haver votos, a projeção é a previsão congelada**: corrida a corrida, no controlo das câmaras e na distribuição de lugares, a menos do erro de Monte Carlo. Com a previsão de 1 de novembro (ensaio de 13 de outubro), o controlo sem votos ficou entre 72,4% e 73,1% no Senado em quatro sementes, contra 72,9% da previsão; na Câmara ficou entre 96,7% e 97,0%, contra 96,8%. Por corrida, a diferença média foi de cerca de 0 e a maior foi de 1,1 pontos, o que corresponde ao ruído de duas simulações de 20 000 cenários.

As corridas com votos informam os fatores comuns por pesos de precisão. As corridas sem feed (Pensilvânia, Arizona, Texas, Ohio, Michigan, Nevada e Alasca, além das que ainda não fecharam) ficam no prior, deslocadas apenas pelo que as outras já mostraram, e **mantêm a incerteza toda** da previsão.

A t de Student escreve-se como uma mistura de normais com escala aleatória. Cada simulação:

1. sorteia a escala do erro nacional a partir do prior;
2. pesa a escala pela verosimilhança dos votos já contados (amostragem por importância, com reamostragem sistemática); sem votos, os pesos são iguais e cada escala sai exatamente uma vez;
3. sorteia os fatores comuns da normal condicionada a essa escala;
4. sorteia o desvio de cada corrida e, por fim, a margem final.

São 20 000 simulações antitéticas. Os lugares somam-se com as corridas decididas e com os lugares que não vão a votos. Um Senado 50-50 é decidido pelo partido do vice-presidente.

Os sorteios antitéticos tornam a simulação exatamente simétrica: trocar os partidos em todas as entradas troca exatamente todas as saídas, e há um teste que o confirma.

## 4. Testes

`pipeline/tests/modelo/test_noite_eleitoral.py` usa noites sintéticas com resultado conhecido e verifica que:

- sem votos, a projeção é a previsão, corrida a corrida e no controlo das câmaras (diferença de controlo abaixo de 1,5 pontos e variação total entre as distribuições de lugares abaixo de 0,04);
- com tudo contado e declarado completo, a projeção é o resultado;
- trocar os partidos troca a projeção;
- os intervalos de 80% contêm o resultado entre 72% e 95% das vezes em cada fase da contagem;
- o Brier desce à medida que se conta;
- uma corrida sem feed mantém pelo menos 60% da largura do intervalo prior.

`pipeline/tests/modelo/test_ordem_contagem_noite.py` faz o mesmo para a ordem de contagem, com corridas de 40 condados em que o voto antecipado chega inteiro e primeiro, com uma diferença de sinal aleatório. Verifica que o caminho por modos só se usa nas condições acima, que trocar os partidos troca a análise, que com tudo contado a margem é a contada, que os intervalos de 80% contêm o resultado entre 72% e 95% das vezes (79% a 81% em 900 corridas) e que, com metade dos condados só com o voto antecipado, o erro da margem projetada fica abaixo de 70% do erro sem os modos.

## 5. Repetição com 2022 e 2024

`pipeline.jobs.repeticao_noite` repete as noites com os resultados oficiais que o ensaio da recolha de resultados descarrega: Carolina do Norte, Geórgia e Carolina do Sul em 2022 e em 2024, Florida e Iowa em 2024.

As fontes só guardam o resultado final, por isso a ordem da noite é reconstruída. Há duas reconstruções:

- **ensaio**: a do ensaio da recolha, em que os condados chegam inteiros por ordem aleatória;
- **modos**: em cada condado chega primeiro o voto antecipado e por correspondência, depois o dia da eleição aos poucos e no fim os provisórios. É a mais exigente, porque cada condado passa por estados parciais com a inclinação real do voto antecipado.

Nenhuma é a sequência real da noite, por isso estes números medem a coerência do modelo e não a sua calibração temporal exata. O ponto de partida é a previsão do backtest de cada ano. As reconstruções foram refeitas a 14 de outubro, depois da correção dos modos da Carolina do Norte (ver abaixo), já com a ordem de contagem, e de novo a 16 de outubro, com as classificações dos especialistas na previsão de partida (só 2022 mudou, e pouco):

| Repetição    | Brier no 1.º passo | Brier a 50–60% contado | Cobertura 80% (mín.–máx.) | Maior probabilidade dada a quem perdeu | Chamadas erradas (≥ 99%) |
| ------------ | -----------------: | ---------------------: | ------------------------: | -------------------------------------- | -----------------------: |
| 2022, ensaio |         0,027 (7%) |                  0,008 |                 0,89–0,97 | NC-13 0,73; GA-S 0,51                  |                        0 |
| 2022, modos  |         0,026 (4%) |                  0,007 |                 0,94–1,00 | NC-13 0,71; GA-S 0,60                  |                        0 |
| 2024, ensaio |        0,002 (10%) |                  0,002 |                 0,78–1,00 | IA-01 0,60; NC-01 0,44                 |                        0 |
| 2024, modos  |        0,002 (22%) |                  0,002 |                 0,88–1,00 | IA-01 0,51; NC-01 0,32                 |                        0 |

Leitura:

- **Nenhuma chamada errada.** Em nenhuma repetição o modelo chegou a dar 99% a quem acabou por perder.
- **NC-S 2022, a corrida onde a ordem de contagem pesa.** O voto antecipado de Beasley (D) chega primeiro e o dia da eleição, mais republicano, depois. Sem a ordem de contagem, o modelo geral começava em D+2,6 com 75% para Beasley e só passava para o lado de Budd (R) a meio da contagem. Com ela, começa em R+4,9 (intervalo de 80% de R+8 a R+1, 4% para Beasley); o resultado foi R+3,2. Até cerca de metade contada a projeção fica 1 a 2,5 pontos demasiado republicana, dentro do intervalo ou na sua borda. Na Carolina do Sul de 2022, tratada como se estivesse na lista só para este teste, o SC-S arranca em R+25,5 contra R+17,8 sem os modos, para um resultado de R+25,9, sempre dentro do intervalo.
- **GA-S 2022.** O voto antecipado de Warnock (D+7) seguido do dia da eleição de Walker (R+15) fez a projeção oscilar, como seria de esperar. A Geórgia só dá os modos no total, por isso fica no modelo geral. O pico de 60% para Walker vem da NC-S, que agora puxa mais cedo o desvio nacional para o lado republicano.
- **2024.** Nenhuma corrida reúne as condições (a Carolina do Norte não teve Senado), por isso os números são os do modelo geral. A projeção afasta-se cedo da previsão (desvio nacional de cerca de 2,5 pontos para o lado republicano no fim), o que bate certo com o erro real da previsão desse ano.
- **Intervalos largos.** Estão um pouco largos (cobertura acima de 80%), o que é preferível numa noite em que as fontes falham. Os parâmetros não foram afinados com estas repetições.

Durante a repetição apareceram dois problemas nos dados do ensaio da Carolina do Norte de 2022, comunicados à recolha de resultados e já corrigidos: os FIPS de quatro condados (Macon, Madison, Martin e McDowell) e os rótulos do voto antecipado (`ovc`, one-stop) e do dia da eleição (`evc`), que estavam trocados (PR #64).

## 6. Publicação na noite eleitoral

O job `pipeline.jobs.projecao_noite` corre no workflow `noite.yml`, ao mesmo tempo que a recolha de resultados (workflow `resultados.yml`):

1. No arranque, descarrega a previsão congelada (`previsao-2026.json`, da Release `dados-previsao`). Recusa uma previsão ainda não congelada.
2. A cada 30 segundos, pede o `parciais.json` da Release `resultados-2026` com um pedido condicional. Só calcula quando chega um instante mais recente do que o último projetado.
3. Calcula a projeção e verifica-a antes de publicar:
   - estão todas as corridas da previsão;
   - as probabilidades de controlo não somam mais de 1;
   - a distribuição de lugares soma 1;
   - os percentis estão por ordem.
4. Escreve e envia para a Release `dados-noite` dois ficheiros:
   - `projecao-noite-2026.json` (contrato `ProjecaoNoite`): o retrato completo do instante;
   - `historico-noite-2026.json` (contrato `HistoricoNoite`): a evolução ao longo da noite, com a probabilidade, a margem projetada e o intervalo de 80% de cada corrida com votos. Os pontos guardados distam pelo menos 5 minutos, e o último é sempre o mais recente.

Um ciclo que falha (fonte em baixo, ficheiro inválido, verificação falhada) não apaga nada: o último ficheiro válido continua publicado. Cada job dura no máximo 6 horas. Com a hora `ate`, o workflow volta a lançar-se, e o job seguinte continua o histórico já publicado.

O carimbo temporal de cada ficheiro tem duas partes:

- `instante`: o momento dos resultados usados;
- `metadados.gerado_em`: o momento do cálculo.

Os dois ficheiros dizem ainda se partiram da previsão congelada (`prior_congelado`) e se os resultados são uma reconstrução (`reconstruido`, verdadeiro nos ensaios). O site deve assinalar qualquer ficheiro que não seja congelado e real.

**Ensaio.** Todas as segundas-feiras, o mesmo workflow reconstrói a noite de 2024 na Carolina do Norte, na Geórgia, na Carolina do Sul, no Iowa e na Florida. Um estado cuja fonte recuse pedidos automáticos fica de fora, com um aviso, e o bloqueio nunca se contorna. Desde 13 de outubro, o Clarity da Carolina do Sul responde ao GitHub Actions com um desafio anti-robô. Depois corre o job passo a passo, a partir da previsão do backtest de 2024, e valida os ficheiros. À mão, com `publicar_ensaio`, os ficheiros de 2024 vão para a mesma Release (`projecao-noite-2024.json` e `historico-noite-2024.json`), o que permite desenvolver a página com dados reais antes da noite.

**Ensaio ao vivo.** No ensaio com carga, a recolha serve a noite de 2024 na Release `resultados-ensaio`. O modo `ensaio-vivo` segue o `parciais.json` dessa Release como se fosse a noite, parte da previsão do backtest de 2024 (`--backtest 2024`) e publica `projecao-noite-2024.json` e `historico-noite-2024.json` na mesma Release. Aceita também a hora `ate`.

**Na noite.** Lançar à mão os workflows Resultados e Projeção da noite, ambos em modo `noite` e com a mesma hora `ate` (por exemplo, `2026-11-04T12:00`).

## 7. Limitações

- A inclinação do voto contado primeiro, e a diferença entre modos na ordem de contagem, são independentes entre corridas. Na realidade, o correio inclina para o mesmo lado em todo o país, o que torna a incerteza das câmaras no início da noite um pouco estreita. O desvio nacional aprende com as corridas já avançadas, o que compensa em parte.
- Sem fração do voto esperado nas fontes (nenhuma das atuais a publica), o volume do que falta depende da participação estimada e das secções. Por isso o modelo nunca dá uma unidade por completa sem a fonte o dizer.
- Os distritos da Câmara não têm referência própria por condado (os condados são partidos pelos distritos), por isso aprendem menos com os primeiros votos do que as corridas ao Senado.
