# deliveries

Serviço FastAPI independente com banco e role `mesa_deliveries`, modelos SQLAlchemy
e histórico Alembic em `migrations/`. Guarda o endereço, a taxa fixa de 500 centavos
e os dados de despacho de cada pedido de entrega. A prontidão exige o banco/usuário
corretos e schema na revisão atual.

Expõe somente rotas internas em `/internal/v1/deliveries`, chamadas por Pedidos com
`MESA_ORDERS_ACCESS_KEY`. O gateway não publica essas rotas:

- `PUT /{order_id}` registra o endereço de forma idempotente por pedido e operação.
- `POST /lookup` devolve endereço, taxa e despacho de até 100 pedidos.
- `PUT /{order_id}/dispatch` registra a saída com o `transition_id` de Pedidos.

O estado público do pedido pertence a Pedidos. Entregas não expõe estado próprio,
e endereços não aparecem em erros nem em logs.

Na raiz, com `MESA_DATABASE_URL` configurada:

```bash
PYTHONPATH=packages/mesa_platform/src uv run --frozen python -m mesa_platform.migrations deliveries
PYTHONPATH=packages/mesa_platform/src uv run --frozen uvicorn services.deliveries.main:app --port 8000 --no-access-log
```

Compose aplica migrações antes de iniciar o servidor. Entregas não recebe dados
operacionais fictícios. Consulte [desenvolvimento](../../docs/development.md).
