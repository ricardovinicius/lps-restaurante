# Concorrência e recuperação

Admissão, cotação, idempotência, recuperação e transições estão implementadas para
retirada e entrega, incluindo o endereço e o despacho em Entregas. Os passos
específicos de Mesas pertencem à etapa 6.

## Ponto de admissão

Pedidos grava uma operação pending antes de chamar dependências. Configuração
valida a revisão e as features numa transação que bloqueia a linha da configuração
e persiste uma admissão por operation_id. Salvar configuração usa o mesmo bloqueio.
Isso define uma ordem: novas operações após a desativação são rejeitadas; operações
admitidas antes podem terminar. Repetir a admissão não revalida a configuração nova.
Se não houver admissão válida, a operação será rejeitada sem pedido confirmado.

Catálogo aceita uma cotação por operation_id, validando revisão, preço e
 disponibilidade sob transação consistente com a alteração de catálogo. A cotação
persistida fixa o snapshot naquele instante. Alterações posteriores afetam compras
futuras. No frontend o preço aceito deve corresponder ao preço dessa cotação;
conflitos exigem confirmação do usuário, nunca ajuste silencioso.

## Idempotência

Índice único em (principal_id, idempotency_key). A mesma chave com hash de payload
diferente retorna 409. Gravar a operação e sua identidade numa transação. Retornar
a mesma operação/pedido em toda repetição, inclusive concorrente e após reinício.
O hash inclui modalidade, origem, itens, contexto e revisões. Tokens e hash não
aparecem em logs. Manter os registros durante toda a demonstração; não expirar
chaves enquanto pedidos ou recuperação dependam delas.

## Criação coordenada

1. Persistir operação e UUID reservado do pedido.
2. Obter admissão em Configuração e gravar o resultado.
3. Obter cotação imutável em Catálogo e gravar o resultado.
4. Se mesa: validar no serviço de Mesas com operation_id e guardar referência.
5. Se entrega: persistir endereço em Entregas via PUT idempotente e guardar recibo.
6. Numa transação local, criar pedido/itens com estado received e finalizar a
   operação succeeded. Só agora emitir confirmação e incluir na fila.

Endereço em recuperação deve ser persistido com acesso restrito, nunca em logs,
e removido da operação quando o recibo remoto estiver confirmado. A implementação
também o remove quando a operação é rejeitada; em `needs_attention` ele permanece
até a retomada, pois ainda é necessário para concluir o PUT. O recibo guarda só a
taxa, validada contra os 500 centavos fixos antes de compor o total. O endereço
canônico pertence a Entregas. Falha após o PUT é recuperada repetindo o mesmo PUT;
não exige rollback distribuído. A recuperação segue adiante com o snapshot aceito.
Rejeições definitivas antes da entrega deixam apenas operação rejeitada e eventuais
cotações/admissões auditáveis, sem pedido operacional.

## Recuperação durável

Worker do serviço Pedidos consulta operações pending a cada 3 segundos, com lease
persistente e aquisição transacional (`FOR UPDATE SKIP LOCKED`). O processo HTTP e
o worker usam o mesmo mecanismo de exclusão. Lease expira após crash; operações
remotas são idempotentes mesmo se dois workers se sobrepuserem após expiração.

Backoff de 3, 6, 12, 24 e no máximo 60 segundos; após 10 tentativas a operação fica
needs_attention. Expor estado ao dono sem dados internos; fornecer comando
administrativo autenticado de retomada com auditoria. Não descartar operações nem
mostrar sucesso para encerrar o retry. Reinício retoma a partir dos dados persistidos.

Falhas de autenticação entre serviços são erros internos recuperáveis, expostos
como `dependency_authentication_failed`, e não rejeições do cliente. Somente códigos
conhecidos de negócio encerram a operação como rejected. A migração `orders_0003`
reclassifica rejeições antigas `403 forbidden` como needs_attention, preservando
rejeições legítimas e exigindo retomada administrativa após corrigir a configuração.

Administração → Envios e Balcão → Verificação de envios listam e consultam as
tentativas. O cliente informa a referência do envio; apenas o administrador pode
retomar. O atendimento consulta o resultado antes de orientar um novo envio quando
o navegador perdeu a identificação e sua credencial de recuperação.

## Transições e despacho

Transição informa target_state, expected_version e chave de idempotência. Cada
chave do operador é reservada uma única vez em `action_keys`, na mesma transação
da transição ou do despacho; uma ação concorrente com a mesma chave em outro pedido
recebe 409, sem deixar despacho confirmado em Entregas e pendente em Pedidos. Bloquear
ou atualizar condicionalmente a linha do pedido, validar aresta da máquina de
estados e incrementar version. Replay de uma transição já concluída devolve seu
resultado; uma segunda ação concorrente baseada em versão antiga recebe 409.

Despacho usa uma operação durável (`dispatch_operations`): persistir intenção,
`transition_id` e `dispatched_at` sob o bloqueio do pedido, registrar no serviço
Entregas por PUT idempotente e só então tornar state=dispatched em Pedidos, na mesma
transação que grava a transição. O id da operação é o `transition_id`, então toda
repetição após timeout ou reinício é replay em Entregas. Durante a recuperação,
outras transições do pedido retornam 409. O estado público permanece ready até a
confirmação; Entregas guarda metadados e não expõe estado público independente.
O worker aplica o mesmo lease/retry da criação aos despachos. Após dez tentativas,
o despacho fica needs_attention e aparece em Administração → Envios e no Balcão
como **Saídas para entrega**; somente o administrador retoma, com auditoria em
`dispatch_resumes`. Falhas de Entregas nunca rejeitam um despacho.

Leituras de pedidos de entrega consultam Entregas em lote. Se Entregas estiver
indisponível, a fila e o acompanhamento continuam com os dados de Pedidos e marcam
os dados de entrega como indisponíveis; o Balcão não registra a saída nesse estado.

## Casos de validação

Timeout antes/depois do commit remoto; reinício entre recibo remoto e commit local;
dois envios concorrentes; mesma chave com payload distinto; dois operadores avançando
mesmo pedido; configuração e preço alterados durante checkout; dependência fora do
ar após admissão; retomada de needs_attention e preservação do resultado original.
