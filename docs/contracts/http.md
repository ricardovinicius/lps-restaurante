# Contratos HTTP v1

As rotas de Configuração, Acesso, Catálogo, retirada e entrega estão implementadas,
incluindo admissões, cotações, endereços e despachos internos. Mesas, TV e resumo
descrevem as etapas seguintes. Cada serviço gera OpenAPI a partir de seus modelos e rotas em `/openapi.json`.
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
| POST /internal/v1/admissions/{operation_id} | Serviço Pedidos | principal, revision, origin, fulfillment (`pickup` ou `delivery`) | 201 autorização persistida ou 200 replay; 409 revisão antiga; 403 modalidade desabilitada |
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
| POST /v1/customer-contexts | Público | recovery_token opcional; new_context=false | 201 cookie opaco; contexto existente preservado por padrão |
| POST /v1/customer-contexts/recover | Credencial de recuperação | context_id, recovery_token | Recupera o contexto e seu cookie; 401 sem prova válida |
| POST /v1/orders | Cliente, operador ou tablet | Payload abaixo + Idempotency-Key | 201 pedido confirmado ou 202 operação pendente |
| GET /v1/operations | Admin ou operador | state?, reference?, cursor, limit | Tentativas paginadas; reference busca operation_id ou Idempotency-Key em qualquer estado |
| GET /v1/operations/{id} | Dono, admin ou operador | — | state; order se succeeded; erro se rejected |
| POST /v1/operations/{id}/resume | Admin + CSRF | — | Retoma needs_attention, com auditoria; 409 nos demais estados |
| GET /v1/my-orders | Contexto cliente | status=active|completed?, cursor, limit | Pedidos apenas do contexto |
| GET /v1/orders/{id} | Dono, mesa autorizada ou operador | — | Pedido e estado |
| GET /v1/queue | Operador | fulfillment=pickup|delivery?, cursor, limit | Pedidos confirmados não concluídos |
| POST /v1/orders/{id}/transitions | Operador + CSRF | expected_version, target_state + Idempotency-Key | Pedido atualizado ou replay; 202 despacho pendente |
| GET /v1/dispatches | Admin ou operador | state?, cursor, limit | Saídas para entrega; padrão needs_attention |
| POST /v1/dispatches/{id}/resume | Admin + CSRF | — | 202 retoma needs_attention, com auditoria; 409 nos demais estados |
| GET /v1/table-orders | Contexto tablet | cursor, limit | Histórico da mesa da credencial, incluindo concluídos |
| GET /v1/tv | Público com feature ativa | limit, preparing_cursor?, ready_cursor? | Páginas por estado: number, fulfillment, table_number |
| GET /v1/summary | Admin | — | active_orders, completed_order_value_cents |

Payload de criação:

Aceita `origin=client|counter` e `fulfillment=pickup|delivery`. Mesa e tablet
serão integrados na etapa 6. Na retirada, omitir `address`.

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

Itens: de 1 a 50 produtos distintos, com quantidades inteiras de 1 a 99.
Nome obrigatório para Cliente/Balcão (1–120 caracteres após trim), endereço
obrigatório somente para entrega (1–500). Mesa exige table_id; tablet deriva esse
ID da credencial e dispensa nome. Rejeitar combinações incompatíveis; validar origin
contra o principal autenticado. Subtotal/taxa/total não são aceitos como autoridade
do cliente. Para esse exemplo total = 2 × 3290 + 500 = 7080 centavos.

Pedidos de entrega retornam `fee_cents=500` e `delivery`: `{available, address,
dispatched_at}`, lido de Entregas a cada consulta autorizada do dono ou do operador.
Se Entregas não responder, a leitura não falha: `available=false` e o endereço fica
ausente. `dispatch_state` vale `pending` ou `needs_attention` enquanto a saída para
entrega aguarda confirmação. Retirada usa `delivery=null`. Snapshots de replay das
transições não guardam esses campos; eles são lidos novamente na resposta.

Estados: retirada `received → preparing → ready → completed`; entrega
`received → preparing → ready → dispatched → completed`. Em uma entrega `ready`,
`target_state=dispatched` retorna 200 com o pedido despachado ou 202
`{operation_id, order_id, state, status_url}` quando Entregas ainda não confirmou.
Enquanto houver despacho pendente, outras transições do pedido retornam 409. Uma
chave de idempotência serve a uma única ação do operador, seja transição ou despacho;
reutilizá-la em outra ação retorna 409, inclusive em requisições simultâneas.

Idempotency-Key: UUID gerado pelo frontend antes do envio e mantido durante retries.
Resposta 202: `{operation_id, state: "pending", status_url}`. Não limpar carrinho
até `succeeded`; desabilitar edição durante a operação ou iniciar outra identidade
somente após resolução explícita. Nova revisão de preço exige revisão do carrinho
e uma nova chave, após a operação anterior ser rejeitada.

O frontend envia `X-Customer-Context` no checkout do cliente. O valor deve
corresponder ao contexto autenticado pelo cookie; não é uma credencial e não
permite trocar o dono da operação. Essa verificação impede replay com outra
identidade quando o cookie muda.

`recovery_token` possui 64 caracteres hexadecimais aleatórios. O navegador o
preserva antes do envio e o servidor guarda apenas seu hash. O UUID do contexto,
do pedido ou a referência do envio, isoladamente, não autorizam recuperação.
`new_context=true` inicia outro atendimento sem cancelar ou apagar tentativas
anteriores. Para tentativas antigas sem credencial de recuperação, a interface
exige confirmação explícita de que o resultado foi verificado com o atendimento.

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
| POST /internal/v1/deliveries/lookup | Pedidos | order_ids (1–100) | Endereço, taxa e despacho dos pedidos encontrados |
| PUT /internal/v1/deliveries/{order_id}/dispatch | Pedidos | transition_id, dispatched_at | 201 registrado ou 200 replay; 404 sem entrega |

Mesmo ID com conteúdo diferente retorna 409. Entregas não altera diretamente o
banco de Pedidos e não serve estado operacional concorrente ao de Pedidos.
A consulta em lote substitui o GET individual previsto inicialmente: a fila e o
acompanhamento leem uma página inteira em uma chamada. Pedidos trata respostas de
Entregas como dados internos; nenhum conflito de Entregas rejeita o pedido do cliente,
apenas mantém a operação em recuperação até a intervenção administrativa.

## Timeouts e repetição

Chamadas HTTP internas: conexão até 1 segundo, leitura até 2 segundos, deadline
total da requisição coordenadora 8 segundos. Sem retries automáticos de POST não
idempotente. Operações persistidas podem retornar 202 ao atingir o orçamento;
GET indisponível retorna 503. Recuperação assíncrona segue `consistency.md`.
