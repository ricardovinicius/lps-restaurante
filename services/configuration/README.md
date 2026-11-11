# configuration

Serviço FastAPI independente com banco e role `mesa_configuration`, modelos SQLAlchemy
e histórico Alembic em `migrations/`. Gerencia sessões internas, configuração versionada, modelos e exportação.
A prontidão exige o banco e usuário corretos e o schema na revisão atual.

Na raiz, com `MESA_DATABASE_URL` configurada:

```bash
PYTHONPATH=packages/mesa_platform/src uv run --frozen python -m mesa_platform.migrations configuration
PYTHONPATH=packages/mesa_platform/src uv run --frozen python -m mesa_platform.seed configuration
PYTHONPATH=packages/mesa_platform/src uv run --frozen uvicorn services.configuration.main:app --port 8000 --no-access-log
```

Compose aplica migrações antes de iniciar o servidor. Seeds são explícitos e não
sobrescrevem dados existentes. Consulte [desenvolvimento](../../docs/development.md).
