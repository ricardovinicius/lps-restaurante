## Rules

- Use blank lines to separate blocks of code to improve readability
- Separate responsabilities properly
- Focus on readability of code
- Separate the modules properly

## Contexto do projeto

Mesa Fácil é um trabalho acadêmico de Linha de Produtos de Software (LPS) para
estabelecimentos de alimentação, com arquitetura de microsserviços. Priorize
clareza, reutilização, variabilidade explícita e execução reproduzível.

O protótipo em `prototypes/mesa-facil` usa HTML, CSS e JavaScript, com dados locais
e serviços simulados. A stack abaixo foi aprovada para a implementação real;
não presuma que ela já esteja implementada. Consulte também o PRD nessa pasta.

## Stack aprovada

| Camada | Tecnologia e orientação |
| --- | --- |
| Frontend | React + TypeScript + Vite |
| Estilos | Reutilizar e adaptar o CSS do protótipo, preservando o visual aprovado |
| Navegação | React Router, com rotas para cada área |
| Backend | Python + FastAPI + Pydantic |
| Persistência | PostgreSQL |
| Acesso aos dados | SQLAlchemy |
| Migrações | Alembic, com migrações sob responsabilidade de cada serviço |
| Comunicação entre serviços | HTTP/REST inicialmente |
| Atualização das interfaces | Polling a cada 3 segundos para filas, TV e acompanhamento |
| Entrada da aplicação | Nginx para servir o frontend e encaminhar chamadas às APIs |
| Execução | Docker Compose |
| Testes de backend | pytest |
| Testes de jornadas no navegador | Playwright |

Não adicionar Kubernetes, Kafka ou Redis sem uma necessidade concreta. Manter
a infraestrutura proporcional ao escopo acadêmico.

## Organização e responsabilidades

Manter um único repositório, com pastas separadas por serviço e componentes
compartilhados no frontend. Não copiar aplicações nem criar branches permanentes
para cada variante da LPS.

Os cinco serviços previstos são:

- **Configuração e acesso:** funcionalidades habilitadas, revisões de configuração
  e usuários internos/permissões.
- **Catálogo:** produtos, categorias, preços e disponibilidade.
- **Pedidos:** criação, snapshots dos itens e valores, fila e estados do pedido.
- **Entregas:** endereço, taxa e despacho.
- **Mesas:** cadastro e validação das mesas.

Cada serviço possui seu próprio banco e credencial. Uma única instância
PostgreSQL pode hospedar esses bancos para simplificar a demonstração. Um serviço
não acessa diretamente as tabelas de outro; a integração ocorre pelas APIs.
Pedidos é a fonte canônica do estado público do pedido; o despacho deve refletir
esse estado sem criar fontes contraditórias.

Administração, Cliente, Balcão, Comanda digital e TV são áreas do frontend.
Comanda e TV consomem os serviços existentes e não exigem microsserviços próprios.
O seletor de áreas do protótipo não substitui autenticação e autorização nas APIs.

## Variabilidade da LPS

- Cardápio e gestão de pedidos são obrigatórios.
- Retirada, entrega e atendimento em mesa podem coexistir; ao menos uma
  modalidade deve estar habilitada.
- Comanda digital e TV são opcionais; Comanda digital exige atendimento em mesa.
- Lanchonete, Delivery e Restaurante são modelos personalizáveis, representados
  por arquivos JSON validados pelo serviço de Configuração.
- Validar funcionalidades e permissões no servidor, além de ajustar a interface.
- Profiles do Docker Compose podem selecionar serviços opcionais na inicialização.
  Configuração em execução e composição de implantação são conceitos distintos.
- Desabilitar funcionalidades bloqueia novas operações incompatíveis, preservando
  o acesso e a conclusão dos pedidos já aceitos. Não desligar automaticamente
  serviços necessários a pedidos em andamento.

## Sequência de implementação e validação

Implementar primeiro o fluxo de retirada completo e persistente: Configuração,
Catálogo, Pedidos e Balcão. Depois integrar Entregas, Mesas, Comanda e TV.

Preservar preços históricos dos pedidos e validar valores no backend. Tratar
idempotência na criação, transições válidas e falhas entre serviços. Usar pytest
para regras e integração e Playwright para as jornadas principais. Os testes
atuais do protótipo usam DOM simulado e não comprovam o comportamento distribuído.

Documentar comandos de execução, migrações, dados de demonstração e configurações
dos produtos para permitir uma apresentação reproduzível com Docker Compose.
