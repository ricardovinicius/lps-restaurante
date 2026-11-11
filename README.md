# Mesa Fácil

Linha de Produtos de Software para restaurantes, em implementação iterativa.

## Executar a aplicação

O gateway serve a interface React. A Administração usa as APIs de Configuração
e Catálogo para persistir funcionalidades, preços e disponibilidade no PostgreSQL.
O Cardápio público já consulta o catálogo persistido.

```bash
cp .env.example .env
docker compose up --build -d --wait
docker compose exec configuration python -m mesa_platform.seed configuration
docker compose exec catalog python -m mesa_platform.seed catalog
docker compose exec tables python -m mesa_platform.seed tables
```

Abra a [Administração](http://localhost:8080/admin) e entre com o usuário
`admin` e a senha de `MESA_DEMO_ADMIN_PASSWORD` configurada no `.env`.
O usuário `operator` acessa o [Balcão](http://localhost:8080/balcao) com a senha
`MESA_DEMO_OPERATOR_PASSWORD`. A fila e o checkout fazem parte da etapa de retirada.

Consulte o [plano](PLAN.md) e o [guia de desenvolvimento](docs/development.md).

```bash
uv sync --frozen
uv run --frozen pytest -q
uv run --frozen pytest -q tests/integration/test_administration.py
python3 scripts/verify_infrastructure.py
```

## Executar o protótipo

```bash
python3 -m http.server 4173 --directory prototypes/mesa-facil/dist
```

Abra [Administração](http://localhost:4173/?view=admin). O seletor **Acessar** permite navegar entre Cliente, Balcão, Comanda digital e TV, conforme os recursos habilitados.

Não exige instalação de dependências. Os dados ficam no navegador; a sincronização funciona entre abas da mesma origem, não entre dispositivos. O seletor de áreas não é autenticação.

## Documentação

- [Funcionalidades e roteiro de demonstração](prototypes/mesa-facil/README.md)
- [PRD e arquitetura proposta](prototypes/mesa-facil/PRD.md)

## Validar o protótipo

```bash
node --check prototypes/mesa-facil/dist/app.js
node prototypes/mesa-facil/test.mjs
```

Os testes usam DOM simulado e verificam configuração, pedidos, histórico, fila, TV e preservação de preços. Não substituem a revisão visual em navegador.
