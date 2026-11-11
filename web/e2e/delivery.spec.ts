import { expect, test } from "@playwright/test";
import { prepare } from "./helpers";

test("cliente pede entrega com taxa e o Balcão registra a saída e conclui", async ({ browser, request, baseURL }) => {
  const { product } = await prepare(request, { pickup: true, delivery: true });
  const customer = await browser.newContext({ baseURL, viewport: { width: 390, height: 844 } });
  const staff = await browser.newContext({ baseURL });
  const address = "Rua da Jornada, " + Date.now();

  try {
    const page = await customer.newPage();
    await page.goto("/cliente");
    const cart = page.getByRole("complementary", { name: "Seu pedido" });
    await cart.getByLabel("Como você prefere receber?").selectOption({ label: "Entrega no endereço" });
    await page.getByRole("button", { name: "Adicionar " + product.name, exact: true }).click();
    const name = "Jornada entrega " + Date.now();
    await cart.getByLabel("Nome para identificação").fill(name);
    await expect(cart.getByRole("button", { name: "Confirmar entrega", exact: true })).toBeDisabled();
    await cart.getByLabel("Endereço de entrega").fill(address);
    await expect(cart.getByText("Taxa de entrega")).toBeVisible();
    await expect(cart.locator(".grand-total")).toContainText(
      new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" }).format((product.price_cents + 500) / 100),
    );

    await page.reload();
    await expect(cart.getByLabel("Endereço de entrega")).toHaveValue(address);
    await cart.getByRole("button", { name: "Confirmar entrega", exact: true }).click();
    const tracked = page.getByRole("region", { name: "Meus pedidos" }).getByRole("article").filter({ hasText: name });
    await expect(tracked).toContainText("Entregar em: " + address);
    await expect(tracked).toContainText("Taxa de entrega");
    await expect(cart.getByText("Seu carrinho está vazio")).toBeVisible();

    const counter = await staff.newPage();
    await counter.goto("/balcao");
    await counter.getByLabel("Usuário", { exact: true }).fill("operator");
    await counter.getByLabel("Senha", { exact: true }).fill(process.env.MESA_DEMO_OPERATOR_PASSWORD ?? "DemoOperatorChangeMe");
    await counter.getByRole("button", { name: "Entrar", exact: true }).click();
    const ticket = counter.getByRole("region", { name: "Fila de pedidos" }).getByRole("article").filter({ hasText: name });
    await expect(ticket).toContainText(address);
    await ticket.getByRole("button", { name: "Iniciar preparo", exact: true }).click();
    await ticket.getByRole("button", { name: "Marcar como pronto", exact: true }).click();
    await expect(ticket.getByRole("button", { name: "Concluir retirada", exact: true })).toHaveCount(0);
    await ticket.getByRole("button", { name: "Saiu para entrega", exact: true }).click();
    await expect(tracked.locator("[aria-current=step]")).toHaveText("Saiu para entrega");
    await ticket.getByRole("button", { name: "Concluir entrega", exact: true }).click();
    await expect(ticket).toHaveCount(0);
    await expect(tracked.locator("[aria-current=step]")).toHaveText("Concluído");
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);

    await counter.getByText("Criar pedido", { exact: true }).click();
    await counter.getByLabel("Como você prefere receber?").selectOption({ label: "Entrega no endereço" });
    await counter.getByRole("button", { name: "Adicionar " + product.name, exact: true }).click();
    const counterName = "Entrega do balcão " + Date.now();
    await counter.getByLabel("Nome para identificação").fill(counterName);
    await counter.getByLabel("Endereço de entrega").fill(address + " - Balcão");
    await counter.getByRole("button", { name: "Confirmar entrega", exact: true }).click();
    const counterTicket = counter.getByRole("region", { name: "Fila de pedidos" }).getByRole("article").filter({ hasText: counterName });
    await expect(counterTicket).toContainText("Entrega · Balcão");
    await expect(counterTicket).toContainText(address + " - Balcão");
  } finally {
    await customer.close();
    await staff.close();
  }
});

