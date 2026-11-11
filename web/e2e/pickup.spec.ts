import { expect, test } from "@playwright/test";
import { catalogPath, ordersPath, prepare } from "./helpers";

test("cliente envia retirada e acompanha os estados operados em outra sessão", async ({ browser, request, baseURL }) => {
  const { product } = await prepare(request);
  const customer = await browser.newContext({ baseURL, viewport: { width: 390, height: 844 } });
  const staff = await browser.newContext({ baseURL });
  try {
    const page = await customer.newPage();
    await page.goto("/cliente");
    await page.getByRole("searchbox", { name: "Buscar produtos" }).fill(product.name);
    await page.getByRole("button", { name: "Adicionar " + product.name, exact: true }).click();
    await page.getByRole("button", { name: "Aumentar " + product.name, exact: true }).click();
    const name = "Jornada retirada " + Date.now();
    await page.getByLabel("Nome para identificação").fill(name);
    await page.reload();
    const cart = page.getByRole("complementary", { name: "Seu pedido" });
    await expect(cart.getByLabel("Nome para identificação")).toHaveValue(name);
    await expect(cart.getByLabel("Quantidade de " + product.name)).toHaveText("2");
    const response = page.waitForResponse((response) => response.url().endsWith(ordersPath + "/orders") && response.request().method() === "POST");
    await page.getByRole("button", { name: "Confirmar retirada", exact: true }).click();
    expect([201, 202]).toContain((await response).status());
    const feed = page.getByRole("region", { name: "Meus pedidos" });
    const tracked = feed.getByRole("article").filter({ hasText: name });
    await expect(tracked).toBeVisible();
    await expect(cart.getByText("Seu carrinho está vazio")).toBeVisible();

    const counter = await staff.newPage();
    await counter.goto("/balcao");
    await counter.getByLabel("Usuário", { exact: true }).fill("operator");
    await counter.getByLabel("Senha", { exact: true }).fill(process.env.MESA_DEMO_OPERATOR_PASSWORD ?? "DemoOperatorChangeMe");
    await counter.getByRole("button", { name: "Entrar", exact: true }).click();
    const queue = counter.getByRole("region", { name: "Fila de pedidos" });
    const ticket = queue.getByRole("article").filter({ hasText: name });
    await ticket.getByRole("button", { name: "Iniciar preparo", exact: true }).click();
    await expect(tracked.locator("[aria-current=step]")).toHaveText("Em preparo");
    await ticket.getByRole("button", { name: "Marcar como pronto", exact: true }).click();
    await expect(tracked.locator("[aria-current=step]")).toHaveText("Pronto");
    await ticket.getByRole("button", { name: "Concluir retirada", exact: true }).click();
    await expect(ticket).toHaveCount(0);
    await expect(tracked.locator("[aria-current=step]")).toHaveText("Concluído");
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);

    await counter.getByText("Criar pedido", { exact: true }).click();
    await counter.getByRole("button", { name: "Adicionar " + product.name, exact: true }).click();
    const counterName = "Pedido do balcão " + Date.now();
    await counter.getByLabel("Nome para identificação").fill(counterName);
    await counter.getByRole("button", { name: "Confirmar retirada", exact: true }).click();
    const counterTicket = queue.getByRole("article").filter({ hasText: counterName });
    await expect(counterTicket).toBeVisible();
    await expect(counterTicket).toContainText("Balcão");
    await expect(feed.getByRole("article").filter({ hasText: counterName })).toHaveCount(0);
  } finally {
    await customer.close();
    await staff.close();
  }
});

test("resposta perdida preserva o carrinho e repete a mesma criação após recarga", async ({ page, request }) => {
  const { product, headers } = await prepare(request);
  await page.goto("/cliente");
  await page.getByRole("button", { name: "Adicionar " + product.name, exact: true }).click();
  await page.getByLabel("Nome para identificação").fill("Reenvio " + Date.now());
  const sent: { key: string | undefined; payload: unknown }[] = [];
  await page.route("**/api/orders/v1/orders", async (route) => {
    sent.push({ key: route.request().headers()["idempotency-key"], payload: route.request().postDataJSON() });
    if (sent.length === 1) {
      await route.fetch();
      await route.abort("failed");
    } else await route.continue();
  });
  await page.getByRole("button", { name: "Confirmar retirada", exact: true }).click();
  await expect(page.getByRole("button", { name: "Tentar confirmar o mesmo envio" })).toBeEnabled();
  await page.reload();
  await page.getByRole("button", { name: "Tentar confirmar o mesmo envio" }).click();
  const feed = page.getByRole("region", { name: "Meus pedidos" });
  await expect(feed.getByRole("article")).toHaveCount(1);
  await expect(page.getByRole("complementary", { name: "Seu pedido" }).getByText("Seu carrinho está vazio")).toBeVisible();
  expect(sent).toHaveLength(2);
  expect(sent[0].key).toBeTruthy();
  expect(sent[1]).toEqual(sent[0]);

  await page.getByRole("button", { name: "Adicionar " + product.name, exact: true }).click();
  await page.getByLabel("Nome para identificação").fill("Revisão de preço");
  const catalog = await (await request.get(catalogPath + "/admin/products")).json();
  expect((await request.patch(catalogPath + "/products/" + product.id, { headers, data: {
    expected_revision: catalog.revision, price_cents: product.price_cents + 50,
  } })).status()).toBe(200);
  await page.getByRole("button", { name: "Confirmar retirada", exact: true }).click();
  await expect(page.getByRole("button", { name: "Revisar preços e disponibilidade" })).toBeVisible();
  await expect(feed.getByRole("article")).toHaveCount(1);
  await page.getByRole("button", { name: "Revisar preços e disponibilidade" }).click();
  await expect(page.getByRole("button", { name: "Confirmar retirada", exact: true })).toBeEnabled();
});

test("resposta de uma tela anterior não sobrescreve o carrinho atual", async ({ page, request }) => {
  const { product } = await prepare(request);
  let release!: () => void;
  const delayed = new Promise<void>((resolve) => { release = resolve; });
  let holding = true;
  let waiting = 0;
  await page.route("**/api/configuration/v1/configuration", async (route) => {
    if (!holding) return route.continue();
    const response = await route.fetch();
    waiting += 1;
    await delayed;
    await route.fulfill({ response });
  });
  await page.goto("/cliente");
  await expect.poll(() => waiting).toBeGreaterThanOrEqual(2);
  await page.getByRole("link", { name: "Administração", exact: true }).click();
  holding = false;
  await page.getByRole("link", { name: "Cardápio", exact: true }).click();
  await page.getByRole("button", { name: "Adicionar " + product.name, exact: true }).click();
  release();
  await page.waitForLoadState("networkidle");
  await page.reload();
  const cart = page.getByRole("complementary", { name: "Seu pedido" });
  await expect(cart.getByLabel("Quantidade de " + product.name)).toHaveText("1");
});
