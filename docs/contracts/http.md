# Contratos HTTP v1

As rotas de Configuração, Acesso, Catálogo, retirada, entrega, Mesas e Comanda
estão implementadas, incluindo admissões, cotações, endereços, despachos, validações
de mesa e credenciais de tablet internas, projeção pública da TV e resumos administrativos.
Cada serviço gera OpenAPI a partir de seus modelos e rotas em `/openapi.json`.
Os contratos de saúde implementados estão em `docs/contracts/health-*.json`.

## Convenções

Gateway: `/api/{service}/v1`; no serviço: `/v1`. Internos: `/internal/v1`.
JSON UTF-8, campos snake_case. Campos extras rejeitados nas entradas. UUIDs para
IDs e timestamps UTC. `X-Request-ID` UUID em resposta, propagado entre serviços;
valores inválidos são substituídos, não registrados literalmente.

Listas: `limit` 1–100 (padrão 20), cursor opaco validado e filtros explícitos;
resposta `{items: [...], next_cursor: string|null}`. Ordenação estável por
`(created_at, id)` para pedidos/histórico e por `(id)` para catálogo/mesas.
A TV retorna duas listas limitadas com cursores e total por estado, sem truncamento silencioso.

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
| GET /v1/summary | Admin | — | available_products, total_products |
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
| GET /v1/queue | Operador | fulfillment=pickup|delivery|table?, cursor, limit | Pedidos confirmados não concluídos |
| POST /v1/orders/{id}/transitions | Operador + CSRF | expected_version, target_state + Idempotency-Key | Pedido atualizado ou replay; 202 despacho pendente |
| GET /v1/dispatches | Admin ou operador | state?, cursor, limit | Saídas para entrega; padrão needs_attention |
| POST /v1/dispatches/{id}/resume | Admin + CSRF | — | 202 retoma needs_attention, com auditoria; 409 nos demais estados |
| GET /v1/table-orders | Contexto tablet | cursor, limit | `{table, items, next_cursor, historical_total_cents, order_count}` da mesa da credencial, mais recentes primeiro |
| GET /v1/tv | Público com feature ativa | limit, preparing_cursor?, ready_cursor? | preparing e ready: items[{number, fulfillment, table_number}], total, next_cursor |
| GET /v1/summary | Admin | — | active_orders, completed_order_value_cents |

TV: somente estados `preparing` e `ready`, independentemente das features atuais
das modalidades de pedidos já aceitos. Recebidos, concluídos, despachados e tentativas
incompletas não aparecem. Páginas e totais vêm de uma única instrução SQL, ordenadas
por `(created_at, id)`. `total` conta todo o estado, mesmo nas páginas seguintes ou
vazias. A API não retorna nomes, endereços, itens, valores ou IDs dos pedidos.
O cookie de administrador não amplia a projeção. A feature `tv` é consultada em
Configuração a cada leitura: 403 `feature_disabled` quando desligada, 503 se não
for possível verificá-la. Respostas usam `Cache-Control: no-store`.

Resumo de Pedidos: `active_orders` conta confirmados em `received`, `preparing`,
`ready` ou `dispatched`; `completed_order_value_cents` soma `total_cents` dos
concluídos, incluindo taxas e todo o histórico preservado. Não representa receita
recebida. O resumo de Catálogo conta disponíveis e total de produtos. Ambos exigem
administrador, agregam todo o banco independentemente de paginação, retornam zero
quando não há registros e usam `Cache-Control: no-store`.

Payload de criação:

Aceita `origin=client|counter|tablet` e `fulfillment=pickup|delivery|table`. Na
retirada e na mesa, omitir `address`; fora da mesa, omitir `table_id`.

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

Mesa: Cliente e Balcão enviam `customer_name` e `table_id` de uma mesa disponível;
o Cliente escolhe a mesa sem comprovar presença, e o pedido aparece no histórico
autorizado daquela mesa (limitação acadêmica). O tablet envia só `origin=tablet`,
`fulfillment=table`, revisões e itens, com o cookie `mesa_table`, `X-CSRF-Token`
do contexto e `X-Table-Context` igual ao contexto autenticado; nome ou `table_id`
no corpo retornam 422 e outro contexto retorna 401 `table_context_changed`. Pedidos
deriva a mesa da credencial antes do hash de idempotência. A confirmação exige o
recibo de Mesas; `table_unavailable` e `table_not_found` rejeitam o envio. Pedidos
de mesa retornam `table_id` e `table_number` (snapshot), `fee_cents=0` e seguem
`received → preparing → ready → completed`. Toda resposta autorizada pela credencial
da mesa omite `customer_name`, inclusive `GET /v1/orders/{id}` e `/v1/operations/{id}`.
O tablet lê pedidos confirmados da sua mesa e só as tentativas do próprio contexto;
sem Mesas, essas leituras retornam 503, exceto quando o mesmo navegador tem sessão
válida de operador, que é verificada em seguida.

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
| GET /v1/tables | Público com `tables` ativa; staff com `include_unavailable=true` | cursor (UUID), limit | id, number, available, version |
| PATCH /v1/tables/{id} | Operador + CSRF | expected_version, available | Mesa atualizada; 409 `table_changed` |
| POST /v1/table-contexts | Operador + CSRF; `tables` e `tablet` ativas | table_id de mesa disponível | 201 cookie `mesa_table` e `{context_id, table_id, table_number, expires_at, csrf_token}` |
| GET /v1/table-contexts/current | Cookie `mesa_table` válido | — | Metadados do contexto; 401 `table_context_required` |
| DELETE /v1/table-contexts/current | Operador + CSRF | — | 204; revoga o contexto e remove o cookie |
| POST /internal/v1/validations/{operation_id} | Pedidos | table_id | 201 recibo `{operation_id, table_id, table_number}` ou 200 replay; 404/409 |
| POST /internal/v1/table-contexts/verify | Pedidos | token, csrf_token? | `{context_id, table_id, table_number, expires_at}`; 401 credencial inválida |

O cookie `mesa_table` é HttpOnly, SameSite=Lax, caminho `/api` e vale 8 horas; Mesas
guarda só o hash. Não há renovação: expirado, perdido ou revogado, o operador vincula
de novo e tentativas pendentes são conferidas na Verificação de envios. Vincular outra
mesa revoga o contexto anterior do navegador. Um contexto por navegador. Features e
disponibilidade não invalidam a credencial; só bloqueiam novos pedidos. A validação
bloqueia a linha da mesa, como a mudança de disponibilidade, e um recibo emitido
continua valendo mesmo após a mesa ficar indisponível.

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
