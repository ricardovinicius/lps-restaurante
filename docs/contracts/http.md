# Contratos HTTP v1

As rotas públicas de Configuração, Acesso e Catálogo e a verificação interna de
sessão foram implementadas na etapa 3. Admissões, cotações e os contratos de Pedidos,
Mesas e Entregas descrevem as etapas seguintes. Cada serviço gera OpenAPI a partir
de seus modelos e rotas em `/openapi.json`.
Os contratos de saúde implementados estão em `docs/contracts/health-*.json`.

## Convenções

Gateway: `/api/{service}/v1`; no serviço: `/v1`. Internos: `/internal/v1`.
JSON UTF-8, campos snake_case. Campos extras rejeitados nas entradas. UUIDs para
IDs e timestamps UTC. `X-Request-ID` UUID em resposta, propagado entre serviços;
valores inválidos são substituídos, não registrados literalmente.

Listas: `limit` 1–100 (padrão 20), cursor opaco validado e filtros explícitos;
resposta `{items: [...], next_cursor: string|null}`. Ordenação estável por
`(created_at, id)` para pedidos/histórico e por `(id)` para catálogo/mesas.
A TV retorna duas listas limitadas com cursores, sem truncamento silencioso.

Erros de negócio: `{error: {code, message, details}, request_id}`. Não expor senha,
endereço, SQL ou stack trace. 401 sessão ausente/inválida; 403 sem permissão ou
feature desabilitada; 404 recurso inexistente ou pertencente a outro contexto;
409 conflito de revisão, preço, transição ou idempotência; 422 entrada inválida;
503 dependência indisponível. 503 inclui `Retry-After: 3`. 202 indica operação
pendente, nunca confirmação de atendimento. A validação de saúde usa apenas 200/503.

Mutações de configuração, catálogo e estado exigem `expected_revision` ou
`expected_version`; atualização condicional no banco evita sobrescrever concorrentes.

## Configuração e acesso

| Método / caminho | Acesso | Entrada | Resultado |
| --- | --- | --- | --- |
| POST /v1/sessions | Público | username, password | 201 cookie de sessão; perfil e expires_at |
| DELETE /v1/sessions/current | Autenticado + CSRF | — | 204, revogação |
| GET /v1/sessions/current | Autenticado | — | Perfil, expires_at e token CSRF |
| GET /v1/configuration | Público | — | revision, features, updated_at |
| PUT /v1/configuration | Admin + CSRF | expected_revision, features | 200 configuração validada; 409 revisão antiga |
| GET /v1/configuration/presets | Admin | — | Modelos JSON validados pelo servidor |
| GET /v1/configuration/export | Admin | — | version do formato, name, features, services |
| POST /internal/v1/admissions/{operation_id} | Serviço Pedidos | principal, revision, origin, fulfillment | 201 autorização persistida ou 200 replay; 409 revisão antiga |
| POST /internal/v1/sessions/verify | Serviço autorizado | token, required_scope, csrf_token opcional | username, role, expires_at ou 401/403 |

O cookie `mesa_staff` tem caminho `/api`, é HttpOnly e usa SameSite=Lax.
Mutações autenticadas exigem o cabeçalho `X-CSRF-Token`. A verificação interna
recebe `X-Mesa-Service-Key` e valida o token CSRF quando ele é fornecido.

A configuração exportada segue `products/schema/product.schema.json`; sua versão
é versão do formato, não a revisão de concorrência. Modelos são rascunhos no UI;
salvar é uma operação separada. Administrador e operador não são equivalentes.

## Catálogo

| Método / caminho | Acesso | Entrada | Resultado |
| --- | --- | --- | --- |
| GET /v1/products | Público | q, category_id, cursor, limit | revision e página de produtos disponíveis |
| GET /v1/admin/products | Admin | cursor, limit | revision e página incluindo indisponíveis |
| PATCH /v1/products/{id} | Admin + CSRF | expected_revision, price_cents, available | `{product, revision}` |
| POST /internal/v1/quotes/{operation_id} | Pedidos | expected_revision, items[{product_id, quantity, expected_unit_price_cents}] | Snapshot imutável e total; 409 catálogo/preço alterado |

Produto: id, category_id, category_name, name, description, image_url,
price_cents e available. Rejeitar produtos duplicados no mesmo payload.
Cotação aceita é persistida por operation_id; replay com payload distinto retorna
409. Cotação fixa valores, não representa reserva de estoque (fora do P0).

