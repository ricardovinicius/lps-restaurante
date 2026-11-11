# Desenvolvimento e validação

## Estado atual

O ambiente inclui os cinco serviços FastAPI com bancos e migrações independentes.
As APIs de Configuração, Acesso e Catálogo atendem o frontend React pelo gateway.
Retirada, fila do Balcão e acompanhamento usam Pedidos com persistência,
idempotência e recuperação. Entrega, mesa, Comanda e TV permanecem nas próximas etapas.

`/health/live` informa que o processo responde. `/health/ready` exige conexão ao
banco/usuário do serviço e revisão Alembic atual; não significa que os fluxos de
negócio estejam prontos. Schema ausente, antigo ou banco incorreto resulta em 503.

## Executar com Docker

Requer Docker Engine com Compose; em WSL, a integração do Docker Desktop deve estar
habilitada. Na raiz do repositório:

```bash
cp .env.example .env
# Ajuste as credenciais locais em .env antes de iniciar.
docker compose config --quiet
docker compose up --build -d --wait
```

Se o arquivo `.env` já existia, adicione as variáveis de acesso listadas em
`.env.example`, incluindo `MESA_ORDERS_ACCESS_KEY`. Preserve as credenciais
PostgreSQL usadas pelo volume existente.

Na inicialização, cada serviço aplica suas próprias migrações antes de iniciar o
Uvicorn. Um advisory lock transacional serializa tentativas simultâneas de migração.
Não é usado `create_all` para substituir o histórico Alembic. Cada revisão é um
arquivo congelado e não importa modelos de execução.

Provisionar dados demonstrativos explicitamente:

```bash
docker compose exec configuration python -m mesa_platform.seed configuration
docker compose exec catalog python -m mesa_platform.seed catalog
docker compose exec tables python -m mesa_platform.seed tables
```

Os seeds criam a configuração Lanchonete, oito produtos, quatro categorias e 12
mesas com IDs estáveis. As contas `admin` e `operator` são criadas se
`MESA_DEMO_ADMIN_PASSWORD` e `MESA_DEMO_OPERATOR_PASSWORD` forem fornecidas.
Repetir os seeds preserva contas, configuração, preços e disponibilidade.