test("desabilitar entrega bloqueia novos pedidos e preserva a entrega em andamento", async ({ browser, request, baseURL }) => {
  const { product, headers } = await prepare(request, { pickup: true, delivery: true });
  const customer = await browser.newContext({ baseURL });

  try {
    const page = await customer.newPage();
    await page.goto("/cliente");
    const cart = page.getByRole("complementary", { name: "Seu pedido" });
    await cart.getByLabel("Como você prefere receber?").selectOption({ label: "Entrega no endereço" });
    await page.getByRole("button", { name: "Adicionar " + product.name, exact: true }).click();
    const name = "Entrega preservada " + Date.now();
    await cart.getByLabel("Nome para identificação").fill(name);
    await cart.getByLabel("Endereço de entrega").fill("Rua Preservada, 1");
    await cart.getByRole("button", { name: "Confirmar entrega", exact: true }).click();
    const tracked = page.getByRole("region", { name: "Meus pedidos" }).getByRole("article").filter({ hasText: name });
    await expect(tracked).toContainText("Entregar em: Rua Preservada, 1");

    const configuration = await (await request.get("/api/configuration/v1/configuration")).json();
    expect((await request.put("/api/configuration/v1/configuration", { headers, data: {
      expected_revision: configuration.revision, features: { ...configuration.features, pickup: true, delivery: false },
    } })).status()).toBe(200);

    await expect(cart.getByLabel("Como você prefere receber?")).toHaveCount(0);
    await expect(cart.getByRole("button", { name: "Confirmar retirada", exact: true })).toBeVisible();
    await expect(tracked).toContainText("Entregar em: Rua Preservada, 1");
    await expect(tracked.locator("[aria-current=step]")).toHaveText("Recebido");
  } finally {
    await customer.close();
  }
});

test("envio de entrega pendente mantém modalidade, endereço e taxa após desabilitar entrega", async ({ page, request }) => {
  const { product, headers } = await prepare(request, { pickup: true, delivery: true });
  const money = new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" });
  await page.goto("/cliente");
  const cart = page.getByRole("complementary", { name: "Seu pedido" });
  await cart.getByLabel("Como você prefere receber?").selectOption({ label: "Entrega no endereço" });
  await page.getByRole("button", { name: "Adicionar " + product.name, exact: true }).click();
  const name = "Entrega pendente " + Date.now();
  await cart.getByLabel("Nome para identificação").fill(name);
  await cart.getByLabel("Endereço de entrega").fill("Rua Pendente, 7");

  let attempts = 0;
  await page.route("**/api/orders/v1/orders", async (route) => {
    attempts += 1;
    if (attempts === 1) {
      await route.fetch();
      await route.abort("failed");
    } else await route.continue();
  });
  await cart.getByRole("button", { name: "Confirmar entrega", exact: true }).click();
  const retry = cart.getByRole("button", { name: "Tentar confirmar o mesmo envio" });
  await expect(retry).toBeEnabled();

  const configuration = await (await request.get("/api/configuration/v1/configuration")).json();
  expect((await request.put("/api/configuration/v1/configuration", { headers, data: {
    expected_revision: configuration.revision, features: { ...configuration.features, pickup: true, delivery: false },
  } })).status()).toBe(200);
  await page.reload();

  await expect(cart.locator(".cart-header")).toContainText("Entrega");
  await expect(cart.getByLabel("Endereço de entrega")).toHaveValue("Rua Pendente, 7");
  await expect(cart.getByText("Taxa de entrega")).toBeVisible();
  await expect(cart.locator(".grand-total")).toContainText(money.format((product.price_cents + 500) / 100));
  await expect(cart.getByLabel("Como você prefere receber?")).toHaveCount(0);

  await retry.click();
  const tracked = page.getByRole("region", { name: "Meus pedidos" }).getByRole("article").filter({ hasText: name });
  await expect(tracked).toContainText("Entregar em: Rua Pendente, 7");
  await expect(tracked).toContainText(money.format((product.price_cents + 500) / 100));
  expect(attempts).toBe(2);
});
