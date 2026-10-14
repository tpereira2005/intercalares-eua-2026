# Metodologia: voto antecipado e análise por idade

Este documento descreve como o pipeline transforma os ficheiros oficiais em indicadores do voto antecipado, com a idade como dimensão principal (plano, secção 6). Começa pela Carolina do Norte, o único estado prioritário com ficheiros individuais gratuitos e diários com idade, partido, raça, género, condado, distrito, modalidade e histórico de voto.

## 1. Fontes (Carolina do Norte)

| Ficheiro                                | Conteúdo                                                 | Atualização                                            | Uso                                                                |
| --------------------------------------- | -------------------------------------------------------- | ------------------------------------------------------ | ------------------------------------------------------------------ |
| `ENRS/<data>/absentee_<data>.zip`       | Um registo por boletim (correio e presencial antecipado) | Diária em período eleitoral; final nos anos anteriores | Numeradores: quem já votou, quando e como                          |
| `data/ncvoter_Statewide.zip`            | Eleitores atuais, incluindo removidos                    | Semanal                                                | Denominadores de 2026, ano de nascimento, distrito no mapa de 2026 |
| `data/ncvhis_Statewide.zip`             | Histórico de voto individual (cerca de dez anos)         | Semanal                                                | Grupos históricos (habitual, antecipação, voto novo)               |
| `data/Snapshots/VR_Snapshot_<data>.zip` | Retrato do recenseamento no dia de cada eleição          | Uma vez por eleição                                    | Denominadores de 2016, 2018, 2020, 2022 e 2024                     |

Todos são registos públicos (N.C. G.S. 132-1 e 163-82.10), publicados em `https://dl.ncsbe.gov`. Os ficheiros têm nomes e moradas: o pipeline lê só as colunas de que precisa e nunca grava dados pessoais fora da cache local, que o git ignora. O repositório e o site só recebem **cubos de contagens agregadas**.

O UF Election Lab (CC BY-NC-ND) não é usado como fonte: serve apenas para conferir ordens de grandeza.

### Leitura robusta

Os ficheiros da NCSBE têm aspas por fechar e bytes fora de UTF-8. Os leitores CSV paralelos perdem linhas sem avisar: no ficheiro de 2022, o DuckDB devolveu 1,87 milhões de registos quando o ficheiro tem 2,28 milhões. Por isso a leitura é feita linha a linha com o módulo `csv` da biblioteca padrão, que confere o número de campos de cada linha e falha se mais de 0,1% das linhas estiverem partidas.

### Validação

Cada ano de referência é conferido com uma fonte independente: o total de votos antecipados reconstruído a partir dos boletins tem de coincidir, a menos de 1%, com o histórico individual oficial. Em 2018: 2 074 734 votos nos boletins contra 2 069 792 no histórico (0,24%). Em 2022: 2 201 705 contra 2 199 518 (0,10%). Em 2024: 4 530 345 contra 4 521 970 (0,19%). Em 2020: 4 636 013 contra 4 631 054 (0,11%).

## 2. Definições

- **Voto antecipado**: boletim por correspondência devolvido ou voto presencial antecipado ("one-stop"). Um eleitor conta uma vez, pelo primeiro boletim válido.
- **Já votou até ao dia d**: tem um boletim devolvido com data de devolução a `d` ou mais dias da eleição. Contam os estados aceite, pendente (em verificação ou correção) e rejeitado; não contam os anulados (substituídos, cancelados, não usados). Esta é a única definição igual em 2026 (estados ainda provisórios) e nos anos anteriores (estados finais).
- **Dia do ciclo**: sempre em **dias antes da eleição**. A janela de voto presencial começa 19 dias antes em 2022, 2024 e 2026 (20 em 2018), por isso os ciclos alinham-se bem.
- **Recenseados**: eleitores ativos, inativos e temporários no dia da eleição (retratos) ou no ficheiro mais recente (2026). Os votantes que ainda não constam do ficheiro (sobretudo recenseamento no próprio dia) entram com os atributos do boletim.
- **Idade**: idade no fim do ano da eleição, a definição dos ficheiros de boletins. Confirmámos eleitor a eleitor que coincide com o ano da eleição menos o ano de nascimento. Os retratos trazem a idade no dia do retrato (cerca de 14% dos eleitores ficariam um ano mais novos), por isso são corrigidos com o ano de nascimento do ficheiro atual, que inclui os eleitores removidos.
- **Faixas etárias**: 18-24, 25-29, 30-39, 40-49, 50-64, 65-74 e 75+ (faixas largas nos mapas: 18-29, 30-49, 50-64 e 65+).
- **Distritos**: os eleitores de anos anteriores são postos no distrito do mapa de 2026 em que estão hoje, para que as comparações por distrito usem as mesmas fronteiras.
- **Partido**: partido de registo (`dem`, `rep`, `nao_afiliado`, `outro`). É uma característica do eleitor, não o seu voto.

