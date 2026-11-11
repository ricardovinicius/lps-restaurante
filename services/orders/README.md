# orders

Serviço FastAPI independente com banco e role `mesa_orders`, modelos SQLAlchemy
e histórico Alembic em `migrations/`. Cria retiradas, entregas e pedidos de mesa
(Cliente, Balcão e Comanda) com snapshots e idempotência, mantém a fila, o acompanhamento e as transições com controle de
concorrência. É a fonte canônica do estado público, inclusive de "Saiu para entrega".
A prontidão exige o banco/usuário corretos e schema na revisão atual.

As chamadas internas de admissão, cotação, endereço e despacho usam
`MESA_ORDERS_ACCESS_KEY`, `MESA_CONFIGURATION_URL`, `MESA_CATALOG_URL`,
`MESA_DELIVERIES_URL` e `MESA_TABLES_URL`. A identidade do tablet é verificada em Mesas
a cada requisição; Pedidos guarda só o ID do contexto e o número da mesa como
snapshot, e `GET /v1/table-orders` serve o “Já pedi” da mesa da credencial. O endereço fica em Entregas: Pedidos o guarda na operação só
até o recibo remoto e o lê em lote nas consultas autorizadas. O contexto do cliente usa cookie
HttpOnly; seu identificador público não autoriza a consulta de pedidos.

O worker retoma criações e despachos pendentes a cada três segundos, com lease de 30 segundos
e backoff limitado a 60 segundos. Após dez tentativas, a operação exige intervenção.
Um administrador autenticado pode retomá-la por
`POST /api/orders/v1/operations/{id}/resume`, com `X-CSRF-Token`; a ação é auditada.
Despachos esgotados usam `POST /api/orders/v1/dispatches/{id}/resume`, auditado em
`dispatch_resumes`. Na interface, use Administração → Envios. O Balcão também consulta
as tentativas e as saídas para entrega, mas a retomada exige administrador.

A perda do cookie pode ser recuperada com uma credencial independente preservada
no navegador e armazenada apenas como hash no banco. Tentativas antigas sem essa
credencial possuem um fluxo explícito para verificar o resultado com o atendimento
e iniciar outra identificação, preservando a operação anterior.

Listas carregam os itens em lote. O acompanhamento atualiza uma página de pedidos
ativos; o histórico concluído é paginado e consultado sob demanda.

`GET /v1/tv` é público com a feature TV ativa e retorna só números, modalidade e
mesa de pedidos em preparo/prontos. Totais e páginas vêm da mesma instrução SQL;
Mesas e Entregas não são consultados. `GET /v1/summary` exige administrador e
agrega andamento e valor histórico dos concluídos, incluindo taxas.

Na raiz, com `MESA_DATABASE_URL` configurada:

```bash
PYTHONPATH=packages/mesa_platform/src uv run --frozen python -m mesa_platform.migrations orders
PYTHONPATH=packages/mesa_platform/src uv run --frozen python -m mesa_platform.seed orders
PYTHONPATH=packages/mesa_platform/src uv run --frozen uvicorn services.orders.main:app --port 8000 --no-access-log
```

Compose aplica migrações antes de iniciar o servidor. Seeds são explícitos e não
sobrescrevem dados existentes; Pedidos e Entregas não recebem dados operacionais
fictícios. Consulte [desenvolvimento](../../docs/development.md).
