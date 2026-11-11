# Produtos da LPS

Catálogo e Pedidos são obrigatórios; ao menos uma de Retirada, Entrega ou Mesas
precisa estar ativa. Comanda exige Mesas. TV é independente. As combinações são
inclusivas e modelos apenas preenchem o rascunho na futura Administração.

`version` identifica o formato do arquivo, não a revisão da configuração salva.
`services` inclui Configuração e acesso, além das dependências das features.
O schema JSON descreve os tipos; as restrições cruzadas e a correspondência exata
dos serviços são validadas pelo modelo Pydantic de Configuração.

```bash
uv run --frozen python -m scripts.validate_products
```

Os nomes de serviços deste formato diferem dos rótulos legados do protótipo;
importação de localStorage não faz parte desta entrega.