## 3. As três perguntas

Para cada faixa etária e cada dia do ciclo, o site separa três coisas que costumam aparecer misturadas.

### 3.1 Composição

Quota da faixa no voto antecipado até ao dia `d`. É o número que circula nas redes sociais e, sozinho, mistura todos os efeitos seguintes.

### 3.2 Participação

Taxa = votos da faixa até `d` / recenseados da faixa. Comparada com o mesmo dia de 2022, 2018, 2024, 2016 e 2020, corrige automaticamente o envelhecimento da população e as mudanças no recenseamento.

A variação da quota entre dois anos divide-se exatamente em dois efeitos. Com `r` a quota da faixa no recenseamento e `t` a taxa de participação, a quota no voto é `s = r t / Σ r t`. O **efeito do recenseamento** é quanto a quota mudaria só por mudar `r`; o **efeito da participação**, só por mudar `t`. Usamos a média das duas ordens possíveis (valor de Shapley), o que torna a soma exata e independente da ordem.

**Esperado e desvio**: votos esperados = recenseados de hoje × taxa do ano de referência no mesmo dia; desvio = observados / esperados − 1. Mostramos o desvio face a cada ano de referência. A distância entre as referências intercalares (2018 e 2022) é a medida honesta da incerteza: não há um "normal" único. Cada linha traz também `desvio_min` e `desvio_max`: o menor e o maior desvio quando a taxa de referência se lê até 3 dias antes ou depois do mesmo dia do ciclo, o que mede a sensibilidade ao alinhamento do calendário (feriados, abertura dos locais de voto, atrasos no registo dos boletins). O erro de amostragem é desprezável com estas contagens. O intervalo das barras "acima / abaixo do esperado" é o envelope destes valores nas referências intercalares.

### 3.3 Momento do voto

Cada eleitor é classificado pelo que fez na eleição anterior do mesmo tipo (2022 para 2026, 2018 para 2022, 2020 para 2024):

| Grupo                                 | Significado quando vota antecipadamente agora               |
| ------------------------------------- | ----------------------------------------------------------- |
| Votou antecipadamente na referência   | Comportamento habitual                                      |
| Votou no dia da eleição na referência | **Antecipação**: o voto mudou de dia, não é voto novo       |
| Estava recenseado e não votou         | **Voto novo** ou de baixa propensão: o sinal de mobilização |
| Recenseou-se depois da referência     | Eleitor novo no registo (jovens, mudanças de estado)        |

O contributo de cada grupo é os seus votos a dividir pelos recenseados da faixa. Os contributos somam a taxa de participação, por isso a variação da participação face a 2022 divide-se exatamente entre voto habitual, antecipação e voto novo.

2016 e 2018 não têm grupos: o histórico público só começa em 2016, e as referências seriam 2012 e 2014.

### 3.4 Geografia e cruzamentos

Tudo o que se compara entre anos usa o **mesmo dia do ciclo** `d`, nunca o total final de um ano anterior: a série, a comparação, o histórico, a reserva, a geografia e os cruzamentos. O teste `test_cruzamentos_e_geografia_dos_anos_de_referencia_sao_do_mesmo_dia` confirma-o.

- **Geografia**: votos até `d` e recenseados por condado e por distrito do Congresso, para cada faixa larga (18-29, 30-49, 50-64, 65+, desconhecida) e para o total. Os distritos são os do mapa de 2026 em todos os anos: cada eleitor de um ano anterior fica no distrito em que está hoje no ficheiro de eleitores; quem já não está no ficheiro fica no distrito da época. Os condados não mudam.
- **Histórico por geografia** (`historico_geografia`): o contributo de cada grupo histórico (secção 3.3) por condado e distrito e por faixa larga. Os contributos de um lugar somam a sua taxa de participação, por isso a variação face a 2022 divide-se, em cada condado e distrito, entre voto habitual, antecipação e voto novo. Só existe nos anos com histórico individual de referência (2022, 2024 e 2026).
- **Cruzamentos**: votos e recenseados por faixa etária × partido, raça, etnia, género e modalidade, para o estado. Na modalidade, o denominador é o total da faixa, para que as taxas de correio e presencial somem a taxa total.

