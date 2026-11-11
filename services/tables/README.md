# tables

Serviço FastAPI independente com banco e role `mesa_tables`, modelos SQLAlchemy
e histórico Alembic em `migrations/`. Guarda as 12 mesas demonstrativas, sua
disponibilidade versionada, as credenciais da Comanda digital e os recibos de
validação de mesa usados por Pedidos. A prontidão exige o banco/usuário corretos e
schema na revisão atual.

- `GET /v1/tables` lista mesas disponíveis quando `tables` está ativa; com
  `include_unavailable=true`, staff vê todas.
- `PATCH /v1/tables/{id}` altera a disponibilidade com `expected_version`.
- `POST /v1/table-contexts` vincula o navegador a uma mesa (operador + CSRF, com
  `tables` e `tablet` ativas). O cookie `mesa_table` vale 8 horas e só seu hash fica
  no banco. `GET` e `DELETE /v1/table-contexts/current` consultam e revogam o vínculo.
- `/internal/v1/table-contexts/verify` e `/internal/v1/validations/{operation_id}`
  atendem somente Pedidos, com `MESA_ORDERS_ACCESS_KEY`.

Mesas consulta Configuração (`MESA_CONFIGURATION_URL`) para as features e verifica
o operador com `MESA_TABLES_ACCESS_KEY`. Disponibilidade e features bloqueiam novos
pedidos e vínculos, nunca a leitura de uma credencial válida nem pedidos já aceitos.

Limites acadêmicos: o histórico é permanente por mesa, não por visita; o Cliente
escolhe a mesa sem comprovar presença; há um vínculo de tablet por navegador e não há
renovação, apenas novo vínculo pelo operador.

Na raiz, com `MESA_DATABASE_URL` configurada:

```bash
PYTHONPATH=packages/mesa_platform/src uv run --frozen python -m mesa_platform.migrations tables
PYTHONPATH=packages/mesa_platform/src uv run --frozen python -m mesa_platform.seed tables
PYTHONPATH=packages/mesa_platform/src uv run --frozen uvicorn services.tables.main:app --port 8000 --no-access-log
```

Compose aplica migrações antes de iniciar o servidor. Seeds são explícitos e não
sobrescrevem dados existentes, incluindo disponibilidade e versão. Consulte
[desenvolvimento](../../docs/development.md).
