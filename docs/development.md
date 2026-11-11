# Desenvolvimento e validação

## Estado atual

O ambiente inclui os cinco serviços FastAPI com bancos e migrações independentes.
As APIs de Configuração, Acesso e Catálogo atendem o frontend React pelo gateway.
Retirada, entrega, fila do Balcão e acompanhamento usam Pedidos com persistência,
idempotência e recuperação; Entregas guarda endereço, taxa e despacho. Mesas valida pedidos
de mesa e as credenciais da Comanda digital. A TV pública e os resumos administrativos
usam projeções de leitura, com configuração compartilhada e atualização periódica.

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
`.env.example`, incluindo `MESA_ORDERS_ACCESS_KEY` e `MESA_TABLES_ACCESS_KEY`.
Preserve as credenciais PostgreSQL usadas pelo volume existente.

As migrações criam as tabelas, mas não os dados de demonstração. Sem o seed de
Mesas não há mesas para pedidos nem para a Comanda, mesmo com a feature habilitada;
o Balcão avisa quando nenhuma mesa está cadastrada.

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
o resultado no [Cardápio](http://localhost:8080/cliente). Com retirada ou entrega
habilitada, adicione produtos e confirme um pedido; na entrega, informe o endereço
e confira a taxa de R$ 5,00. A conta `operator` acessa o
[Balcão](http://localhost:8080/balcao) para iniciar preparo, marcar pronto, registrar
a saída para entrega e concluir. O Cliente acompanha os estados sem recarga; o Balcão
também cria pedidos nas modalidades habilitadas.

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
| MESA_ORDERS_ACCESS_KEY | Credencial de Pedidos para sessões, admissões, cotações e entregas internas |
| MESA_CONFIGURATION_URL | URL interna de Configuração, padrão `http://configuration:8000` |
| MESA_CATALOG_URL | URL interna do Catálogo, padrão `http://catalog:8000` |
| MESA_DELIVERIES_URL | URL interna de Entregas, padrão `http://deliveries:8000` |
| MESA_TABLES_URL | URL interna de Mesas, padrão `http://tables:8000` |
| MESA_TABLES_ACCESS_KEY | Credencial de Mesas para verificar sessões de operador em Configuração |
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

## Verificação real da entrega

`tests/integration/test_delivery.py` roda na mesma suíte e no mesmo projeto Compose
descartável. Cobre taxa e total calculados no servidor, endereço guardado apenas em
Entregas, isolamento entre clientes, rotas internas fora do gateway, entrega criada
pelo Balcão, endereço ausente sem dados parciais, replay da criação e do despacho,
conclusão após desabilitar entrega e a retomada administrativa auditada.

As falhas entre serviços são reais: Entregas é parado durante a criação e pausado
durante o despacho, o que produz timeout. Os testes executam a chamada remota sem
entregar a resposta a Pedidos, reiniciam Pedidos e verificam que o worker conclui
uma única vez. Com Entregas pausado, a fila e o acompanhamento continuam com o
endereço marcado como indisponível.

Para demonstrar no navegador, habilite Entrega na Administração. Para ver a
recuperação, pare o serviço com `docker compose stop deliveries`, registre
"Saiu para entrega" e observe o aviso de confirmação pendente; após
`docker compose start deliveries`, o pedido avança sozinho em alguns segundos.

## Mesas e Comanda digital

Confirme que o seed de Mesas foi executado; ele cria as Mesas 01 a 12 e pode ser
repetido sem sobrescrever a disponibilidade:

```bash
docker compose exec tables python -m mesa_platform.seed tables
```

Habilite **Atendimento em mesa** e **Comanda digital** na Administração. No Cardápio,
escolha "Atendimento na mesa" e a mesa. No Balcão, a seção **Disponibilidade das
mesas** bloqueia novas validações sem afetar pedidos aceitos.

Para usar um tablet, abra [Comanda › vincular](http://localhost:8080/comanda/configurar)
no próprio navegador do tablet, entre como `operator` e escolha a mesa. A conta do
operador é encerrada ali e a [Comanda](http://localhost:8080/comanda) passa a enviar
rodadas e mostrar o “Já pedi”. O vínculo vale 8 horas; depois disso, vincule de novo.
O histórico é permanente por mesa e inclui pedidos do Cliente e do Balcão.

`tests/integration/test_tables.py` cobre disponibilidade concorrente, regras de
vínculo, pedidos de mesa pelas três origens, isolamento entre mesas, paginação e
total do histórico, bloqueio por features e mesa indisponível, recibo perdido com
reinício de Pedidos, conflito de `operation_id` entre mesas e conclusão de uma rodada
depois de a credencial expirar.

## TV, resumo e sincronização

A TV em `/tv` exibe até nove números por coluna e informa o excedente a partir
do total calculado no servidor. Números além desse limite não aparecem nesta versão;
a demonstração deve respeitar essa capacidade. Rotação automática permanece P1.
Pedidos já aceitos continuam no painel quando sua modalidade é desabilitada;
desabilitar TV ou perder a conexão remove os números até nova leitura autorizada.

O resumo em `/admin` conta todo o histórico preservado, sem filtro por período.
Valor dos concluídos inclui taxas e não representa receita recebida. Falhas de
Catálogo não apagam os indicadores de Pedidos; cada fonte mostra sua sincronização.

Configuração tem um único polling por aplicação React. Alterações reiniciam
carrinhos não enviados com aviso; envios pendentes preservam payload e chave.
Rascunhos administrativos são preservados e exigem revisão da nova versão salva.
O cardápio consulta sua revisão a cada três segundos e exige revisão explícita
do carrinho quando preços ou disponibilidade dos itens mudarem.

Depois de recriar os volumes de demonstração com `docker compose down -v`, recarregue
as abas abertas e autentique/provisione novamente quando necessário. A revisão da
configuração reinicia no novo banco; o frontend mantém a proteção contra revisões
antigas durante a execução normal e não detecta automaticamente a troca do banco.

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

- 168 testes Python unitários, incluindo features, entradas, endereço, despacho e classificação de erros internos.
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
- Iteração 5: 135 testes unitários, 20 de integração (sete de entrega) com
  PostgreSQL 17 e dez jornadas Playwright no Chromium, três delas de entrega.
- Iteração 6: 157 testes unitários, 27 de integração (sete de Mesas e Comanda) e
  17 jornadas Playwright, sete delas de mesa e Comanda.
- Iteração 7: três integrações novas de projeções com PostgreSQL 17 e 21 jornadas
  Playwright validadas, incluindo quatro de TV e sincronização. Resumos foram
  conferidos com mais de uma página de pedidos; a projeção pública foi verificada
  com as três modalidades, cursores, permissões e serviços opcionais parados.
- A TV foi inspecionada em 1920×1080, com nove números e contador de excedentes.
- A revisão pontual repetiu quatro testes de integração e quatro jornadas afetadas,
  cobrindo a leitura compartilhada de features, falhas sem dados visíveis e o singular
  na TV. Os pedidos extras de agregação são concluídos; sua limpeza é registrada
  antes da inserção e também executa se o setup falhar.

### Medição da propagação — T49

As jornadas gravam `propagation.json` em seu diretório de resultados e o anexam ao
relatório. A execução registrada em [stage7-propagation.json](evidence/stage7-propagation.json)
usou Linux x64, Intel i7-1165G7, oito processadores lógicos, aproximadamente 15 GiB
de RAM, Chromium 157.0.8103.38 e Docker Compose com PostgreSQL 17. O catálogo tinha
oito produtos e o seed de Mesas, 12 registros. A jornada começou sem pedidos e criou
três retiradas; configuração foi medida depois de concluí-las.

| Evento e destino | Tempos observados (ms) | Meta |
| --- | --- | --- |
| Criação: Cliente → Balcão | 1795, 271, 235 | ≤5000 |
| Transição: Balcão → TV | 837, 851, 856 | ≤5000 |
| Configuração: Administração → TV | 3357, 2829, 2828 | ≤5000 |
| Configuração: Administração → carrinho do Cliente | 1903, 1857, 1852 | ≤5000 |
| Configuração: Administração → navegação do Cliente | 1842, 1862, 1813 | ≤5000 |

Tempos medidos com relógio monotônico desde o início da ação até a mudança visível
em outro contexto de navegador. A configuração é observada simultaneamente nos três
destinos, partindo do mesmo instante inicial a cada mudança. Os contextos têm cookies
e armazenamento separados.
A captura da TV com excedentes usa dados controlados na resposta do navegador;
estados, totais e privacidade da API foram verificados separadamente em PostgreSQL.
Os resultados são do ambiente e volume descritos, não uma medição de carga/p95.

## Próxima iteração

Etapa 8, T50–T58. Consolidação dos testes e da documentação, derivação dos produtos,
ensaio de carga com 20 clientes e roteiro de apresentação em ambiente limpo.

## Referências de implementação

- [Alembic: conexão compartilhada em migrações](https://alembic.sqlalchemy.org/en/latest/cookbook.html#sharing-a-connection-across-one-or-more-programmatic-migration-commands)
- [PostgreSQL: advisory locks](https://www.postgresql.org/docs/17/explicit-locking.html#ADVISORY-LOCKS)

- [Nginx: resolução dinâmica de upstreams](https://nginx.org/en/docs/http/ngx_http_upstream_module.html#server)
