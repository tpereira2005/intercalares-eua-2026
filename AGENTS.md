# Convenções do projeto

Guia para quem contribui, incluindo agentes de IA. Lê-o antes de alterar o repositório.

## Língua

- Todo o texto visível do site está em **português de Portugal** (vocabulário, ortografia e construções de Portugal; nunca português do Brasil). O texto vive em `apps/web/messages/pt-PT.json` e é lido com `t("chave")`; não escrevas texto diretamente nos componentes.
- Números, percentagens e datas usam sempre `apps/web/lib/formatacao.ts` (`Intl` em `pt-PT`): "12,4%", "+2,1 pp", "D +1,2", "E−21", "3 de novembro de 2026".
- Documentação, comentários, mensagens de commit e descrições de PR em PT-PT. Nomes de código em português quando descrevem o domínio (`formatarPercentagem`, `Fonte`); termos técnicos consagrados podem ficar em inglês (`connectors`, `early_vote`), como na estrutura do plano.

## Organização e responsabilidades

| Pasta                                                     | Responsável por omissão | Notas                                                                     |
| --------------------------------------------------------- | ----------------------- | ------------------------------------------------------------------------- |
| Raiz (configuração, CI, `pyproject.toml`, `package.json`) | Fundações               | Alterações coordenadas; mantêm-se pequenas                                |
| `apps/web`                                                | Site                    | Design final só depois de aprovado o protótipo                            |
| `apps/edge`                                               | API e Worker            | Nunca processamento pesado: só orquestração e leitura de dados já prontos |
| `schemas`, `packages/contratos`                           | Contratos               | Ver abaixo                                                                |
| `pipeline`                                                | Dados                   | Ver `pipeline/README.md`                                                  |

Trabalho em paralelo: cada tarefa altera só a sua pasta. Os ficheiros de bloqueio (`pnpm-lock.yaml`, `uv.lock`) são gerados; em caso de conflito, aceita a versão do `main` e volta a correr `pnpm install` ou `uv lock`.

## Sistema visual

O site chama-se **Escrutínio** e segue a direção aprovada pelo Tomás a 13 de outubro de 2026 (`docs/design.md`).

- Cores só através dos tokens (`apps/web/styles/tokens.css`, utilitários como `bg-sheet`, `text-ink-2`); nunca valores hexadecimais nos componentes.
- Ocre (`signal`) só para o ciclo atual, o dia de hoje e o foco; azul e vermelho só para partido; `up`/`down` para acima/abaixo do esperado.
- Republicanos sempre com padrão tracejado e não filiados pontilhado (`fundo-rep`, `fundo-una`, `url(#padrao-rep)`).
- Cada painel usa `Painel` com fonte e método; valores estimados ou ilustrativos levam `Selo`.
- Telemóvel primeiro e sem deslocamento horizontal; claro e escuro verificados em cada ecrã novo.

## Contratos de dados

Os modelos pydantic em `schemas/src/contratos/` são a única fonte de verdade entre o pipeline, a API e o site.

1. Cria ou altera o modelo (herda de `ModeloContrato`) e acrescenta-o a `registo.py`.
2. Corre `pnpm contratos:gerar` para atualizar `schemas/json/` e `packages/contratos/src/gerado/`.
3. Faz commit dos ficheiros gerados. O CI falha se estiverem desatualizados.

Alterações incompatíveis sobem `VERSAO_ESQUEMA` em `schemas/src/contratos/base.py`. Contratos novos que só um módulo usa podem ser propostos pela equipa desse módulo num ficheiro novo em `schemas/src/contratos/`.

## Qualidade

- TypeScript estrito (`noUncheckedIndexedAccess`, `exactOptionalPropertyTypes`); ESLint com `strictTypeChecked`; Prettier.
- Python 3.12, `ruff`, `mypy --strict`, `pytest`. Os nomes dos ficheiros de teste têm de ser únicos em todo o repositório (o pytest usa o modo de importação por omissão).
- Cada conector tem testes com ficheiros de exemplo pequenos e anonimizados, e valida o esquema da fonte: dados que falham a validação nunca são publicados.
- Antes de abrir um PR: `pnpm verificar` e as verificações Python do README.

## Segurança e privacidade

- Nenhum segredo no repositório. Tokens só como segredos do GitHub ou da Cloudflare; localmente em `.dev.vars` ou `.env` (ignorados pelo git).
- Ficheiros individuais de eleitores ficam em `data/brutos/` (ignorado) ou só em memória no CI; publica-se apenas agregados. Nunca guardes nomes, moradas ou identificadores de eleitores em ficheiros versionados, testes incluídos.
- Ações do GitHub fixadas por SHA; permissões mínimas em cada workflow.
- Pedidos às fontes com cabeçalhos condicionais (ETag, Last-Modified), um User-Agent identificado e limites de frequência.

## Custo zero

Nunca ativar um serviço pago nem associar um cartão. Não usar R2 (exige método de pagamento). Qualquer funcionalidade que dependa de um serviço externo novo é discutida antes com o Tomás.

## Git

- Ramos curtos a partir de `main`; PR com o CI verde antes de integrar.
- Mensagens de commit no imperativo, em PT-PT, com um título curto (ex.: "Adiciona conector de voto antecipado da Carolina do Norte").
