# Mesa Fácil

Linha de Produtos de Software para restaurantes, em implementação iterativa.

## Executar a aplicação

O gateway serve a interface React. A Administração usa as APIs de Configuração
e Catálogo para persistir funcionalidades, preços e disponibilidade no PostgreSQL.
O Cliente cria e acompanha retiradas, entregas e pedidos de mesa; o Balcão registra
pedidos e controla os estados Recebido, Em preparo, Pronto, Saiu para entrega e
Concluído. Entregas guarda endereço, taxa fixa e despacho. Mesas valida as mesas e
vincula tablets à Comanda digital, que envia rodadas e mostra o histórico “Já pedi”.

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
`MESA_DEMO_OPERATOR_PASSWORD`. Abra o [Cliente](http://localhost:8080/cliente)
em outra sessão para criar uma retirada ou entrega e acompanhar o andamento.

Consulte o [plano](PLAN.md) e o [guia de desenvolvimento](docs/development.md).

```bash
uv sync --frozen
uv run --frozen pytest -q
uv run --frozen pytest -q tests/integration
python3 scripts/verify_infrastructure.py
```

As jornadas de retirada, entrega, mesa e Comanda no navegador estão em `web/e2e/`. Consulte os comandos e
os cuidados com dados de teste em [tests/e2e/README.md](tests/e2e/README.md).

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
