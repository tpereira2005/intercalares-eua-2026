# Acessibilidade e desempenho

Objetivo: WCAG 2.1 nível AA em todas as páginas, no computador e no telemóvel, nos temas claro e escuro.

## Como verificar

```sh
pnpm --filter @intercalares/web dados:obter
pnpm build
pnpm --filter @intercalares/web auditar   # CAMINHO_CHROMIUM=... para usar um Chromium já instalado
```

O script `apps/web/scripts/auditar-acessibilidade.mjs` serve a pasta exportada e, em cada página, a 1280 e a 320 px, em claro e escuro:

- corre o axe-core com as regras WCAG 2.0 e 2.1 A e AA e as boas práticas;
- confirma que há exatamente um `h1` e nenhum deslocamento horizontal (critério 1.4.10, refluxo a 320 px);
- mede o deslocamento cumulativo do esquema (CLS) e falha acima de 0,1.

## Revisão de 13 de outubro de 2026

Páginas: início, mapa, previsão, noite eleitoral, voto antecipado (NC, PA, ME, FL), metodologia, sistema visual e 404, com os dados publicados nesse dia.

### Corrigido

| Problema                                                                                                                                                     | Critério         | Correção                                                                                                                        |
| ------------------------------------------------------------------------------------------------------------------------------------------------------------ | ---------------- | ------------------------------------------------------------------------------------------------------------------------------- |
| Maine: o quadro "Correio e presencial" era um `<dl>` com `<span>` como filhos diretos                                                                        | 1.3.1            | Passa a `<table>` com cabeçalhos de coluna e de linha                                                                           |
| Metodologia, Noite eleitoral e 404 sem `h1`                                                                                                                  | 1.3.1, 2.4.6     | `Painel` aceita `nivelTitulo`; as secções em preparação e a 404 usam `h1`                                                       |
| Previsão: legenda das categorias com um `<span>` solto dentro do `<dl>`                                                                                      | 1.3.1            | A amostra de cor passa para dentro do `<dt>`                                                                                    |
| Ligação do logótipo com o nome "Escrutínio, início", diferente do texto visível                                                                              | 2.5.3            | O nome passa a ser o próprio texto ("Escrutínio Intercalares EUA 2026")                                                         |
| Linhas interativas dos gráficos (composição, momento do voto, cruzamento por partido) com nome acessível sem a variação em pp, as partes da barra ou o D−R   | 1.1.1, 1.3.1     | O nome inclui todos os valores visíveis, pela ordem em que aparecem                                                             |
| Quadrados do mapa com o nome do estado mas sem a sigla visível                                                                                               | 2.5.3            | "Maine, ME: +60%"                                                                                                               |
| Página inicial com CLS de 0,18 no telemóvel: com a letra de reserva, mais larga, os títulos quebravam em duas linhas e voltavam a uma quando a letra chegava | Desempenho (CLS) | Letras de reserva com `size-adjust` medido (ver `styles/tokens.css`); o número e a etiqueta da contagem já não quebram de linha |

### Verificado sem problemas

- **Contraste** (1.4.3, 1.4.11): nenhuma falha do axe em claro nem em escuro.
- **Teclado** (2.1.1, 2.4.7): todos os elementos focáveis, incluindo as linhas dos gráficos e os quadrados do mapa, têm indicador de foco visível; a ligação "Saltar para o conteúdo" é a primeira paragem.
- **Refluxo** (1.4.10): nenhuma página tem deslocamento horizontal a 320 px.
- **Gráficos**: cada SVG tem `role="img"` (ou `group`, quando é interativo), um `<title>` e um nome acessível.
- **Língua** (3.1.1): `lang="pt-PT"`.

### Exceção conhecida da ferramenta

O axe marca `label-content-name-mismatch` nas linhas interativas dos gráficos SVG porque junta os `<text>` adjacentes sem espaços ("18–245,0%-0,4 pp") e retira o que está entre parênteses. O nome dessas linhas começa pelo rótulo visível e inclui todos os valores mostrados, que é o que o critério 2.5.3 pede. O script ignora esta regra só em elementos `<g>` de SVG.

### Desempenho (telemóvel, 4G lenta, CPU 4× mais lento, site em produção)

| Página               | FCP / LCP | CLS antes | CLS depois (local) |
| -------------------- | --------- | --------- | ------------------ |
| Início               | 1,2 s     | 0,185     | 0,006              |
| Previsão             | 1,1 s     | 0,011     | 0,014              |
| Voto antecipado (NC) | 1,6 s     | 0,033     | 0,031              |
| Mapa                 | 1,4 s     | 0,024     | 0,027              |
| Voto antecipado (ME) | 1,2 s     | 0,008     | 0,004              |

HTML de cada página até cerca de 45 kB comprimido; JavaScript partilhado de cerca de 200 kB comprimido, em cache imutável (`/_next/static/*`). As letras são alojadas no site, em woff2, com `font-display: swap`.

### A acompanhar

- O `aria-live` do mapa e os controlos segmentados foram verificados com o axe e o teclado, mas não com um leitor de ecrã real (NVDA, VoiceOver). Vale a pena um teste manual antes da noite eleitoral.
