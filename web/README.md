# Frontend do Mesa Fácil

React, TypeScript, Vite e React Router. A interface reutiliza a folha de estilos
do protótipo. O Docker Compose compila e serve a aplicação pelo gateway.

```bash
npm --prefix web ci
npm --prefix web run dev
npm --prefix web run build
```

O Vite usa o gateway local como proxy da API. Consulte o
[guia de desenvolvimento](../docs/development.md) para executar os serviços
e provisionar as contas demonstrativas.
