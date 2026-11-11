# orders

Serviço FastAPI independente com banco e role `mesa_orders`, modelos SQLAlchemy
e histórico Alembic em `migrations/`. Cria retiradas com snapshots e idempotência,
mantém a fila, o acompanhamento e as transições com controle de concorrência.
A prontidão exige o banco/usuário corretos e schema na revisão atual.

As chamadas internas de admissão e cotação usam `MESA_ORDERS_ACCESS_KEY`,
`MESA_CONFIGURATION_URL` e `MESA_CATALOG_URL`. O contexto do cliente usa cookie
HttpOnly; seu identificador público não autoriza a consulta de pedidos.

O worker retoma operações pendentes a cada três segundos, com lease de 30 segundos
e backoff limitado a 60 segundos. Após dez tentativas, a operação exige intervenção.
Um administrador autenticado pode retomá-la por
`POST /api/orders/v1/operations/{id}/resume`, com `X-CSRF-Token`; a ação é auditada.
Na interface, use Administração → Envios. O Balcão também consulta as tentativas
pela referência informada pelo cliente, mas a retomada exige administrador.

A perda do cookie pode ser recuperada com uma credencial independente preservada
no navegador e armazenada apenas como hash no banco. Tentativas antigas sem essa
credencial possuem um fluxo explícito para verificar o resultado com o atendimento
e iniciar outra identificação, preservando a operação anterior.

Listas carregam os itens em lote. O acompanhamento atualiza uma página de pedidos
ativos; o histórico concluído é paginado e consultado sob demanda.

Na raiz, com `MESA_DATABASE_URL` configurada:

```bash
PYTHONPATH=packages/mesa_platform/src uv run --frozen python -m mesa_platform.migrations orders
PYTHONPATH=packages/mesa_platform/src uv run --frozen python -m mesa_platform.seed orders
PYTHONPATH=packages/mesa_platform/src uv run --frozen uvicorn services.orders.main:app --port 8000 --no-access-log
```

Compose aplica migrações antes de iniciar o servidor. Seeds são explícitos e não
sobrescrevem dados existentes; Pedidos e Entregas não recebem dados operacionais
fictícios. Consulte [desenvolvimento](../../docs/development.md).
