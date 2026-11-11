# PRD — Mesa Fácil
>
**Versão:** 1.0  
**Data:** 10 de novembro de 2026  
**Contexto:** trabalho acadêmico de Linha de Produtos de Software (LPS) com microsserviços  
**Referência:** protótipo navegável em `prototypes/mesa-facil`  
**Status:** especificação baseada no protótipo aprovado; requisitos de backend e metas abaixo são propostos para a próxima etapa, ainda não implementados.
>
## 1. Visão do produto
>
O Mesa Fácil é uma linha de produtos para pequenos estabelecimentos de alimentação. Uma base compartilhada oferece cardápio e gestão de pedidos; funcionalidades selecionadas pelo administrador adaptam o sistema a retirada no balcão, delivery e atendimento em mesa, inclusive simultaneamente.
>
O produto possui cinco áreas: Administração, Cliente, Balcão, Comanda digital e Painel de TV. Essas áreas representam contextos de uso. A configuração da LPS acontece em uma tela própria de funcionalidades, acessível à administração, e determina os recursos disponíveis em todas as áreas.
>
**Proposta de valor:** configurar uma operação de alimentação a partir de componentes reutilizáveis e acompanhar o pedido desde sua criação até sua conclusão.
>
**Tese acadêmica:** demonstrar variabilidade explícita, regras de composição e reutilização de ativos, com serviços separados por responsabilidade. Lanchonete, Delivery e Restaurante são modelos de configuração; não são aplicações copiadas nem branches independentes.
>
## 2. Problema e oportunidade
>
Estabelecimentos podem atender por mais de um canal. Um sistema limitado a um tipo fixo de negócio dificulta representar uma lanchonete que também entrega ou um restaurante que oferece retirada.
>
Além disso, cada participante precisa de uma interface adequada: o cliente escolhe itens, o atendente organiza a fila, o administrador configura a operação, o tablet recebe rodadas da mesa e a TV comunica o andamento sem expor informações pessoais.
>
Para o trabalho acadêmico, a oportunidade é construir um domínio compreensível e demonstrável, com variações concretas e um fluxo completo, mantendo o escopo pequeno o suficiente para implementar.
>
## 3. Objetivos e critérios de sucesso
>
| Objetivo | Evidência esperada |
| --- | --- |
| Demonstrar uma LPS configurável | Modelos Lanchonete, Delivery, Restaurante e uma configuração personalizada derivados da mesma base |
| Tornar a variabilidade explícita | Tela de features, dependências validadas e configuração exportável |
| Completar o ciclo do pedido | Pedido criado no Cliente ou Tablet, operado no Balcão e acompanhado até a conclusão |
| Manter consistência entre áreas | Configuração e estados refletidos sem recarregar manualmente cada interface |
| Demonstrar microsserviços | Serviços executáveis separadamente, com responsabilidades e propriedade dos dados documentadas |
| Preservar o escopo acadêmico | Execução reproduzível, dados demonstrativos e roteiro de apresentação |
>
As metas de desempenho e sincronização deste documento são critérios propostos de validação, não resultados já medidos.
>
## 4. Usuários e áreas
>
| Usuário/contexto | Necessidade | Área |
| --- | --- | --- |
| Administrador | Escolher recursos, gerenciar cardápio e acompanhar a operação | Administração |
| Cliente | Escolher itens, informar como receber e acompanhar seu pedido | Cliente |
| Atendente | Registrar pedidos e controlar recebimento, preparo e conclusão | Balcão |
| Pessoa atendida à mesa | Enviar rodadas pelo tablet e consultar o que já pediu | Comanda digital |
| Público do estabelecimento | Identificar pedidos em preparo ou prontos | Painel de TV |
>
No MVP, o Balcão concentra a operação da cozinha; uma área exclusiva para cozinheiros não é necessária. O seletor “Acessar” do protótipo é um atalho de demonstração, não um controle de acesso.
>
## 5. Escopo e prioridades
>
**P0:** necessário à entrega acadêmica com microsserviços. **P1:** evolução após o fluxo principal. **Fora do escopo:** não necessário para essa entrega.
>
### 5.1 P0 — MVP acadêmico
>
- Tela administrativa de composição por funcionalidades, com modelos iniciais, rascunho, validação, salvar e descartar.
- Catálogo com categorias, preços e disponibilidade; manutenção de preços/disponibilidade pela administração.
- Pedidos com múltiplos itens, quantidades, modalidade, identificação necessária e preços registrados na compra.
- Retirada, entrega com taxa fixa de R$ 5,00 e atendimento em mesa.
- Fila do balcão reunindo todas as modalidades e permitindo avanço dos estados.
- Comanda digital opcional para tablet, com seleção de mesa, novas rodadas e “Já pedi”.
- Painel de TV opcional, com pedidos em preparo/prontos e números legíveis.
- Acompanhamento de pedidos do cliente e atualização entre dispositivos via backend.
- Persistência no servidor e validação das regras também nas APIs.
- Controle mínimo de acesso administrativo e operacional; acesso público restrito ao necessário.
- Documentação da LPS, serviços e roteiro de demonstração.
>
### 5.2 P1 — evoluções
>
- Sessão de atendimento por visita, separando históricos de clientes diferentes na mesma mesa.
- Consolidação de rodadas em uma comanda, fechamento e registro do pagamento.
- Cadastro completo de produtos, categorias e imagens pela interface; no P0, catálogo inicial pode ser provisionado por dados demonstrativos.
- Cancelamento de pedidos com motivo e regras por estado.
- Taxa de entrega configurável e estimativas de tempo ajustáveis.
- QR Code por mesa e identificação permanente do tablet.
- Paginação automática da TV, alertas sonoros e opções de apresentação.
>
### 5.3 Fora do escopo
>
Marketplace, integração com iFood/WhatsApp, pagamento online, emissão fiscal, GPS, roteirização, estoque, reservas, cupons, fidelidade, relatórios financeiros avançados, operação offline e múltiplos estabelecimentos na mesma instalação.
>
## 6. Modelo de funcionalidades da LPS
>
| Feature | Tipo | Regra | Efeito |
| --- | --- | --- | --- |
| Catálogo digital | Obrigatória | Sempre habilitada | Produtos, categorias, preços e disponibilidade |
| Pedidos e operação | Obrigatória | Sempre habilitada | Carrinho, acompanhamento e fila operacional |
| Retirada no balcão | Opcional de grupo | Ao menos uma modalidade deve existir | Pedido retirado no estabelecimento |
| Entrega | Opcional de grupo | Exige endereço no pedido | Taxa fixa e etapa de saída para entrega |
| Atendimento em mesa | Opcional de grupo | Exige mesa válida no pedido | Associação do pedido à mesa |
| Comanda digital | Opcional | Depende de Atendimento em mesa | Interface de tablet e histórico de rodadas |
| Painel de TV | Opcional | Usa o núcleo obrigatório de Pedidos | Exibição pública de números e andamento |
>
**Restrições formais:**
>
- `Catálogo = verdadeiro` e `Pedidos = verdadeiro`.
- `Retirada OU Entrega OU Mesas = verdadeiro` — seleção inclusiva, não exclusiva.
- `ComandaDigital implica Mesas`.
- Cada pedido utiliza exatamente uma modalidade habilitada, mesmo que o estabelecimento ofereça várias.
>
### 6.1 Modelos iniciais
>
| Modelo | Retirada | Entrega | Mesas | Comanda digital | TV |
| --- | --- | --- | --- | --- | --- |
| Lanchonete | Sim | Não | Não | Não | Sim |
| Delivery | Não | Sim | Não | Não | Não |
| Restaurante | Não | Não | Sim | Sim | Sim |
>
Os modelos preenchem o rascunho e podem ser alterados. Uma combinação diferente é identificada como “Personalizado”. Nenhum modelo cria uma base de código separada.
>
### 6.2 Configuração e derivação
>
A seleção de funcionalidades deriva o comportamento do produto. Desabilitar um recurso bloqueia novas operações dependentes dele e remove seus pontos de entrada; não apaga dados nem impede concluir pedidos existentes.
>
A exportação JSON descreve features e serviços necessários à configuração salva. A troca de funcionalidades em tempo de execução não implica criar ou destruir serviços automaticamente. No MVP, a infraestrutura pode manter os serviços disponíveis enquanto a configuração controla o comportamento. A composição de implantação deve garantir que todo serviço necessário esteja disponível, inclusive para pedidos em andamento.
>
## 7. Requisitos funcionais
>
| ID | Prioridade | Requisito e critério de aceite |
| --- | --- | --- |
| RF-01 | P0 | **Configurar features:** administrador seleciona recursos, vê uma prévia e salva uma combinação válida. Rascunhos não alteram as outras áreas. |
| RF-02 | P0 | **Validar dependências:** impedir salvar sem modalidade ou com Comanda digital sem Mesas. Exibir o motivo junto à configuração. |
| RF-03 | P0 | **Aplicar modelos:** carregar Lanchonete, Delivery ou Restaurante no rascunho, sem salvar automaticamente. Descartar restaura a configuração persistida. |
| RF-04 | P0 | **Propagar configuração:** áreas abertas e novas acessam a mesma configuração. Recursos desabilitados não podem ser usados por URL direta ou API. |
| RF-05 | P0 | **Preservar pedidos:** mudanças reiniciam carrinhos com aviso, mas mantêm pedidos e valores históricos. O Balcão continua operando pedidos de modalidades desabilitadas. |
| RF-06 | P0 | **Gerenciar catálogo:** administrador altera preço e disponibilidade. Alterações aparecem no cardápio; pedidos existentes não são recalculados. |
| RF-07 | P0 | **Consultar cardápio:** cliente filtra por categoria e nome, visualiza preço/descrição e adiciona produtos disponíveis. Busca sem resultado apresenta estado vazio. |
| RF-08 | P0 | **Montar pedido:** adicionar/remover unidades, mostrar subtotal, taxa aplicável e total; não permitir envio de carrinho vazio. |
| RF-09 | P0 | **Selecionar atendimento:** oferecer somente modalidades habilitadas. Havendo mais de uma, solicitar a escolha; ela define campos e cálculo do pedido. |
| RF-10 | P0 | **Validar envio:** exigir nome no Cliente/Balcão; endereço na entrega; mesa no salão. Tablet usa a mesa como identificação, sem nome/endereço. API valida disponibilidade e calcula valores. |
| RF-11 | P0 | **Confirmar criação:** retornar identificador e número legível, registrar itens/valores/modalidade e limpar o carrinho apenas após sucesso. |
| RF-12 | P0 | **Acompanhar pedido:** cliente consulta seus pedidos, itens, valores e estado, inclusive após mudança nas funcionalidades do estabelecimento. |
| RF-13 | P0 | **Operar o balcão:** apresentar fila de todas as modalidades, identificação, itens e ações válidas. Permitir também criar pedido em nome do cliente. |
| RF-14 | P0 | **Avançar estados:** permitir somente transições válidas; entrega possui etapa adicional “Saiu para entrega”. Conclusão retira o pedido da fila ativa. |
| RF-15 | P0 | **Usar tablet:** selecionar mesa, montar uma rodada e enviar. Confirmar número, manter a mesa e permitir nova rodada. Não habilitar tablet sem suas features. |
| RF-16 | P0 | **Consultar “Já pedi”:** listar rodadas da mesa selecionada, com data, itens, quantidades, valores e estado. Incluir concluídos; sinalizar que o total é histórico, não conta aberta. |
| RF-17 | P0 | **Exibir TV:** mostrar números em preparo e prontos, com mesa/modalidade quando necessário; excluir recebidos, concluídos e entregas já despachadas. Não mostrar nomes, endereços ou valores. |
| RF-18 | P0 | **Mostrar resumo:** administração consulta quantidade de pedidos em andamento, valor dos concluídos e produtos disponíveis. Valor de pedidos não deve ser chamado de receita recebida. |
| RF-19 | P0 | **Documentar composição:** mostrar features salvas e serviços propostos; exportar JSON consistente com a configuração persistida. |
>
### 7.1 Regras de valores e identificação
>
- Taxa de entrega do MVP: R$ 5,00 por pedido de entrega; demais modalidades sem taxa adicional.
- Total: soma de quantidade × preço registrado de cada item + taxa aplicável.
- No backend, usar centavos inteiros ou decimal exato para valores monetários.
- Identificador técnico único e número de atendimento gerado pelo servidor, sem depender da contagem local de pedidos.
- Cada rodada do tablet é um pedido independente no P0.
- Mudança de preço após envio não altera pedido existente.
- Se preço ou disponibilidade mudar antes da confirmação, informar o cliente e solicitar revisão do pedido, sem alterar silenciosamente o valor aceito.
>
## 8. Jornadas principais
>
### 8.1 Administrador compõe o produto
>
1. Abre Configurações e escolhe um modelo ou ajusta features individualmente.
2. Vê o resumo da composição e eventuais dependências inválidas.
3. Salva; o servidor valida e persiste uma nova revisão.
4. As áreas recebem a atualização, ajustam recursos disponíveis e avisam sobre carrinhos reiniciados.
5. Pedidos já enviados continuam acessíveis para acompanhamento e conclusão.
>
### 8.2 Cliente faz pedido de entrega
>
1. Consulta o cardápio e adiciona itens.
2. Escolhe Entrega, se habilitada, informa nome/endereço e revisa a taxa.
3. Confirma; recebe número e acompanha o andamento.
4. O Balcão inicia preparo, marca pronto, registra saída e conclui a entrega.
>
### 8.3 Pessoa envia rodadas pelo tablet
>
1. Com Mesas e Comanda digital habilitadas, seleciona a mesa.
2. Escolhe itens e envia para a cozinha.
3. Recebe confirmação, mantém a mesa e pode iniciar outra rodada.
4. Em “Já pedi”, acompanha rodadas e estados da mesa.
5. O P0 não fecha conta nem separa visitas; essa limitação deve permanecer explícita na demonstração.
>
### 8.4 Balcão e TV acompanham a operação
>
1. O atendente vê os pedidos recebidos de todos os canais.
2. Ao iniciar preparo, o número aparece na coluna correspondente da TV.
3. Ao marcar pronto, o número passa para a coluna de prontos.
4. Retirada/conclusão ou saída para entrega remove o número do painel.
>
## 9. Estados do pedido
>
| Modalidade | Transições permitidas |
| --- | --- |
| Retirada | Recebido → Em preparo → Pronto → Concluído |
| Mesa | Recebido → Em preparo → Pronto → Concluído |
| Entrega | Recebido → Em preparo → Pronto → Saiu para entrega → Concluído |
>
O recebimento na cozinha é representado por “Recebido”; não há aceite separado no MVP. Regressão de estado, edição após envio e cancelamento não fazem parte do P0.
>
O protótipo representa saída para entrega com um marcador adicional; o backend deve expor estados inequívocos e validar as transições. Repetir uma ação já aplicada não deve avançar o pedido novamente.
>
## 10. Arquitetura proposta
>
Esta seção orienta a implementação; não afirma que os serviços abaixo já existem. A separação final de APIs e eventos deve ser detalhada em um documento técnico.
>
| Serviço | Responsabilidade | Dados sob sua propriedade |
| --- | --- | --- |
| Configuração e acesso | Features, revisões e acesso de administrador/operador | Configuração do estabelecimento, usuários internos e permissões |
| Catálogo | Produtos, categorias, preços e disponibilidade | Catálogo e sua revisão |
| Pedidos | Criação, snapshots de itens, valores, fila e ciclo de vida | Pedidos, itens, estados e histórico de transições |
| Entregas | Dados e operação específicos da entrega | Endereço, taxa registrada e dados de despacho |
| Atendimento em mesa | Cadastro/validação de mesas e associação ao atendimento | Mesas e identificadores de atendimento; sessões de visita na evolução P1 |
>
Pedidos mantém a referência da mesa e a modalidade para consulta; isso não transfere a propriedade do cadastro de mesas. O estado público do pedido tem fonte canônica em Pedidos; ações de entrega precisam refletir esse estado sem duas fontes contraditórias.
>
### 10.1 Diretrizes
>
- Frontend React para as áreas; FastAPI como tecnologia proposta para serviços; PostgreSQL para persistência; Nginx como ponto de entrada; Docker Compose para execução acadêmica.
- Uma instância PostgreSQL pode hospedar bancos separados por serviço. Um serviço não escreve diretamente nas tabelas de outro.
- Comunicação HTTP inicialmente; atualização das interfaces por polling ou eventos enviados pelo servidor, conforme a implementação mais simples que cumpra os critérios de aceite.
- A TV é uma interface de leitura de Pedidos, não exige microsserviço próprio. O mesmo vale para o tablet.
- Configuração precisa ser aplicada no servidor, além de ocultar botões na interface.
- Mudanças devem usar uma revisão de configuração para detectar clientes desatualizados.
- Não introduzir Kubernetes ou mensageria apenas para aumentar o número de tecnologias na apresentação.
>
### 10.2 Consistência e falhas
>
- Criação recebe uma chave de idempotência; uma repetição após timeout não cria dois pedidos.
- Confirmar sucesso somente quando os dados necessários ao atendimento estiverem persistidos. Uma entrega não pode ser confirmada sem endereço recuperável.
- Definir compensação ou recuperação para falhas entre serviços, documentando como evitar pedidos incompletos.
- Preservar o carrinho quando o envio falhar; permitir nova tentativa com a mesma identidade da operação.
- Diante de revisão de configuração desatualizada, rejeitar criação com orientação de atualização, sem aceitar uma modalidade desabilitada.
- Indisponibilidade de atualização não deve apresentar dados antigos como atuais: exibir aviso e horário da última sincronização.
>
## 11. Dados e acesso
>
### 11.1 Entidades essenciais
>
| Entidade | Campos principais |
| --- | --- |
| Configuração | Identificador do estabelecimento, revisão, features, data de atualização |
| Produto | Identificador, categoria, nome, descrição, preço e disponibilidade |
| Pedido | Identificador, número, modalidade, origem, identificação do cliente/mesa, estado, total, data e revisão usada |
| Item do pedido | Referência de produto, nome/preço registrados, quantidade e subtotal |
| Entrega | Referência de pedido, endereço, taxa e informação de despacho |
| Mesa | Identificador, número e disponibilidade para atendimento |
| Transição | Pedido, estado anterior/novo, responsável e data |
>
Origem do pedido (Cliente, Balcão ou Tablet) é diferente de modalidade (Retirada, Entrega ou Mesa). Essa distinção deve ser preservada.
>
### 11.2 Acesso mínimo proposto
>
- Administrador: configuração, catálogo, resumo e composição da LPS.
- Operador: criação operacional, fila e avanço dos pedidos.
- Cliente: criação pública e consulta somente de seus pedidos, mediante identificador de acesso não previsível.
- Tablet: contexto de mesa e leitura dos pedidos permitidos nesse contexto. Na demonstração pode haver seleção explícita da mesa; isso não constitui isolamento seguro para uso comercial.
- TV: leitura limitada aos campos necessários ao painel.
>
IDs públicos sequenciais não devem, sozinhos, autorizar consulta de dados do pedido. Configuração e acesso por perfil continuam sujeitos à autorização do servidor.
>
## 12. Requisitos não funcionais
>
| ID | Requisito proposto | Validação |
| --- | --- | --- |
| RNF-01 | Interface responsiva para desktop, tablet e celular; TV legível em 1920×1080 | Revisão visual nos quatro formatos, sem cortes de ações essenciais |
| RNF-02 | Controles principais do tablet com área de toque mínima de 44×44 px | Inspeção de layout |
| RNF-03 | Teclado, foco visível, rótulos e status compreensíveis sem depender somente de cor | Teste manual de navegação e leitura |
| RNF-04 | Estados e configurações refletidos em outros dispositivos em até 5 segundos na rede de demonstração | Medir criação, transição e mudança de feature entre duas sessões/dispositivos |
| RNF-05 | Dados preservados após recarga e reinício dos serviços | Teste de persistência |
| RNF-06 | Não duplicar pedido em repetição de envio nem perder atualizações concorrentes | Testes de idempotência e duas sessões operacionais |
| RNF-07 | Leituras do cardápio/fila com p95 inferior a 1 segundo para 20 clientes concorrentes no ambiente documentado | Ensaio limitado, informando hardware e volume de dados |
| RNF-08 | Diagnóstico de falhas por serviço e pedido | Logs com identificador de correlação, sem endereço completo ou credenciais |
| RNF-09 | Execução reproduzível | Compose, migrações, dados demonstrativos e instruções verificadas |
>
Esses valores são metas de aceite acadêmico; não são compromissos comerciais de disponibilidade ou escala.
>
## 13. Plano de validação e apresentação
>
| Cenário | Resultado esperado |
| --- | --- |
| Carregar um modelo sem salvar | As demais áreas não mudam |
| Desmarcar todas as modalidades | Salvamento bloqueado com explicação |
| Ativar Comanda sem Mesas | Salvamento bloqueado; dependência indicada |
| Habilitar retirada + entrega + mesas | Cliente escolhe entre três modalidades; Balcão reúne todos os pedidos |
| Criar entrega sem endereço | Pedido rejeitado sem persistência parcial |
| Enviar duas rodadas da mesma mesa | Dois pedidos distintos; ambos em “Já pedi” |
| Consultar outra mesa | Histórico filtrado; estado vazio quando não há pedidos |
| Desabilitar entrega com pedido em preparo | Novo delivery bloqueado; pedido existente continua até conclusão |
| Desabilitar TV ou Comanda com área aberta | Recurso indisponível automaticamente, inclusive em URL direta |
| Atualizar preço de produto | Próxima compra usa novo preço; pedido anterior mantém snapshot |
| Repetir envio após timeout | Um único pedido persistido |
| Acessar endpoint administrativo sem permissão | Operação negada sem mudança de dados |
| Reiniciar serviços | Configuração e pedidos recuperados |
| Exportar configuração personalizada | JSON reflete features salvas e serviços necessários |
>
A entrega deve incluir modelo de features, configuração de cada exemplo, diagrama de serviços, código, instruções de execução e evidências dos testes. O roteiro deve demonstrar tanto uma combinação válida quanto a rejeição de uma combinação inválida.
>
## 14. Estado atual versus implementação prevista
>
| Aspecto | Protótipo atual | Próxima implementação P0 |
| --- | --- | --- |
| Interface | HTML/CSS/JavaScript navegável | Reutilizar experiência; React proposto |
| Configuração | Features em localStorage, com dependências e rascunho | Configuração persistida no servidor, revisada e autorizada |
| Comunicação | Eventos de storage entre abas do mesmo navegador | APIs e sincronização entre dispositivos |
| Pedidos | Persistência local e avanço manual | Persistência no servidor, concorrência e idempotência |
| Microsserviços | Representados conceitualmente | Serviços executáveis e dados sob responsabilidade definida |
| Controle de acesso | Seletor de áreas, sem autenticação real | Separação de acessos e validação nas APIs |
| Comanda | Rodadas por mesa; histórico sem separação por visita | Mesmo escopo demonstrativo; sessões/conta consolidada em P1 |
| TV | Dados locais, filtrados e sem dados pessoais | Projeção de leitura atualizada pelo backend |
| Testes | Comportamento com DOM simulado e formatação | Integração dos serviços, cenários de falha e validação visual |
>
Os testes atuais não comprovam segurança, comportamento distribuído, sincronização entre dispositivos nem metas de desempenho.
>
## 15. Sequência de entrega
>
1. **Base e contratos:** consolidar modelo de features, entidades, propriedade dos dados e estados; definir interfaces entre serviços.
2. **Núcleo funcional:** Configuração/acesso, Catálogo e Pedidos; fluxo de retirada completo e persistente.
3. **Variabilidade:** Entregas e Mesas; combinações válidas, dependências e preservação de pedidos após reconfiguração.
4. **Experiências:** Cliente, Balcão, Tablet e TV conectados ao backend e sincronizados entre dispositivos.
5. **Validação acadêmica:** testes, recuperação de falhas, documentação, exemplos de derivação e apresentação.
>
Não há prazo ou capacidade da equipe informados. Estimativas e divisão de tarefas devem ser definidas antes de comprometer datas.
>
## 16. Riscos e decisões pendentes
>
| Risco/questão | Tratamento |
| --- | --- |
| Microsserviços ampliarem o trabalho além do prazo | Priorizar retirada ponta a ponta; adicionar os serviços opcionais depois |
| Configurações apenas esconderem botões | Validar regras no servidor e demonstrar rejeição de operações incompatíveis |
| Falhas entre serviços gerarem pedidos parciais | Especificar idempotência, compensação e testes antes da integração |
| Histórico de mesa misturar visitas | Manter uso demonstrativo e limitação explícita no P0; sessões obrigatórias antes de uso real compartilhado |
| Mudança de features interromper pedidos existentes | Separar habilitação de novas operações da conclusão de pedidos já aceitos |
| Identificadores de pedido exporem dados | Separar número de atendimento de credencial de consulta |
| Infraestrutura dominar a apresentação | Usar Compose e demonstrar funcionalidades, variabilidade e responsabilidades |
>
**A confirmar com a equipe/professor:** prazo, integrantes, rubrica de avaliação, quantidade mínima exigida de serviços, exigência de derivação por implantação versus configuração em execução e profundidade esperada dos testes. Nenhum desses pontos foi informado; o documento adota um MVP acadêmico de um estabelecimento por instalação.
