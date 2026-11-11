# Mesa Fácil
>
Protótipo acadêmico de Linha de Produtos de Software para alimentação.
>
## Executar
>
Na raiz do repositório:
>
```sh
python3 -m http.server 4173 --directory prototypes/mesa-facil/dist
```
>
Abra http://localhost:4173/?view=admin para configurar o produto. Não exige instalação de dependências.
>
## Configuração por funcionalidades
>
A Administração possui uma tela de **Configurações**, com rascunho, prévia da composição, validação de dependências, salvar e descartar alterações.
>
- **Obrigatórios:** catálogo digital e pedidos/operação.
- **Modalidades combináveis:** retirada no balcão, entrega e atendimento em mesa. É necessário selecionar ao menos uma.
- **Opcionais:** comanda digital (exige mesas) e painel de TV.
- **Modelos iniciais:** Lanchonete, Delivery e Restaurante preenchem o rascunho; não aplicam mudanças até salvar.
>
Um estabelecimento pode oferecer retirada, entrega e mesas simultaneamente. Cliente e Balcão escolhem a modalidade do pedido entre as habilitadas. O tablet atende exclusivamente mesas. TV e comanda desabilitadas deixam de aparecer nos atalhos; URLs antigas mostram uma mensagem de recurso indisponível.
>
A configuração salva é compartilhada entre abas do mesmo navegador. Mudanças reiniciam carrinhos em andamento, preservando pedidos existentes. O balcão continua exibindo pedidos de modalidades desabilitadas, para permitir sua conclusão. A TV mostra pedidos em preparo e prontos de todos os canais, exceto entregas que já saíram. Cliente acompanha seus pedidos independentemente de mudanças de configuração.
>
O JSON exportado na página Linha de produtos descreve features e serviços propostos. A configuração usa `mesa-establishment-variant-v1`, agora com `{version: 2, features: ...}`. Strings antigas `express`, `delivery` e `salao` são interpretadas como seus respectivos modelos. Parâmetros antigos `variant` na URL são ignorados.
>
## Áreas do sistema
>
| Endereço | Função |
| --- | --- |
| `/?view=admin` | Configurações, resumo, preços/disponibilidade e documentação da LPS |
| `/?view=client` | Cardápio, checkout e acompanhamento dos pedidos feitos nesta aba |
| `/?view=counter` | Fila de todos os canais, avanço dos estados e criação de pedidos |
| `/?view=tablet` | Comanda digital por mesa, novas rodadas e histórico “Já pedi” |
| `/?view=tv` | Números em preparo/prontos, relógio e tela cheia |
>
O seletor **Acessar** é um atalho de demonstração para navegar entre áreas, não um mecanismo de autenticação. As funcionalidades são escolhidas apenas nas Configurações da Administração.
>
## Demonstração
>
1. Em Configurações, selecione retirada, entrega, mesas, comanda digital e TV; salve.
2. Abra Cliente, Balcão, Comanda digital e TV em abas do mesmo navegador.
3. No Cliente, faça um pedido de entrega: informe nome e endereço. O total inclui taxa fixa de R$ 5,00.
4. Na Comanda digital, selecione uma mesa e envie itens sem nome/endereço. Cada envio cria uma rodada separada.
5. Avance os pedidos no Balcão e acompanhe o Cliente, Já pedi e a TV.
6. Desative a TV e salve: a aba do painel informa que o recurso está desabilitado.
7. Explore a Linha de produtos e baixe a configuração JSON.
>
## Limites do protótipo
>
Frontend HTML/CSS/JavaScript. Serviços, cozinha, entregas e pagamentos são simulados, sem backend, autenticação, autorização real ou cobrança. Configurar recursos não implanta microsserviços reais. Imagens ilustrativas vêm do Unsplash e fontes do Google Fonts.
>
Pedidos persistem em localStorage; os pedidos do cliente são associados à sessão da aba via sessionStorage. Não há sincronização entre dispositivos ou transações para gravações simultâneas. Isso exige backend.
>
Na comanda digital, cada rodada gera um pedido separado; não existe conta consolidada. “Já pedi” filtra o histórico salvo da mesa, com itens, quantidades, valores, data e status. Inclui pedidos concluídos, sem separação por visita; o total histórico não é saldo em aberto. Preços dos pedidos existentes são preservados.
>
A TV omite nomes, endereços e valores. Filas extensas usam rolagem. Não use dados pessoais reais na demonstração.
>
Após alterações no código, recarregue as abas antigas para carregar a nova versão. Mudanças de configuração são sincronizadas automaticamente entre abas que já carregaram esta versão.
>
## Testes
>
```sh
node --check prototypes/mesa-facil/dist/app.js
node prototypes/mesa-facil/test.mjs
```
>
Cobertura: migração, dependências de features, salvar/descartar rascunhos, restrição à administração, múltiplas modalidades, checkouts, histórico por mesa, fila multicanal, despacho, privacidade da TV, sincronização da configuração, recursos desabilitados, persistência e preços históricos. Harness com DOM simulado, sem validação visual de layout.
