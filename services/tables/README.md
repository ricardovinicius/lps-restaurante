# tables

Serviço FastAPI independente com banco e role `mesa_tables`, modelos SQLAlchemy
e histórico Alembic em `migrations/`. Expõe saúde e OpenAPI; APIs de negócio ainda
pendentes. A prontidão exige o banco/usuário corretos e schema na revisão atual.

Na raiz, com `MESA_DATABASE_URL` configurada:

```bash
PYTHONPATH=packages/mesa_platform/src uv run --frozen python -m mesa_platform.migrations tables
PYTHONPATH=packages/mesa_platform/src uv run --frozen python -m mesa_platform.seed tables
PYTHONPATH=packages/mesa_platform/src uv run --frozen uvicorn services.tables.main:app --port 8000 --no-access-log
```

Compose aplica migrações antes de iniciar o servidor. Seeds são explícitos e não
sobrescrevem dados existentes; Pedidos e Entregas não recebem dados operacionais
fictícios. Consulte [desenvolvimento](../../docs/development.md).
