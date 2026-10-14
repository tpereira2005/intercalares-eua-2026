# Voto antecipado nos outros estados e resumo nacional

A Carolina do Norte (ver [voto-antecipado.md](voto-antecipado.md)) é o único estado prioritário com ficheiro de eleitores gratuito: só lá se calculam taxas de participação por grupo. Nos outros estados, o site usa o que cada fonte oficial gratuita publica e diz claramente o que não é possível medir.

## 1. Que estados e porquê

Verificámos a 13 de outubro de 2026, a partir do GitHub Actions (onde o pipeline corre), as fontes dos estados prioritários do plano.

| Estado                                     | Fonte                                                                               | Granularidade                                                                            | Idade                 | Comparação                      |
| ------------------------------------------ | ----------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------- | --------------------- | ------------------------------- |
| Pensilvânia                                | Pedidos de voto por correspondência em data.pa.gov (diário, sem nomes)              | Um registo por boletim: condado, partido, mês de nascimento, distrito, datas             | Sim                   | 2022 e 2024, mesmo dia do ciclo |
| Maine                                      | "Absentee Voter File" do Secretary of State (algumas vezes por semana)              | Um registo por boletim: município, partido, distrito, modalidade, datas                  | Não                   | 2022, 2018 e 2024               |
| Florida                                    | Estatísticas diárias da Division of Elections                                       | Totais por condado e partido                                                             | Não                   | Só a série que nós guardamos    |
| Geórgia, Texas                             | Ficheiros diários existem, mas o servidor bloqueia pedidos automáticos              | ·                                                                                        | ·                     | ·                               |
| Michigan, Ohio, Nevada, Arizona (Maricopa) | Painéis oficiais com o mesmo bloqueio                                               | ·                                                                                        | ·                     | ·                               |
| Iowa                                       | Relatórios diários em PDF do Secretary of State (por distrito e por condado)        | Totais por distrito, condado, partido e forma de receção                                 | Não                   | 2022 e 2024, mesmo dia do ciclo |
| Colorado                                   | Folha de cálculo diária do Secretary of State (a mesma informação do resumo em PDF) | Totais por condado, partido de registo, género e faixa de dez anos, correio e presencial | Sim (faixas da fonte) | 2022 e 2024, mesmo dia do ciclo |
| Carolina do Sul                            | Relatórios da Election Commission (scvotes.gov), finais de 2022 e 2024              | Totais por condado e raça (sem partido nem idade)                                        | Não                   | Extensão possível, não feita    |

A Carolina do Sul fica como extensão possível: sem partido nem idade, só com o retrato final do voto por correspondência nos anos anteriores e sem os ficheiros de 2026 publicados a 13 de outubro, o ganho é pequeno.

Não contornamos bloqueios a robôs (desafios do Cloudflare, Akamai ou Incapsula): seria contra as condições das fontes. Esses estados ficam de fora até haver uma via oficial aberta.

## 2. O que se mede sem ficheiro de eleitores

Sem os recenseados de cada grupo, não há taxa de participação. Compara-se **votos com votos**, no mesmo dia do ciclo (dias antes da eleição), como na Carolina do Norte:

- **Composição**: quota de cada faixa etária, partido ou modalidade nos votos antecipados de 2026 e do ano de referência.
- **Geografia**: votos até ao mesmo dia do ciclo por condado e distrito (mapa em vigor em 2026), por partido e, onde há idade (Pensilvânia), por faixa larga. As linhas por faixa têm `partido = "total"`; as linhas por partido têm `faixa = "total"`. No Iowa, o mapa por condado é só o do último dia de 2026.
- **Ritmo**: votos de 2026 / votos do ano de referência no mesmo dia − 1, para o total e para cada categoria.
- **Pedidos por devolver**: boletins por correspondência pedidos até ao dia, quantos já voltaram e quantos faltam, por partido e faixa. É o equivalente, nestes estados, da reserva restante.

Um ritmo positivo diz que há mais boletins do que no mesmo dia de 2022; não diz que a participação final será maior, porque as regras e os hábitos de voto mudam entre ciclos (ver os avisos de cada estado).

## 3. Definições por estado

