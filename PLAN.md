# Plano de implementação — Mesa Fácil

Este plano transforma o protótipo em um MVP acadêmico de Linha de Produtos de
Software com microsserviços. Segue as decisões do [AGENTS.md](AGENTS.md) e os
requisitos do [PRD](prototypes/mesa-facil/PRD.md). O protótipo é a referência
visual e funcional; suas simulações não representam serviços implementados.

## Como acompanhar

- Marcar uma tarefa somente após implementar e verificar seu resultado.
- Registrar evidências de validação e limitações na documentação da entrega.
- Seguir as dependências indicadas e manter cada etapa demonstrável.
- Não há estimativa de datas: prazo, equipe e rubrica acadêmica ainda precisam
  ser definidos.

## Registro de iterações

### Iteração 1 — Base técnica e contratos

T01–T07 e T12 concluídas. Contratos de negócio em `docs/contracts/http.md` e
`docs/contracts/consistency.md`; arquitetura em `docs/architecture.md`.
Validador dos produtos e endpoints de saúde dos cinco serviços implementados.
Compose, Nginx e inicialização PostgreSQL preparados, mas T08–T11 e T13 continuam
pendentes de implementação complementar e validação real. Docker indisponível
nesta distribuição WSL. Evidências e execução em `docs/development.md`.

### Iteração 2 — Persistência e infraestrutura verificadas

T08–T11 e T13 concluídas. Docker agora disponível. Cinco históricos Alembic,
modelos SQLAlchemy e seeds idempotentes implementados. Readiness exige banco,
usuário e revisão corretos. Validação com PostgreSQL 17 real comprovou isolamento
nas 20 conexões cruzadas, constraints, equivalência de schema/modelos e preservação
de configuração, catálogo, mesas e pedido com itens após recriação dos containers.
Nginx usa resolução DNS dinâmica para acompanhar endereços novos dos serviços.
49 testes unitários passaram, assim como os testes legados do protótipo. A suíte
`python3 scripts/verify_infrastructure.py` usa um projeto Compose descartável e
não remove dados de desenvolvimento. APIs de negócio e frontend integrado ainda
pendentes; próxima etapa: T14–T20.

### Iteração 3 — Administração integrada

T14–T20 concluídas. Configuração autentica administradores e operadores com
sessões revogáveis e CSRF nas mutações. Configuração e Catálogo usam revisões
para rejeitar gravações concorrentes. Nginx serve o frontend React com
Administração e Cardápio conectados às APIs. A Administração permite revisar,
validar, salvar e descartar rascunhos, exportar a configuração persistida e
editar preços e disponibilidade.

Passaram 49 testes unitários, três testes de integração com PostgreSQL 17,
a verificação de infraestrutura e uma jornada da Administração no Chromium.
A próxima etapa é o fluxo de retirada completo, T21–T29.

### Iteração 4 — Retirada completa

T21–T29 concluídas. Cliente e Balcão criam retiradas persistidas, com valores
calculados no servidor, snapshots, contexto privado de acompanhamento e fila com
transições versionadas. Admissões e cotações são idempotentes; operações pendentes
possuem recuperação após reinício e retomada administrativa auditada. O carrinho
preserva a identidade do envio em falhas e solicita revisão explícita de preços.

Passaram 99 testes unitários, nove testes de integração com PostgreSQL 17 e três
jornadas Playwright no Chromium. A integração verificou migrações/modelos,
concorrência, isolamento, preços históricos, recuperação após commit remoto e
reinício, conclusão após desabilitar retirada e retomada de operações esgotadas.
As jornadas cobriram Cliente/Balcão em sessões independentes, carrinho após recarga,
resposta perdida sem duplicidade, revisão de preço e respostas de telas desmontadas.
O build React passou. Próxima etapa: Entregas, T30–T36.

### Revisão da etapa 4 — Recuperação e consultas

Falhas internas de autenticação permanecem recuperáveis. A Administração e o
Balcão localizam tentativas pela referência, com retomada restrita ao administrador.
A perda de cookie usa uma credencial de recuperação; tentativas antigas sem essa
credencial exigem verificação com o atendimento antes de iniciar outra identificação.
Rejeições antigas causadas por chave divergente são reclassificadas por migração.

