# catalog

Serviço FastAPI independente com banco e role `mesa_catalog`, modelos SQLAlchemy
e histórico Alembic em `migrations/`. Consulta o catálogo público e aplica alterações administrativas versionadas.
A prontidão exige o banco e usuário corretos e o schema na revisão atual.

Na raiz, com `MESA_DATABASE_URL` configurada:

```bash
PYTHONPATH=packages/mesa_platform/src uv run --frozen python -m mesa_platform.migrations catalog
PYTHONPATH=packages/mesa_platform/src uv run --frozen python -m mesa_platform.seed catalog
PYTHONPATH=packages/mesa_platform/src uv run --frozen uvicorn services.catalog.main:app --port 8000 --no-access-log
```

Compose aplica migrações antes de iniciar o servidor. Seeds são explícitos e não
sobrescrevem dados existentes. Consulte [desenvolvimento](../../docs/development.md).