- **Pensilvânia**: só há voto por correspondência (incluindo o pedido e entregue no balcão do condado). Um boletim conta como devolvido quando tem data de devolução e não foi cancelado. Desde 2024 a fonte junta os não filiados e os pequenos partidos em "OTH", por isso, em todos os anos, quem não é democrata nem republicano fica em `outro`. A idade é a do fim do ano da eleição, calculada a partir do ano de nascimento. O mapa dos distritos é o mesmo desde 2022.
- **Maine**: conta um boletim por eleitor (a primeira receção, quando houve um duplicado). O voto na presença do funcionário municipal (`VP`) é o voto antecipado presencial; tudo o resto é correspondência. Em 2022 o voto presencial começou a 11 de outubro, seis dias mais tarde no ciclo do que em 2026. Não há idade.
- **Iowa**: o Secretary of State publica, para cada eleição, PDF cumulativos com um relatório por dia (pedidos, emitidos e recebidos por distrito do Congresso ou por condado, partido de registo e forma de receção). Os números de cada relatório são os do fim do dia anterior. Presencial é o voto no balcão do auditor do condado e em locais satélite; correio é tudo o resto (correio, caixas de depósito, lares e hospitais, e-mail e fax). Os pedidos incluem quem pede e vota logo no balcão, por isso os pendentes são os boletins emitidos e ainda não recebidos. Libertários e "Other" ficam em `outro`. O leitor confere, em cada relatório, que as formas de receção somam os recebidos de cada partido, que os partidos somam a unidade e que os distritos somam o total estadual; um PDF que falhe não é publicado. A série vem dos relatórios diários: cada dia com relatório recebe a diferença face ao anterior (pode ser negativa quando a fonte corrige), por isso os acumulados batem com a fonte. Em 2022, 2024 e 2026 as regras são as mesmas (20 dias de voto presencial antecipado). Os anos de referência estão em `data/reference/ia/retratos_<ano>.csv`; o mapa por condado é só o do último dia de 2026.
- **Colorado**: o Colorado envia o boletim por correio a todos os eleitores ativos, por isso não há pedidos. Nos dias úteis da eleição geral, o Secretary of State publica um comunicado com os boletins devolvidos até às 23h59 do dia anterior, com um resumo em PDF e uma folha de cálculo com as mesmas tabelas completas. Lemos a folha de cálculo: correio e presencial por partido de registo, género e faixa etária, e por condado e partido. O nome da folha não segue sempre o mesmo padrão, por isso em 2026 seguimos os comunicados listados na página de imprensa. As faixas são as da fonte, de dez anos (18-24, 25-34, 35-44, 45-54, 55-64, 65-74, 75+); os pré-recenseados com menos de 18 anos juntam-se aos 18-24. Só 18-24, 65-74 e 75+ coincidem com as faixas dos outros estados. Democratas, republicanos e não afiliados (UAF) ficam com o seu rótulo; os pequenos partidos vão para `outro`. A idade e os condados vêm em tabelas separadas, por isso não há mapa por faixa; o correio por condado é o total menos o presencial. O leitor confere, em cada folha, que os partidos somam o total de cada linha, que as faixas somam cada género, que os géneros e os condados somam a linha de total e que correio mais presencial por idade dá o total dos condados. Uma folha que falhe fica de fora e a série usa as outras, por isso o ficheiro publicado traz sempre a última folha válida. Os anos de referência (11 folhas em 2022 e 10 em 2024, até ao dia da eleição) estão em `data/reference/co/idade_<ano>.csv` e `condados_<ano>.csv`.
- **Florida**: os relatórios são cumulativos até à véspera e cada condado envia o seu a horas diferentes. Cada execução guarda o retrato do dia num arquivo (`historico-fl-2026.csv`, publicado na Release), de onde sai a série diária. Confere-se a soma dos condados com o total estadual da fonte.

Em todos: o último dia com dados é a véspera do dia em que a fonte gerou o ficheiro (hora da costa leste), porque o próprio dia está incompleto.

## 4. Resumo nacional

`nacional.json` tem uma linha por estado, com os números citados do ficheiro do estado: votos, ano de referência, votos no mesmo dia desse ano, ritmo, quotas de democratas e republicanos registados e, onde há idade, a quota de 65 ou mais anos. A soma é só dos estados acompanhados e **não é um total nacional**. Se a recolha de um estado falhar, o resumo usa o último ficheiro já publicado desse estado, com a sua data.

Os estados prioritários sem ficheiro (Geórgia, Texas, Michigan, Ohio, Nevada e Arizona, todos com fontes que recusam pedidos automáticos) vêm em `estados_sem_dados`, com o motivo e uma nota, para o site não os mostrar como "ainda sem dados". Um estado sai da lista assim que tem ficheiro.

## 5. Simetria e privacidade

As regras são as mesmas da Carolina do Norte: os partidos são valores de uma coluna, e o teste `test_troca_de_rotulos_partidarios_troca_os_resultados` (em `test_agregado_ev.py`) confirma que trocar democratas e republicanos troca os resultados e nada mais. Os ficheiros individuais ficam em `data/brutos/` (não versionado); os cubos e os ficheiros publicados só têm contagens, e as linhas de pedidos com 1 a 9 boletins não são publicadas.

## 6. Reprodução

```sh
# cubos de referência (uma vez)
uv run python -m pipeline.jobs.referencia_voto_antecipado_estado --estado PA
uv run python -m pipeline.jobs.referencia_voto_antecipado_estado --estado ME
uv run python -m pipeline.jobs.voto_antecipado_ia --referencia 2022 2024

# atualização de 2026
uv run python -m pipeline.jobs.voto_antecipado_estado --estado PA --saida data/publicado/voto-antecipado/pa.json
uv run python -m pipeline.jobs.voto_antecipado_ia --saida data/publicado/voto-antecipado/ia.json
uv run python -m pipeline.jobs.voto_antecipado_fl --saida data/publicado/voto-antecipado/fl.json \
  --arquivo data/publicado/voto-antecipado/historico-fl-2026.csv
uv run python -m pipeline.jobs.voto_antecipado_nacional --pasta data/publicado/voto-antecipado
```

Os formatos são os contratos `VotoAntecipadoAgregado` e `VotoAntecipadoNacional` (`schemas/src/contratos/voto_antecipado_agregado.py`).

## Condados de Trump e de Harris

O resumo nacional (`nacional.json`) traz, para cada estado com votos por condado (Carolina do Norte, Pensilvânia, Florida, Iowa e Colorado), de que condados vêm os votos antecipados, em 2026 e no ano de referência ao mesmo dia do ciclo: os votos nos condados que Trump venceu em 2024, os votos nos que Harris venceu e a margem presidencial de 2024 (D−R) dos condados ponderada pelos votos antecipados. A margem de cada condado é a referência do Modelo C (`data/reference/modelo/presidencial_condados_2024.csv`). O sinal descreve a geografia de onde vêm os votos, não em quem votam: um eleitor de um condado de Trump pode votar democrata. Nenhuma regra distingue os partidos (trocar o sinal das margens troca os dois grupos).
