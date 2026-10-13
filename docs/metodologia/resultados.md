# Resultados da noite eleitoral

O site mostra os resultados oficiais tal como cada estado os publica, recolhidos a cada 30 segundos. Não há chamadas de vencedor nem projeções neste módulo: a projeção é do Modelo C, que lê estes ficheiros.

## 1. Estados e fontes

Verificámos a 13 de outubro de 2026 os feeds oficiais de resultados dos estados prioritários e das corridas ao Senado mais disputadas.

| Estado            | Fonte                                                                                           | Formato                     | Condados                        | Tipo de voto | 2022 e 2024 no mesmo formato |
| ----------------- | ----------------------------------------------------------------------------------------------- | --------------------------- | ------------------------------- | ------------ | ---------------------------- |
| Carolina do Norte | NCSBE, `er.ncsbe.gov/enr/<data>/data/results_<n>.txt`                                           | JSON, estado + 100 condados | Sim                             | Sim          | Sim                          |
| Florida           | Division of Elections, `<data>_ElecResultsFL.txt`                                               | Texto por tabulações        | Sim                             | Não          | 2024 (o de 2022 está a zero) |
| Geórgia           | Secretary of State, API `results.sos.ga.gov`                                                    | JSON                        | Só o total (159 ficheiros)      | Sim          | Sim                          |
| Carolina do Sul   | Clarity, `enr-scvotes.org` (bloqueado no Actions, ver abaixo)                                   | XML (`detailxml.zip`)       | Sim                             | Sim          | Sim                          |
| Iowa              | Clarity, `electionresults.iowa.gov/IA` (idem)                                                   | XML (`detailxml.zip`)       | Sim                             | Sim          | 2024                         |
| Nebraska          | `electionresults.nebraska.gov` (CSV)                                                            | CSV                         | ·                               | ·            | Não (a acrescentar)          |
| Alasca            | Division of Elections, `elections.alaska.gov/enr26/results/GA_ENR_Precinct_State_of_Alaska.csv` | CSV por secção              | Não (o Alasca não tem condados) | Sim          | 2024 (`ENRbyPrecinct.csv`)   |
| De fora           | Pensilvânia, Arizona, Texas, Ohio, Michigan, Nevada                                             | ·                           | ·                               | ·            | ·                            |

Os sites de resultados dos estados "de fora" recusam pedidos automáticos. Um diagnóstico a 13 de outubro de 2026, a partir do GitHub Actions, encontrou desafios anti-robô do Cloudflare no Arizona (`results.arizona.vote`), no Texas (`results.texas-election.com`), no Michigan (`mielections.us`) e no Ohio (`ohiosos.gov`), do Imperva no Nevada (`silverstateelection.nv.gov`) e do Incapsula na Pensilvânia (`electionreturns.pa.gov`; a API respondeu ao Actions nesse dia, mas o site está protegido contra robôs, por isso não a usamos). Não contornamos esses bloqueios. Para essas corridas, o site mostra a previsão e indica que os resultados ao vivo não estão disponíveis numa fonte oficial aberta.

### Condados com fonte aberta nos estados bloqueados

Nos estados cujo site estadual recusa pedidos automáticos, acompanham-se os condados com fonte oficial aberta que responde ao Actions sem desafios. A cobertura é sempre marcada como parcial: `ResultadosEstado.cobertura = "condados"` com a lista `condados_cobertos`, a mesma marca no resumo nacional e, nos parciais do Modelo C, `cobertura_parcial` com as unidades só desses condados (nunca um `total` do estado). Os totais destas corridas são a soma dos condados acompanhados, **não** o resultado do estado, e ficam fora do CSV de avaliação da previsão.

