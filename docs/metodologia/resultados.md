# Resultados da noite eleitoral

O site mostra os resultados oficiais tal como cada estado os publica, recolhidos a cada 30 segundos. Não há chamadas de vencedor nem projeções neste módulo: a projeção é do Modelo C, que lê estes ficheiros.

## 1. Estados e fontes

Verificámos a 13 de outubro de 2026 os feeds oficiais de resultados dos estados prioritários e das corridas ao Senado mais disputadas.

| Estado            | Fonte                                                       | Formato                     | Condados                   | Tipo de voto | 2022 e 2024 no mesmo formato |
| ----------------- | ----------------------------------------------------------- | --------------------------- | -------------------------- | ------------ | ---------------------------- |
| Carolina do Norte | NCSBE, `er.ncsbe.gov/enr/<data>/data/results_<n>.txt`       | JSON, estado + 100 condados | Sim                        | Sim          | Sim                          |
| Florida           | Division of Elections, `<data>_ElecResultsFL.txt`           | Texto por tabulações        | Sim                        | Não          | 2024 (o de 2022 está a zero) |
| Geórgia           | Secretary of State, API `results.sos.ga.gov`                | JSON                        | Só o total (159 ficheiros) | Sim          | Sim                          |
| Carolina do Sul   | Clarity, `enr-scvotes.org`                                  | XML (`detailxml.zip`)       | Sim                        | Sim          | Sim                          |
| Iowa              | Clarity, `results.enr.clarityelections.com/IA`              | XML (`detailxml.zip`)       | Sim                        | Sim          | 2024                         |
| Nebraska          | `electionresults.nebraska.gov` (CSV)                        | CSV                         | ·                          | ·            | Não (a acrescentar)          |
| De fora           | Pensilvânia, Arizona, Texas, Ohio, Michigan, Nevada, Alasca | ·                           | ·                          | ·            | ·                            |

Os sites de resultados dos estados "de fora" recusam pedidos automáticos (Cloudflare, Incapsula, Akamai) ou não responderam. Não contornamos esses bloqueios. Para essas corridas, o site mostra a previsão e indica que os resultados ao vivo não estão disponíveis numa fonte oficial aberta.

Os identificadores das eleições de 2026 na Carolina do Sul e no Iowa (sites Clarity) só existem quando o estado cria a página; acrescentam-se em `connectors/results/clarity/conector.py`. Até lá, a recolha salta esses estados com um aviso.

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

## 4. Ensaio geral

`pipeline.jobs.ensaio_resultados` descarrega os ficheiros finais de 2022 e 2024 no formato da noite e reconstrói uma noite com 20 retratos, revelando os condados por uma ordem aleatória (na Geórgia, uma fração crescente dos votos). As fontes não guardam os retratos intermédios, por isso a ordem é **reconstruída** e os ficheiros vêm marcados com `reconstruido: true`. O ensaio falha se um retrato não validar, se algum total descer, se o último retrato não coincidir com o resultado oficial ou se um passo passar de 5 segundos.

A 13 de outubro de 2026, as 8 noites (NC, FL, GA, SC e IA, 2022 e 2024) passaram sem falhas, com o passo mais lento abaixo de 0,3 segundos.

O workflow corre o ensaio todas as semanas e guarda os instantes como artefactos, para a repetição do Modelo C.

## 5. Avaliação da previsão

`pipeline.jobs.resultados_avaliacao` escreve o CSV `id,vencedor,margem` que `pipeline.jobs.avaliacao_previsao` lê. Só entram corridas com todas as secções apuradas e um candidato democrata ou republicano à frente; a margem é D−R em pontos percentuais do total.
