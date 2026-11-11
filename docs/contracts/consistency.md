# Concorrência e recuperação

Decisão de projeto para implementação nas etapas 3–6; ainda não executada.

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
e removido da operação quando o recibo remoto estiver confirmado. O endereço
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

## Transições e despacho

Transição informa target_state, expected_version e chave de idempotência. Bloquear
ou atualizar condicionalmente a linha do pedido, validar aresta da máquina de
estados e incrementar version. Replay de uma transição já concluída devolve seu
resultado; uma segunda ação concorrente baseada em versão antiga recebe 409.

Despacho usa uma operação durável: persistir intenção e transition_id, registrar
no serviço Entregas por PUT idempotente e só então tornar state=dispatched em
Pedidos. Durante a recuperação, impedir outras transições no mesmo pedido. O
estado público permanece ready até a confirmação; Entregas guarda metadados e não
expõe estado público independente. Aplicar o mesmo lease/retry da criação.

## Casos obrigatórios de teste futuro

Timeout antes/depois do commit remoto; reinício entre recibo remoto e commit local;
dois envios concorrentes; mesma chave com payload distinto; dois operadores avançando
mesmo pedido; configuração e preço alterados durante checkout; dependência fora do
ar após admissão; retomada de needs_attention e preservação do resultado original.