| Condado                  | Fonte                                                                                | Estado (13 de outubro de 2026)                                                                                                |
| ------------------------ | ------------------------------------------------------------------------------------ | ----------------------------------------------------------------------------------------------------------------------------- |
| Harris (Texas, 48201)    | Harris County Clerk, `appfiles.harrisvotes.com/.../Data/<mmaa>/resultsbyballot.json` | **Acompanhado.** JSON por eleição com votos por tipo e secções apuradas; 2022 e 2024 no mesmo formato (ensaio semanal)        |
| Travis (Texas)           | Clarity                                                                              | Bloqueado (AWS WAF, como os outros sites Clarity)                                                                             |
| Pima (Arizona)           | Relatórios-resumo em PDF, em endereços que só se conhecem quando são publicados      | Sem feed estruturado; o site Clarity do condado também recusa pedidos                                                         |
| Clark e Washoe (Nevada)  | Painéis do condado                                                                   | Sem feed estruturado encontrado; o painel de Washoe responde `503` fora de período eleitoral                                  |
| Cuyahoga (Ohio)          | Relatórios-resumo em PDF (`GetDocumentById/<guid>`)                                  | Sem feed estruturado; os endereços só se conhecem quando são publicados                                                       |
| Filadélfia (Pensilvânia) | Serviço web do condado (`phillyresws.azurewebsites.us`)                              | Responde ao Actions; o método dos votos ainda não foi identificado. Corridas federais não renhidas, por isso baixa prioridade |

Os condados que usam o Clarity (Dallas, Tarrant, Travis, Oakland, entre outros) têm o mesmo bloqueio do AWS WAF descrito abaixo.

O Alasca estava "de fora" por um erro de configuração, não por um bloqueio: o servidor envia o certificado intermédio errado e a verificação TLS falhava. Os navegadores resolvem isto descarregando o intermédio que o próprio certificado indica (AIA). O pipeline faz o mesmo de forma fixa: `pipeline/src/pipeline/comum/dados/intermedios.pem` guarda esse intermédio público da GlobalSign, verificado contra a raiz GlobalSign R46 e com a impressão digital fixada num teste, e `contexto_tls` junta-o aos certificados de confiança habituais. A verificação do certificado e do nome continua igual. O Alasca não tem condados, por isso só há o total do estado; uma secção conta como apurada quando tem boletins ou a fonte a marca como reportada.

Os identificadores das eleições de 2026 na Carolina do Sul e no Iowa (sites Clarity) só existem quando o estado cria a página. O conector procura-os na lista `elections.json` que o próprio site publica (o Iowa usa-a; a Carolina do Sul devolve uma lista vazia, por isso o identificador acrescenta-se à mão em `connectors/results/clarity/conector.py`). Até lá, a recolha salta esses estados com um aviso.

A 13 de outubro de 2026, o ficheiro da Florida (`flelectionfiles.floridados.gov`, servido pela Azure Front Door) respondeu uma vez `403` ao Actions e passou na repetição. Não é um bloqueio a robôs (não há desafio, e a resposta seguinte foi normal); na noite eleitoral, uma falha isolada mantém publicado o último ficheiro válido e o ciclo seguinte volta a tentar.

### Clarity e o GitHub Actions

Os sites Clarity (Carolina do Sul, Iowa e os condados que o usam) estão atrás de um AWS WAF. A 13 de outubro de 2026, um diagnóstico a partir do GitHub Actions mostrou que todos os pedidos recebem `202 Accepted`, corpo vazio e o cabeçalho `x-amzn-waf-action: challenge`, com ou sem User-Agent e cabeçalhos de navegador: é um desafio anti-robô em JavaScript dirigido aos endereços do Actions. Fora do Actions, os mesmos pedidos com o nosso User-Agent identificado recebem os ficheiros normalmente.