O acompanhamento atualiza páginas de pedidos ativos, consulta concluídos sob demanda
e carrega itens em lote. Passaram 108 testes unitários, 13 de integração e sete
jornadas Playwright, incluindo migração com dados antigos e retomada pela interface.
O build passou; a medição de p95 permanece na T54.

## Etapa 1 — Contratos e estrutura

Dependências: nenhuma.

- [x] T01 — Criar a estrutura do monorepo: `web/`, `services/`, `products/`,
  `infra/`, `tests/e2e/` e `docs/`, preservando `prototypes/mesa-facil/`.
- [x] T02 — Documentar responsabilidades e propriedade dos dados dos serviços
  Configuração e acesso, Catálogo, Pedidos, Entregas e Mesas.
- [x] T03 — Definir contratos HTTP: entradas, respostas, permissões, erros,
  paginação das listas aplicáveis, timeouts e operações internas.
- [x] T04 — Definir entidades e estados: valores em centavos, identificadores
  únicos, números de atendimento gerados no servidor, snapshots e distinção
  entre origem e modalidade do pedido.
- [x] T05 — Especificar revisão de configuração e catálogo, detecção de preços
  alterados, idempotência, concorrência e recuperação de operações incompletas.
- [x] T06 — Documentar o modelo de features e criar JSONs dos modelos
  Lanchonete, Delivery e Restaurante, incluindo suas dependências.

Critério de conclusão: contratos e regras documentados, com responsabilidades
claras e estratégia de falhas definida antes da integração.

Estrutura prevista:

```text
web/
services/
  configuration/
  catalog/
  orders/
  deliveries/
  tables/
products/
infra/
tests/e2e/
docs/
compose.yaml
```

## Etapa 2 — Infraestrutura e persistência

Dependências: etapa 1.

- [x] T07 — Criar os cinco projetos FastAPI com Pydantic, dependências fixadas
  e configuração por ambiente.
- [x] T08 — Preparar PostgreSQL com banco e credencial próprios por serviço,
  sem acesso direto às tabelas de outro serviço.
- [x] T09 — Configurar SQLAlchemy e Alembic por serviço, com migrações e dados
  demonstrativos reproduzíveis.
- [x] T10 — Criar imagens Docker e Compose com volumes persistentes, verificações
  de saúde e inicialização ordenada das dependências.
- [x] T11 — Configurar Nginx como entrada do frontend e das APIs; manter
  operações internas fora das rotas públicas.
- [x] T12 — Adicionar logs com identificador de correlação, sem credenciais ou
  endereços completos, e documentar as variáveis em um arquivo de exemplo.
- [x] T13 — Verificar inicialização em ambiente limpo, migrações e persistência
  após reinício dos serviços.

Critério de conclusão: ambiente inicia de forma reproduzível e preserva dados.
Manter todos os serviços disponíveis no ambiente padrão de desenvolvimento.

## Etapa 3 — Configuração, acesso e catálogo

Dependências: etapa 2.

- [x] T14 — Implementar autenticação de administrador e operador, expiração de
  sessão e autorização das operações nas APIs.
- [x] T15 — Implementar leitura e gravação versionada da configuração, impedindo
  perda de atualização concorrente.
- [x] T16 — Validar pelo menos uma modalidade ativa e a dependência Comanda →
  Mesas; manter Catálogo e Pedidos obrigatórios.
- [x] T17 — Implementar consulta do catálogo e edição administrativa de preços
  e disponibilidade, com revisão para detectar alterações.
- [x] T18 — Criar o frontend React + TypeScript + Vite e React Router, adaptando
  o CSS aprovado e separando componentes, páginas e acesso às APIs.
- [x] T19 — Implementar login e Administração: modelos no rascunho, prévia,
  validação, salvar, descartar, catálogo e exportação da configuração persistida.
- [x] T20 — Testar permissões, configurações inválidas, concorrência e persistência
  das alterações com pytest.