## Pedidos

| Método / caminho | Acesso | Entrada | Resultado |
| --- | --- | --- | --- |
| POST /v1/customer-contexts | Público | — | 201 cookie opaco de contexto anônimo |
| POST /v1/orders | Cliente, operador ou tablet | Payload abaixo + Idempotency-Key | 201 pedido confirmado ou 202 operação pendente |
| GET /v1/operations/{id} | Dono ou operador | — | state; order se succeeded; erro se rejected |
| GET /v1/my-orders | Contexto cliente | cursor, limit | Pedidos apenas do contexto |
| GET /v1/orders/{id} | Dono, mesa autorizada ou operador | — | Pedido e estado |
| GET /v1/queue | Operador | fulfillment?, cursor, limit | Pedidos confirmados não concluídos |
| POST /v1/orders/{id}/transitions | Operador + CSRF | expected_version, target_state + Idempotency-Key | Pedido atualizado ou replay |
| GET /v1/table-orders | Contexto tablet | cursor, limit | Histórico da mesa da credencial, incluindo concluídos |
| GET /v1/tv | Público com feature ativa | limit, preparing_cursor?, ready_cursor? | Páginas por estado: number, fulfillment, table_number |
| GET /v1/summary | Admin | — | active_orders, completed_order_value_cents |

Payload de criação:

```json
{
  "configuration_revision": 1,
  "catalog_revision": 1,
  "origin": "client",
  "fulfillment": "delivery",
  "customer_name": "Cliente demonstrativo",
  "address": "Endereço demonstrativo",
  "items": [
    {"product_id": "24a548d7-0135-4125-a4e4-dfb69c2c4064", "quantity": 2, "expected_unit_price_cents": 3290}
  ]
}
```

Nome obrigatório para Cliente/Balcão (1–120 caracteres após trim), endereço
obrigatório somente para entrega (1–500). Mesa exige table_id; tablet deriva esse
ID da credencial e dispensa nome. Rejeitar combinações incompatíveis; validar origin
contra o principal autenticado. Subtotal/taxa/total não são aceitos como autoridade
do cliente. Para esse exemplo total = 2 × 3290 + 500 = 7080 centavos.

Idempotency-Key: UUID gerado pelo frontend antes do envio e mantido durante retries.
Resposta 202: `{operation_id, state: "pending", status_url}`. Não limpar carrinho
até `succeeded`; desabilitar edição durante a operação ou iniciar outra identidade
somente após resolução explícita. Nova revisão de preço exige revisão do carrinho
e uma nova chave, após a operação anterior ser rejeitada.

## Mesas

| Método / caminho | Acesso | Entrada | Resultado |
| --- | --- | --- | --- |
| GET /v1/tables | Operador ou cliente com mesas ativas | cursor, limit | id, number, available |
| POST /v1/table-contexts | Operador + CSRF | table_id | Credencial de tablet com mesa e expires_at |
| POST /internal/v1/validations/{operation_id} | Pedidos | table_id | Snapshot de mesa válida e ativa, idempotente |
| POST /internal/v1/table-contexts/verify | Serviço autorizado | token | Mesa e escopos ou 401/403 |

O contexto demonstra histórico por mesa, não por visita. Provisionamento pelo
operador não é autenticação de clientes de um restaurante comercial.

## Entregas (somente interno no P0)

| Método / caminho | Acesso | Entrada | Resultado |
| --- | --- | --- | --- |
| PUT /internal/v1/deliveries/{order_id} | Pedidos | operation_id, address | 201 persistido ou 200 replay; fee_cents=500 |
| GET /internal/v1/deliveries/{order_id} | Pedidos | — | Endereço/taxa/despacho para resposta autorizada |
| PUT /internal/v1/deliveries/{order_id}/dispatch | Pedidos | transition_id, dispatched_at | Despacho idempotente |

Mesmo ID com conteúdo diferente retorna 409. Entregas não altera diretamente o
banco de Pedidos e não serve estado operacional concorrente ao de Pedidos.

## Timeouts e repetição

Chamadas HTTP internas: conexão até 1 segundo, leitura até 2 segundos, deadline
total da requisição coordenadora 8 segundos. Sem retries automáticos de POST não
idempotente. Operações persistidas podem retornar 202 ao atingir o orçamento;
GET indisponível retorna 503. Recuperação assíncrona segue `consistency.md`.