Resolver o desafio seria contornar o bloqueio, por isso não o fazemos. O pipeline passou a reconhecer estes desafios (`verificar_resposta` em `pipeline.comum.descarga`, também para o `cf-mitigated` do Cloudflare) e trata-os como `ErroBloqueio`: o estado fica sem resultados ao vivo e o registo diz porquê, em vez de um 202 vazio passar por um ficheiro válido. Os ensaios da Carolina do Sul e do Iowa continuam no workflow semanal, sem o pintar de vermelho, para se ver quando o bloqueio acaba. Os conectores e os ensaios funcionam fora do Actions (verificado a 13 de outubro com as noites de 2022 e 2024).

## 2. Ciclo de recolha

`pipeline.jobs.resultados` corre num job do GitHub Actions (`.github/workflows/resultados.yml`, modo `noite`) até quase 6 horas e relança-se até à hora indicada. Em cada ciclo de 30 segundos:

1. Pede a cada estado o ficheiro principal com pedidos condicionais (ETag, Last-Modified). Na Carolina do Norte, os 100 ficheiros dos condados só se pedem quando o ficheiro do estado mudou, 8 de cada vez.
2. Quando algo mudou, lê, valida e escreve `<estado>.json` (contrato `ResultadosEstado`), `nacional.json` (`ResultadosNacional`) e `parciais.json` (`ResultadosParciais`, a entrada do Modelo C), e envia-os para a Release `resultados-2026`.
3. Compara com o retrato anterior. Uma descida de totais ou de secções apuradas fica registada; os números publicados são sempre os da fonte, sem alisamento.
4. Guarda uma cópia dos ficheiros da fonte e de cada `parciais.json`. No fim do job vão para um artefacto, para rever a noite e para futuros ensaios com a ordem real.

Um estado que falha não para os outros: o último ficheiro válido continua publicado.

## 3. Definições

- **Identificadores**: os mesmos da previsão (`NC-S`, `PA-08`, `OH-S-especial`), e `XX-G` para governador.
- **Partidos**: o rótulo da fonte passa a `dem`, `rep` ou `outro`. Nenhuma regra trata um partido de forma diferente; o teste `test_troca_de_rotulos_partidarios_troca_o_resumo` confirma que trocar os rótulos troca os resultados e nada mais.
- **Apuramento**: secções (ou condados, na Geórgia) com resultados sobre o total. Não é a fração do voto contado: na noite, o voto por correspondência pode chegar depois de todas as secções.
- **Tipo de voto**: dia da eleição, antecipado presencial, correspondência e provisório, quando a fonte os separa.
- **Voto preferencial** (Maine, Alasca): só a primeira volta.
- **Lugar único na Câmara** (Alasca e outros estados com um só distrito): a corrida chama-se só "U.S. Representative" e o identificador é `XX-00`, como na previsão.

## 4. Ensaio geral

`pipeline.jobs.ensaio_resultados` descarrega os ficheiros finais de 2022 e 2024 no formato da noite e reconstrói uma noite com 20 retratos, revelando os condados por uma ordem aleatória (na Geórgia, uma fração crescente dos votos). As fontes não guardam os retratos intermédios, por isso a ordem é **reconstruída** e os ficheiros vêm marcados com `reconstruido: true`. O ensaio falha se um retrato não validar, se algum total descer, se o último retrato não coincidir com o resultado oficial ou se um passo passar de 5 segundos.

A 13 de outubro de 2026, as 8 noites (NC, FL, GA, SC e IA, 2022 e 2024) passaram sem falhas fora do Actions, com o passo mais lento abaixo de 0,3 segundos. No Actions, as da Carolina do Sul e do Iowa param no desafio do AWS WAF (secção 1).

O workflow corre o ensaio todas as semanas e guarda os instantes como artefactos, para a repetição do Modelo C.

## 5. Avaliação da previsão

`pipeline.jobs.resultados_avaliacao` escreve o CSV `id,vencedor,margem` que `pipeline.jobs.avaliacao_previsao` lê. Só entram corridas com todas as secções apuradas e um candidato democrata ou republicano à frente; a margem é D−R em pontos percentuais do total.