Critério de conclusão: administração funcional; servidor rejeita operações sem
permissão e configurações inválidas. Carregar um modelo não salva automaticamente.

## Etapa 4 — Retirada completa

Dependências: etapa 3.

- [x] T21 — Implementar criação de pedidos consultando configuração e catálogo,
  validando disponibilidade, quantidades, identificação e revisão recebida.
- [x] T22 — Calcular valores no servidor e persistir snapshots dos itens;
  rejeitar mudanças de preço não aceitas para revisão pelo cliente.
- [x] T23 — Implementar chave de idempotência com garantia no banco; repetição
  da mesma operação retorna o mesmo pedido e payload incompatível é rejeitado.
- [x] T24 — Implementar transições explícitas Recebido → Em preparo → Pronto →
  Concluído, com histórico e controle de concorrência. Repetir uma ação não pode
  avançar duas etapas.
- [x] T25 — Implementar consulta pública restrita aos pedidos do cliente por
  credencial não previsível, independente do número de atendimento.
- [x] T26 — Conectar cardápio, busca, categorias, carrinho, checkout e
  acompanhamento às APIs.
- [x] T27 — Implementar Balcão com fila, criação operacional e ações válidas.
- [x] T28 — Preservar carrinho em falhas, reutilizar a chave em tentativas da
  mesma operação e limpar o carrinho somente após confirmação.
- [x] T29 — Validar retirada ponta a ponta, snapshots, envio repetido,
  concorrência e recuperação após reinício.

Critério de conclusão: cliente cria uma retirada real, Balcão conclui o pedido e
outra sessão acompanha o andamento com dados persistidos no servidor.

## Etapa 5 — Entregas

Dependências: etapa 4.

- [ ] T30 — Implementar persistência de endereço, taxa fixa de 500 centavos e
  informações de despacho no serviço de Entregas.
- [ ] T31 — Implementar coordenação da criação entre Pedidos e Entregas com
  operações internas idempotentes e registro persistente do progresso.
- [ ] T32 — Implementar retomada ou compensação de operações incompletas após
  timeout ou reinício, conforme o contrato da T05. Definir como a recuperação
  é acionada e como identificar operações que exigem intervenção.
- [ ] T33 — Impedir confirmação e entrada na fila operacional enquanto os dados
  necessários ao atendimento não estiverem persistidos e recuperáveis.
- [ ] T34 — Implementar a etapa Saiu para entrega, mantendo Pedidos como fonte
  canônica do estado público e evitando estados contraditórios entre serviços.
- [ ] T35 — Conectar modalidade entrega, endereço, taxa e acompanhamento no
  frontend; preservar operação de pedidos antigos após desabilitar entrega.
- [ ] T36 — Testar entrega completa, ausência de endereço, timeout, falhas antes
  e depois da persistência remota, repetição e recuperação após reinício.

Critério de conclusão: entregas concluídas sem duplicidade ou confirmação parcial;
falhas entre serviços possuem recuperação verificável.

## Etapa 6 — Mesas e Comanda digital

Dependências: etapa 4; integrar à fila multicanal da etapa 5.

- [ ] T37 — Implementar cadastro demonstrativo, disponibilidade e validação de
  mesas no serviço de Mesas.
- [ ] T38 — Definir e implementar contexto de acesso do tablet e leitura permitida
  por mesa, documentando o limite acadêmico da seleção explícita de mesa.
- [ ] T39 — Implementar pedidos em mesa pelo Cliente e Balcão e rodadas
  independentes pelo Tablet, com validação de features no servidor.
- [ ] T40 — Migrar a Comanda digital: seleção de mesa, controles de toque,
  envio, confirmação e nova rodada mantendo a mesa selecionada.
- [ ] T41 — Implementar “Já pedi” com itens, quantidades, valores, datas e estados,
  incluindo concluídos e indicação de que o total é histórico.
- [ ] T42 — Testar duas rodadas, filtro de mesa, estado vazio, mesa inválida e
  bloqueio de novas operações com Comanda ou Mesas desabilitadas.

