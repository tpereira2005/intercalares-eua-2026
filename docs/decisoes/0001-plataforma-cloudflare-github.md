# 0001. Plataforma: Cloudflare Workers e GitHub, sem Supabase

- Estado: aceite
- Data: 13 de outubro de 2026
- Decidido por: Tomás

## Contexto

O site tem de custar zero, nunca ser suspenso por excesso de tráfego (o pico é a noite eleitoral) e atualizar dados ao minuto. O processamento de ficheiros estaduais com milhões de linhas não cabe numa função de edge.

## Decisão

- Site e API num Worker da Cloudflare (plano gratuito), com o site como export estático do Next.js servido pelo mecanismo de ficheiros estáticos.
- D1 para os snapshots correntes.
- Cron da Cloudflare a cada minuto como relógio fiável e vigilante dos workflows.
- GitHub Actions (repositório público) para o pipeline Python e para os modelos.
- GitHub Pages como espelho de emergência.

## Alternativas rejeitadas

- **Vercel Hobby:** cron só uma vez por dia; ao exceder limites, a funcionalidade pode ficar suspensa cerca de 30 dias.
- **Supabase:** a D1 cobre as necessidades na mesma plataforma; o plano gratuito pausa após 7 dias sem atividade.
- **ChatGPT Sites:** beta com limites não publicados, sem API nem integração com GitHub, sem tarefas agendadas.

## Consequências

- Os ficheiros estáticos são ilimitados; só a API tem o teto de 100 000 pedidos diários, mitigado com cache, pausa em separadores ocultos e o espelho.
- R2 fica de fora porque exige método de pagamento.
- O frontend pode mudar de alojamento sem alterar código, por ser estático.