As células com 1 a 9 recenseados não se publicam (secção 6). Nos condados pequenos isto tira sobretudo a faixa desconhecida; os totais de cada lugar continuam a contar toda a gente.

## 4. Reserva restante

Eleitores que votaram na eleição de referência (por qualquer método) e ainda não votaram até ao dia `d`, por faixa e partido, comparados com o mesmo dia do ciclo anterior. Responde a "quanta base de cada grupo já foi mobilizada e quanta falta", que é o que a liderança no voto antecipado não diz.

## 5. Simetria e proteção contra viés

- Nenhuma regra trata um partido de forma diferente: os partidos são valores de uma coluna. O teste `test_troca_de_rotulos_partidarios_troca_os_resultados` troca `dem` e `rep` nos dados e confirma que todos os indicadores trocam e nada mais (plano, secção 5.5).
- Os indicadores mostram com o mesmo destaque sinais favoráveis a qualquer partido.
- O que é composição e o que é participação nunca se apresenta como preferência de voto: o efeito na margem (plano, secção 6.4) é estimado na Fase 2, com calibração e backtests simétricos, e não é assumido aqui.

## 6. Privacidade

- O painel individual (com o `ncid`) só existe em memória e em `data/cache/`, que não é versionado. Os cubos e o ficheiro publicado têm apenas contagens; os testes confirmam que não há colunas identificadoras (`ncid`, nomes, moradas, data ou ano de nascimento, idade exata) nem nos cubos versionados nem no JSON.
- **Células pequenas**: não se publica nenhuma linha cuja população (recenseados, ou eleitores habituais na reserva) esteja entre 1 e 9. Na prática são quase só células da faixa etária desconhecida. Os totais são calculados antes, por isso continuam a contar toda a gente.
- As contagens de votos pequenas (por exemplo, três votos de 18-29 anos num condado no início do ciclo) mantêm-se: são o próprio sinal do rastreador, e a NCSBE publica os mesmos registos de forma nominal e diária, pelo que agregá-los não acrescenta informação sobre ninguém.

## 7. Limitações conhecidas

- **Mudanças de regras**: em 2024 passou a ser obrigatória a identificação com fotografia e o correio passou a ter de chegar até ao fecho das urnas; em 2018 e 2022 havia três dias de tolerância. As séries até ao dia da eleição não são afetadas pela tolerância, mas o total final de correio sim.
- **2024 é presidencial**, teve o furacão Helene no oeste do estado e o envio dos boletins por correio atrasou cerca de duas semanas por ordem judicial: é uma referência de ritmo do voto presencial, não de nível nem do correio.
- **2016 é presidencial** e não tem grupos históricos: serve para comparar o ritmo e a composição etária com a última presidencial antes da pandemia, não o nível.
- **2020** (pandemia) entra só como curva de contexto: o voto por correspondência foi excecional, por isso aparece sempre com aviso e nunca entra no intervalo do "esperado".
- **Antes do voto presencial** (até 15 de outubro de 2026) só há correio, onde os mais velhos pesam muito mais: a composição etária nessa fase não é comparável com o total final.
- **Denominador de 2026**: o ficheiro de eleitores é semanal e não inclui ainda quem se recensear durante o voto antecipado; esses eleitores entram pelo boletim.
- **Histórico**: o ficheiro individual guarda cerca de dez anos (desde 2016) e inclui eleitores removidos; os totais de votos antecipados conferem com os ficheiros de boletins a menos de 0,3% (secção 1).

## 8. Reprodução

```sh
# cubos de referência (uma vez; descarrega cerca de 5 GB)
uv run python -m pipeline.jobs.referencia_voto_antecipado_nc --anos 2016 2018 2020 2022 2024

# atualização de 2026 (a cada duas horas no GitHub Actions)
uv run python -m pipeline.jobs.voto_antecipado_nc --saida data/publicado/voto-antecipado/nc.json
```

O formato do ficheiro publicado é o contrato `VotoAntecipadoEstado` (`schemas/src/contratos/voto_antecipado.py`).

No GitHub Actions, o ficheiro de 2026 é publicado como asset `nc.json` da Release fixa `dados-voto-antecipado`, substituído a cada execução; o build do site descarrega-o daí.