Critério de conclusão: rodadas aparecem no histórico da mesa e no Balcão;
Comanda exige Mesas. Não implementar fechamento de conta ou sessões por visita
no P0.

## Etapa 7 — TV, resumo e sincronização

Dependências: etapas 5 e 6.

- [ ] T43 — Implementar projeção pública da TV apenas com números,
  modalidade/mesa e estados necessários, sem nomes, endereços ou valores.
- [ ] T44 — Exibir Em preparo e Prontos; excluir recebidos, concluídos e entregas
  já despachadas. Validar a feature TV também na API.
- [ ] T45 — Conectar indicadores administrativos: pedidos em andamento, valor
  dos concluídos e produtos disponíveis, sem chamar esse valor de receita paga.
- [ ] T46 — Implementar polling a cada três segundos nas áreas pertinentes,
  com limpeza de timers, prevenção de requisições sobrepostas e tratamento de erro.
- [ ] T47 — Mostrar indisponibilidade e horário da última sincronização, sem
  apresentar dados antigos como atuais.
- [ ] T48 — Propagar configuração entre sessões: avisar e reiniciar carrinhos,
  bloquear recursos desabilitados e preservar acompanhamento/conclusão de pedidos.
- [ ] T49 — Medir propagação de criação, transição e configuração entre sessões
  independentes em até cinco segundos no ambiente de demonstração.

Critério de conclusão: cinco áreas conectadas, TV com dados limitados e mudanças
refletidas entre dispositivos sem recarga manual.

## Etapa 8 — Validação e entrega acadêmica

Dependências: etapa 7. Testes das regras devem acompanhar as etapas anteriores.

- [ ] T50 — Consolidar testes pytest de regras, permissões, concorrência e
  integração com PostgreSQL e serviços reais.
- [ ] T51 — Criar jornadas Playwright para as cinco áreas, com configuração
  personalizada, diferentes modalidades e preservação de pedidos antigos.
- [ ] T52 — Validar cenários de falha entre serviços, reenvio, recuperação e
  persistência após reinício, registrando evidências.
- [ ] T53 — Revisar desktop, celular, tablet e TV em 1920×1080; verificar foco,
  teclado, rótulos e controles do tablet com área mínima de 44×44 px.
- [ ] T54 — Medir leituras de cardápio/fila com 20 clientes concorrentes e meta
  de p95 inferior a um segundo; registrar hardware, volume e resultados reais.
- [ ] T55 — Preparar profiles do Compose e exemplos de derivação para Lanchonete,
  Delivery, Restaurante e combinação personalizada. Validar disponibilidade dos
  serviços necessários antes de habilitar features; não desligar serviços usados
  por pedidos em andamento.
- [ ] T56 — Documentar instalação, ambiente, migrações, seeds, execução dos testes,
  modelo de features, diagrama dos serviços e contratos das APIs.
- [ ] T57 — Criar roteiro de apresentação com configuração válida/inválida,
  pedido em cada modalidade, duas rodadas de mesa, TV e reconfiguração com pedido
  em andamento.
- [ ] T58 — Executar o roteiro em ambiente limpo e registrar requisitos atendidos,
  limitações e eventuais pendências sem confundir metas com resultados medidos.

Critério de conclusão: as cinco áreas operam sobre o backend, os dados sobrevivem
a reinícios, as APIs validam a variabilidade e a demonstração é reproduzível.

## Limites do escopo

Manter fora desta implementação: pagamento online, estoque, GPS, integrações
externas, marketplace, emissão fiscal, cancelamento, fechamento de comanda e
separação por visita. Não introduzir Kubernetes, Kafka ou Redis sem necessidade
concreta. A implantação atende um estabelecimento.

## Questões de planejamento pendentes

- Prazo e integrantes disponíveis.
- Rubrica de avaliação e quantidade mínima exigida de serviços.
- Exigência do professor quanto à derivação por implantação ou configuração em
  execução.

Essas respostas podem ajustar a organização das entregas; o plano atual adota
o escopo P0 do PRD e a stack aprovada no AGENTS.md.
