# Jornadas ponta a ponta

As jornadas de retirada estão em `web/e2e/pickup.spec.ts`, com Playwright sobre
as APIs e o PostgreSQL reais. Cobrem Cliente e Balcão em contextos independentes,
persistência do carrinho, estados, resposta perdida, reenvio sem duplicidade,
revisão de preços e respostas atrasadas após navegação. A TV será adicionada na
próxima etapa.

`web/e2e/tables.spec.ts` cobre o pedido de mesa pelo Cliente concluído no Balcão,
o vínculo de tablet pelo operador com duas rodadas e o “Já pedi” com o total de todas
as origens, o isolamento de outra mesa e o bloqueio de novas rodadas ao desabilitar
Comanda e Mesas, preservando histórico e conclusão. Também verifica que a Comanda só
abre após encerrar a sessão do operador, inclusive quando a resposta do logout se perde,
e que a referência de uma rodada pendente continua visível depois de perder o cookie da
mesa, com o novo vínculo bloqueado enquanto o tablet é verificado.

`web/e2e/delivery.spec.ts` cobre a escolha da modalidade, endereço e taxa no
carrinho, o endereço na fila do Balcão, "Saiu para entrega" e conclusão vistos pelo
Cliente, a criação de entregas pelo Balcão e a preservação de uma entrega aceita
depois de desabilitar a modalidade.

`web/e2e/recovery.spec.ts` cobre a perda do cookie, o fluxo de tentativas antigas
sem credencial, o histórico sob demanda e a retomada administrativa pela interface.

Use uma instalação descartável, com seeds de Configuração e Catálogo. Os testes
alteram configuração e preços e criam pedidos; não apontar para dados de uso real.

```bash
npm --prefix web ci
npm --prefix web exec -- playwright install chromium
MESA_BASE_URL=http://127.0.0.1:8080 npm --prefix web run test:e2e
```

As contas padrão usam as senhas de `.env.example`. Se forem diferentes, fornecer
`MESA_DEMO_ADMIN_PASSWORD` e `MESA_DEMO_OPERATOR_PASSWORD` ao comando de teste.
`MESA_BROWSER_PATH` permite usar um Chromium já instalado. O teste DOM do protótipo
continua independente dessas jornadas.

A jornada de retomada interrompe temporariamente o Catálogo e exige um projeto
Compose descartável informado por `MESA_TEST_COMPOSE_PROJECT`; sem essa variável,
somente essa jornada é ignorada. Para executar todas, na raiz do repositório:

```bash
mesa_e2e() { MESA_HTTP_PORT=8081 docker compose -p mesa-recovery-test-local --env-file .env.example "$@"; }
mesa_e2e up --build -d --wait
mesa_e2e exec -T configuration python -m mesa_platform.seed configuration
mesa_e2e exec -T catalog python -m mesa_platform.seed catalog
mesa_e2e exec -T tables python -m mesa_platform.seed tables
MESA_BASE_URL=http://127.0.0.1:8081 MESA_TEST_COMPOSE_PROJECT=mesa-recovery-test-local npm --prefix web run test:e2e
mesa_e2e down --volumes
```

A remoção de volumes nesse exemplo afeta somente o projeto descartável nomeado.
