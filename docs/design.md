# Sistema visual: Escrutínio

Direção aprovada pelo Tomás a 13 de outubro de 2026, incluindo o nome "Escrutínio". A fonte da direção (protótipo e tokens) está na pasta `design/` dos ficheiros do projeto.

## Conceito

Painel de instrumentos editorial com o vocabulário do processo eleitoral americano: marcas de sincronização dos boletins de leitura ótica sob o cabeçalho, ovais de boletim nos controlos, dias do ciclo escritos como `E−21`. Sóbrio, denso em informação, sem ornamento genérico.

## Tokens

Definidos em `apps/web/styles/tokens.css` e expostos ao Tailwind em `apps/web/app/globals.css`.

| Token                                 | Papel                                                                                    |
| ------------------------------------- | ---------------------------------------------------------------------------------------- |
| `paper`, `sheet`                      | Fundo da página e dos painéis                                                            |
| `ink`, `ink-2`, `ink-3`               | Texto; nos gráficos, 2022 a traço cheio (`ink`) e 2024 tracejado (`ink-3`)               |
| `rule`, `rule-2`                      | Réguas e divisórias; 2018 nos gráficos                                                   |
| `signal`, `signal-ink`, `signal-wash` | Ciclo atual (2026), dia de hoje, foco, separador ativo                                   |
| `dem`, `rep`, `una`                   | Só partido, com luminosidade equivalente; `rep` tracejado e `una` pontilhado por omissão |
| `up`, `down`                          | Acima e abaixo do esperado; nunca cores partidárias                                      |

`ink-3` foi ajustado em relação ao protótipo (#768093 → #646d7f no claro, #737c8b → #7e8797 no escuro) para cumprir o contraste AA em texto pequeno.

## Tipografia

- **Big Shoulders Display** (700 a 900): títulos e números grandes.
- **Public Sans** (variável): texto e interface; é a letra do sistema de design do governo dos EUA (USWDS).
- **IBM Plex Mono** (400, 500): rótulos, eixos, fontes, códigos `E−n`.

As letras são alojadas no próprio site (pacotes Fontsource, só latim), sem pedidos a terceiros.

## Temas

O tema do sistema por omissão, com escolha manual (Sistema, Claro, Escuro) guardada no browser. Um script no `<head>` aplica a escolha antes da primeira pintura (`apps/web/lib/tema.ts`).

## Componentes base

| Componente                         | Uso                                                                                                                 |
| ---------------------------------- | ------------------------------------------------------------------------------------------------------------------- |
| `Cabecalho`, `Navegacao`, `Rodape` | Estrutura de todas as páginas                                                                                       |
| `IndicadorFase`                    | Fase do painel principal: Antes, Noite, Depois (`lib/fases.ts`)                                                     |
| `ControloSegmentado`               | Escolhas exclusivas com oval de boletim                                                                             |
| `Painel`                           | Bloco de conteúdo com sobrelinha, título, descrição e rodapé de fonte e método                                      |
| `Selo`                             | Estado de um valor: tracejado (ilustrativo, estimativa), sólido (oficial), sinal (ao vivo), pontilhado (geográfico) |
| `QualidadeDados`                   | Ponto cheio (individual), meio (parcial) ou vazio (agregado)                                                        |
| `FaixaKpis`, `Kpi`                 | Indicadores-chave                                                                                                   |
| `CodigoDia`                        | Dia do ciclo, `E−21`                                                                                                |
| `PadroesSvg`                       | Padrões `#padrao-rep` e `#padrao-una` para os gráficos                                                              |

A página `/sistema/` mostra todos os tokens e componentes nos dois temas.

## Regras

- Telemóvel primeiro: grelhas que passam a uma coluna, separadores com deslocamento horizontal, gráficos desenhados à largura real.
- Cada número leva à fonte e ao método.
- Mapa nacional em grelha de quadrados (um estado por quadrado); MapLibre só para condados e distritos.