Abra [Administração](http://localhost:8080/admin) e entre com a conta `admin`.
Carregue um modelo, ajuste o rascunho e salve. O JSON de exportação reflete a
configuração persistida. Use **Editar cardápio** para alterar um produto e confira
o resultado no [Cardápio](http://localhost:8080/cliente). Com retirada habilitada,
adicione produtos e confirme um pedido. A conta `operator` acessa o
[Balcão](http://localhost:8080/balcao) para iniciar preparo, marcar pronto e concluir.
O Cliente acompanha os estados sem recarga; o Balcão também permite criar retiradas.

Endpoints de saúde disponíveis pelo gateway.

```bash
curl --fail http://localhost:8080/api/configuration/health/ready
curl --fail http://localhost:8080/api/catalog/health/ready
curl --fail http://localhost:8080/api/orders/health/ready
curl --fail http://localhost:8080/api/deliveries/health/ready
curl --fail http://localhost:8080/api/tables/health/ready
```

O gateway publica as rotas `/api/{service}/v1/` implementadas e mantém as operações
internas e o OpenAPI acessíveis apenas nos serviços. O acesso direto ao processo local permite
consultar `/openapi.json` durante desenvolvimento.

## Credenciais e persistência

O SQL de inicialização cria bancos/roles somente no primeiro uso de um volume vazio.
Cada role pode conectar apenas ao seu banco; serviços não usam credenciais de
superusuário. Alterar `.env` posteriormente não altera as senhas já persistidas.

As senhas de `.env.example` são para demonstração local. Use senhas URL-safe
(letras/dígitos), pois o Compose monta as URLs com elas. `.env` não é versionado.
Gateway liga apenas em 127.0.0.1; banco e portas internas não são expostos no host.
Demonstração entre dispositivos exigirá configurar explicitamente o endereço
externo do gateway e revisar a configuração de autenticação.

O volume `postgres_data` preserva dados após `docker compose down` e recriação dos
containers. `down --volumes` remove os dados e não deve ser usado para atualizar
schemas ou corrigir migrações. Evoluções exigem novas revisões Alembic por serviço.

Executar migração ou seed manualmente usa somente a credencial do próprio serviço:

```bash
docker compose exec catalog python -m mesa_platform.migrations catalog
```

O comando rejeita banco/usuário de outro serviço antes de executar DDL. Se uma
migração falhar, o serviço não inicia; revisar a falha e aplicar uma correção antes
de subir novamente. Seeds não são executados automaticamente em cada boot.

## Python local

Requer Python 3.13 e uv. O lockfile fixa versões diretas e transitivas; cada processo
tem sua configuração e banco. Docker instala `requirements.txt`, exportado desse
lockfile.

```bash
uv sync --frozen
uv run --frozen python -m scripts.validate_products
uv run --frozen pytest -q
```

Exportar contratos implementados, sem conectar ao banco:

```bash
PYTHONPATH=packages/mesa_platform/src uv run --frozen python -m scripts.export_contracts
```

Para um banco PostgreSQL local configurado com as roles esperadas, definir
`MESA_DATABASE_URL` e executar:

```bash
PYTHONPATH=packages/mesa_platform/src uv run --frozen python -m mesa_platform.migrations configuration
PYTHONPATH=packages/mesa_platform/src uv run --frozen python -m mesa_platform.seed configuration
PYTHONPATH=packages/mesa_platform/src uv run --frozen uvicorn services.configuration.main:app --port 8000 --no-access-log
```

| Variável | Uso |
| --- | --- |
| MESA_DATABASE_URL | Obrigatória; URL `postgresql+psycopg://...` do banco próprio |
| MESA_DATABASE_CONNECT_TIMEOUT | Timeout de conexão em segundos, padrão 2 |
| MESA_LOG_LEVEL | Nível de log Python, padrão INFO |
| MESA_CATALOG_ACCESS_KEY | Credencial compartilhada entre Catálogo e Configuração para verificar sessões |
| MESA_ORDERS_ACCESS_KEY | Credencial de Pedidos para sessões, admissões e cotações internas |
| MESA_CONFIGURATION_URL | URL interna de Configuração, padrão `http://configuration:8000` |
| MESA_CATALOG_URL | URL interna do Catálogo, padrão `http://catalog:8000` |
| MESA_DEMO_ADMIN_PASSWORD | Senha inicial da conta demonstrativa `admin` |
| MESA_DEMO_OPERATOR_PASSWORD | Senha inicial da conta demonstrativa `operator` |
| MESA_SECURE_COOKIES | Use `1` ao servir a aplicação sobre HTTPS, padrão `0` para execução local |

As sessões expiram em oito horas. O identificador aleatório da sessão fica em
cookie HttpOnly e seu hash é armazenado no serviço de Configuração. As mutações
autenticadas exigem o token CSRF retornado pela consulta da sessão.

As conexões têm timeout de statement e lock de 5 segundos. Logs registram template
da rota, método, status, duração, serviço e UUID de correlação, sem payloads ou
query strings. Usar `--no-access-log` evita URLs no log padrão do Uvicorn.

## Frontend local

Com o gateway em execução, use Node.js 22.12 ou superior.

```bash
npm --prefix web ci
npm --prefix web run dev
npm --prefix web run build
```

O Vite encaminha `/api` ao gateway em `http://127.0.0.1:8080`. Se a porta do
gateway mudar, ajuste `MESA_GATEWAY_URL` ao iniciar o Vite.

## Verificação real da Administração

```bash
uv run --frozen pytest -q tests/integration/test_administration.py
```

A suíte cria um projeto Compose descartável. Os testes passam pelo gateway e
cobrem sessão, expiração, autorização de administrador e operador, CSRF,
dependências entre funcionalidades, catálogo público, concorrência de gravação
e persistência de alterações e sessões após recriar serviços.

## Verificação real da retirada

```bash
uv run --frozen pytest -q tests/integration
```

Administração e retirada compartilham um projeto Compose descartável. A suíte
verifica as novas migrações contra os modelos reais, isolamento dos bancos,
snapshots, valores altos, permissões, concorrência, replay de criação/transição,
paginação e persistência após recriação. Interromper o Catálogo e remover apenas
o recibo local de admissão simula falha entre o commit remoto e o progresso local;
o pedido se recupera mesmo após reiniciar Pedidos e desabilitar novas retiradas.
Também cobre o limite de tentativas e a retomada administrativa auditada.

As jornadas Playwright estão em `web/e2e/`; comandos em
[tests/e2e/README.md](../tests/e2e/README.md). O carrinho e a identidade do envio
ficam no navegador. A confirmação e os dados dos pedidos pertencem ao servidor.
O cookie perdido é recuperado pela credencial independente criada antes do envio.
Se essa credencial também não existir, a interface mostra a referência para
verificação no atendimento e permite iniciar outro atendimento após confirmação
explícita do usuário. A tentativa anterior permanece registrada; isso não cancela
um pedido nem confirma o reenvio automaticamente.

Na Administração, abra **Envios** para listar operações que precisam de atenção,
consultar o resultado e retomar após resolver a falha. No Balcão, **Verificação de
envios** permite a consulta pela referência do cliente; apenas o administrador
pode retomar. Erros de chave interna são recuperáveis. A migração `orders_0003`
também torna visíveis as rejeições antigas causadas por esse erro.

O acompanhamento consulta uma página de pedidos ativos a cada três segundos.
Concluídos usam histórico paginado sob demanda. Os itens de uma página são lidos
em lote e o contexto não é criado novamente em cada ciclo. A meta de p95 da T54
continua dependendo de medição específica de carga.

## Verificação real da infraestrutura

```bash
python3 scripts/verify_infrastructure.py
```

O script cria um projeto Compose temporário com nome único e porta livre, usando
`.env.example`. Aplica migrações e seeds, roda verificações e recria os containers
preservando o volume. Ao terminar, remove exclusivamente o projeto temporário e
seus volumes. Não altera nem apaga dados do projeto de desenvolvimento.

Verifica:

- Migrações repetíveis e equivalência entre schema real e metadata SQLAlchemy.
- As 20 conexões cruzadas entre os cinco serviços são negadas pelo PostgreSQL.
- Revisão antiga e tentativa de migrar banco de outro serviço são recusadas.
- Constraints de configuração, preço, mesa, estado de pedido e endereço.
- Seeds repetidos preservam alterações existentes.
- Configuração, catálogo, mesas e pedido de teste com itens sobrevivem à recriação.
- Gateway entrega a aplicação React, publica saúde e bloqueia rotas internas.
- Resolução DNS dinâmica do Nginx mantém o roteamento correto após recriar apenas
  os serviços, sem reiniciar o gateway. O cache DNS tem validade de 5 segundos.

O pedido de teste é inserido diretamente no banco temporário: a prova é de
persistência, não de funcionamento do checkout. Não há simulação de PostgreSQL
nessa suíte; os testes ASGI unitários continuam usando um substituto de conexão.

## Evidências e limites

- 108 testes Python unitários, incluindo features, entradas e classificação de erros internos.
- Suíte de infraestrutura executada com PostgreSQL 17, cinco processos FastAPI e Nginx.
- Docker inicialmente indisponível na iteração 1, acessível e validado na iteração 2.
- O TestClient precisa de execução fora da restrição de sockets do sandbox.
- Starlette emite aviso de depreciação do transporte httpx do TestClient; testes
  passam, mas uma futura atualização do transporte deve considerar esse aviso.
- Três testes de integração da Administração passaram pelo gateway com PostgreSQL 17.
- Uma verificação no Chromium com Playwright cobriu login, modelo em rascunho,
  configuração inválida, descarte, exportação da versão salva, persistência após
  recarga, edição do catálogo, cardápio em viewport de 390 px e saída da sessão.
- Treze testes de integração de Administração e retirada passaram com PostgreSQL 17.
- Sete jornadas Playwright de retirada e recuperação passaram no Chromium: acompanhamento em
  sessões distintas, carrinho após recarga, resposta perdida, reenvio idempotente,
  revisão de preços, respostas de telas desmontadas, perda de cookie, atendimento
  de tentativas antigas, histórico sob demanda e retomada pela interface.
- Entrega, Mesas, Comanda, TV e suas jornadas permanecem nas próximas etapas.

## Próxima iteração

Etapa 5, T30–T36. Persistência de endereço e taxa, coordenação com Entregas,
despacho e recuperação das operações de entrega.

## Referências de implementação

- [Alembic: conexão compartilhada em migrações](https://alembic.sqlalchemy.org/en/latest/cookbook.html#sharing-a-connection-across-one-or-more-programmatic-migration-commands)
- [PostgreSQL: advisory locks](https://www.postgresql.org/docs/17/explicit-locking.html#ADVISORY-LOCKS)

- [Nginx: resolução dinâmica de upstreams](https://nginx.org/en/docs/http/ngx_http_upstream_module.html#server)
