import { performance } from "node:perf_hooks";
import { writeFile } from "node:fs/promises";
import { arch, cpus, platform, totalmem } from "node:os";
import { expect, test, type Browser, type Page, type TestInfo } from "@playwright/test";
import { catalogPath, configurationPath, ordersPath, prepare } from "./helpers";

const money = new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" });
const passwords = {
  admin: process.env.MESA_DEMO_ADMIN_PASSWORD ?? "DemoAdminChangeMe",
  operator: process.env.MESA_DEMO_OPERATOR_PASSWORD ?? "DemoOperatorChangeMe",
};

type Measurement = {
  event: string; source: string; target: string; elapsed_ms: number; limit_ms: number; passed: boolean;
};

async function observed(measurements: Measurement[], event: string, source: string, target: string,
  start: number, check: () => Promise<void>) {
  let reached = false;
  let elapsed = 0;
  try {
    await check();
    reached = true;
  } finally {
    elapsed = performance.now() - start;
    measurements.push({ event, source, target, elapsed_ms: Math.round(elapsed),
      limit_ms: 5000, passed: reached && elapsed <= 5000 });
  }
  expect(elapsed, event + " → " + target).toBeLessThanOrEqual(5000);
}

async function evidence(info: TestInfo, measurements: Measurement[], browserVersion: string) {
  const path = info.outputPath("propagation.json");
  await writeFile(path, JSON.stringify({
    observed_at: new Date().toISOString(), base_url: info.project.use.baseURL,
    browser: browserVersion, viewport: info.project.use.viewport,
    environment: { cpu: cpus()[0]?.model, logical_cores: cpus().length,
      memory_bytes: totalmem(), platform: platform(), architecture: arch() },
    measurements,
  }, null, 2));
  await info.attach("propagation.json", { contentType: "application/json", path });
}

async function open(browser: Browser, baseURL: string | undefined, path: string, user?: keyof typeof passwords) {
  const context = await browser.newContext({ baseURL,
    viewport: path === "/tv" ? { width: 1920, height: 1080 } : undefined });
  const page = await context.newPage();
  await page.goto(path);
  if (user) {
    await page.getByLabel("Usuário", { exact: true }).fill(user);
    await page.getByLabel("Senha", { exact: true }).fill(passwords[user]);
    await page.getByRole("button", { name: "Entrar", exact: true }).click();
  }
  return { context, page };
}

function metric(page: Page, name: string) {
  return page.getByLabel(name, { exact: true }).locator("strong");
}

test("criação e transição propagam entre Cliente, Balcão, Administração e TV", async ({ browser, request, baseURL }, info) => {
  test.setTimeout(90000);
  const { product } = await prepare(request, { pickup: true, tv: true });
  const client = await open(browser, baseURL, "/cliente");
  const counter = await open(browser, baseURL, "/balcao", "operator");
  const admin = await open(browser, baseURL, "/admin", "admin");
  const tv = await open(browser, baseURL, "/tv");
  const measurements: Measurement[] = [];
  const baseline = await (await request.get(ordersPath + "/summary")).json();

  try {
    await expect(tv.page.getByRole("region", { name: "Em preparo", exact: true })).toBeVisible();
    for (let round = 0; round < 3; round += 1) {
      const name = "Propagação " + Date.now() + " " + round;
      await client.page.getByRole("button", { name: "Adicionar " + product.name, exact: true }).click();
      await client.page.getByLabel("Nome para identificação", { exact: true }).fill(name);
      const cart = client.page.getByRole("complementary", { name: "Seu pedido" });
      const start = performance.now();
      await cart.getByRole("button", { name: "Confirmar retirada", exact: true }).click();
      const ticket = counter.page.getByRole("region", { name: "Fila de pedidos" })
        .getByRole("article").filter({ hasText: name });
      await observed(measurements, "creation", "Cliente", "Balcão", start,
        () => expect(ticket).toBeVisible({ timeout: 5000 }));
      const number = Number((await ticket.getByRole("heading").textContent())!.match(/#(\d+)/)![1]);
      await expect(metric(admin.page, "Pedidos em andamento")).toHaveText(String(baseline.active_orders + 1));
      expect(await tv.page.getByText(String(number), { exact: true }).count()).toBe(0);
      const transition = performance.now();
      await ticket.getByRole("button", { name: "Iniciar preparo", exact: true }).click();
      await observed(measurements, "transition", "Balcão", "TV", transition,
        () => expect(tv.page.getByRole("region", { name: "Em preparo", exact: true })
          .getByText(String(number), { exact: true })).toBeVisible({ timeout: 5000 }));
      await ticket.getByRole("button", { name: "Marcar como pronto", exact: true }).click();
      await expect(tv.page.getByRole("region", { name: "Prontos", exact: true })
        .getByText(String(number), { exact: true })).toBeVisible();
      await ticket.getByRole("button", { name: "Concluir retirada", exact: true }).click();
      await expect(tv.page.getByText(String(number), { exact: true })).toHaveCount(0);
      await expect(metric(admin.page, "Valor dos pedidos concluídos")).toHaveText(
        money.format((baseline.completed_order_value_cents + product.price_cents * (round + 1)) / 100),
      );
      await expect(cart.getByText("Seu carrinho está vazio")).toBeVisible();
    }
  } finally {
    await evidence(info, measurements, browser.version());
    await Promise.all([client, counter, admin, tv].map(({ context }) => context.close()));
  }
});

test("configuração compartilhada preserva rascunho administrativo e propaga em até cinco segundos", async ({ browser, request, baseURL }, info) => {
  test.setTimeout(60000);
  const { product } = await prepare(request, { pickup: true, delivery: false, tv: true });
  const client = await open(browser, baseURL, "/cliente");
  const admin = await open(browser, baseURL, "/admin", "admin");
  const tv = await open(browser, baseURL, "/tv");
  const measurements: Measurement[] = [];
  let configurationRequests = 0;
  client.page.on("request", (entry) => {
    if (new URL(entry.url()).pathname === configurationPath) configurationRequests += 1;
  });

  try {
    await expect(tv.page.getByRole("region", { name: "Prontos", exact: true })).toBeVisible();
    await admin.page.getByRole("checkbox", { name: "Entrega", exact: true }).check();
    expect((await (await request.get(configurationPath)).json()).features.delivery).toBe(false);

    for (const enabled of [false, true, false]) {
      await client.page.getByRole("button", { name: "Adicionar " + product.name, exact: true }).click();
      await client.page.getByLabel("Nome para identificação", { exact: true }).fill("Carrinho reiniciado");
      const current = await (await request.get(configurationPath)).json();
      const session = await (await request.get("/api/configuration/v1/sessions/current")).json();
      const start = performance.now();
      expect((await request.put(configurationPath, { headers: {
        "X-CSRF-Token": session.csrf_token,
      }, data: { expected_revision: current.revision, features: { ...current.features, tv: enabled } } })).status()).toBe(200);
      const navigation = client.page.getByRole("navigation", { name: "Áreas do Mesa Fácil" })
        .getByRole("link", { name: "Painel de TV", exact: true });
      const results = await Promise.allSettled([
        observed(measurements, "configuration", "Administração", "TV", start, () => enabled
          ? expect(tv.page.getByRole("region", { name: "Prontos", exact: true })).toBeVisible({ timeout: 5000 })
          : expect(tv.page.getByRole("alert")).toContainText("O painel de TV está desabilitado.", { timeout: 5000 })),
        observed(measurements, "configuration", "Administração", "Carrinho do Cliente", start,
          () => expect(client.page.getByRole("complementary", { name: "Seu pedido" })
            .getByText("Seu carrinho está vazio")).toBeVisible({ timeout: 5000 })),
        observed(measurements, "configuration", "Administração", "Navegação do Cliente", start, () => enabled
          ? expect(navigation).toBeVisible({ timeout: 5000 })
          : expect(navigation).toHaveCount(0, { timeout: 5000 })),
      ]);
      for (const result of results) {
        if (result.status === "rejected") throw result.reason;
      }
    }
    await expect(client.page.getByRole("complementary", { name: "Seu pedido" })
      .getByText("Seu carrinho está vazio")).toBeVisible();
    await expect(client.page.getByRole("navigation", { name: "Áreas do Mesa Fácil" })
      .getByRole("link", { name: "Painel de TV", exact: true })).toHaveCount(0);
    await expect(admin.page.getByRole("checkbox", { name: "Entrega", exact: true })).toBeChecked();
    await expect(admin.page.getByRole("button", { name: "Salvar configuração", exact: true })).toBeDisabled();
    await admin.page.getByRole("button", { name: "Atualizar versão salva", exact: true }).click();
    await expect(admin.page.getByRole("button", { name: "Salvar configuração", exact: true })).toBeEnabled();
    expect(configurationRequests).toBeLessThanOrEqual(5);

    let release!: () => void;
    const held = new Promise<void>((resolve) => { release = resolve; });
    let waiting = false;
    await admin.page.route("**/api/configuration/v1/configuration", async (route) => {
      if (route.request().method() !== "GET") return route.continue();
      const response = await route.fetch();
      waiting = true;
      await held;
      await route.fulfill({ response });
    });
    await expect.poll(() => waiting).toBe(true);
    await admin.page.getByRole("checkbox", { name: "Painel de TV", exact: true }).check();
    await admin.page.getByRole("button", { name: "Salvar configuração", exact: true }).click();
    const navigation = admin.page.getByRole("navigation", { name: "Áreas do Mesa Fácil" });
    await expect(navigation.getByRole("link", { name: "Painel de TV", exact: true })).toBeVisible();
    const response = admin.page.waitForResponse((entry) => new URL(entry.url()).pathname === configurationPath
      && entry.request().method() === "GET");
    release();
    await response;
    await admin.page.evaluate(() => new Promise<void>((resolve) => {
      requestAnimationFrame(() => requestAnimationFrame(() => resolve()));
    }));
    await expect(navigation.getByRole("link", { name: "Painel de TV", exact: true })).toBeVisible();
  } finally {
    await evidence(info, measurements, browser.version());
    await Promise.all([client, admin, tv].map(({ context }) => context.close()));
  }
});

test("TV sinaliza excedentes e falhas, não sobrepõe consultas e limpa seu polling", async ({ browser, request, baseURL }, info) => {
  await prepare(request, { tv: true });
  const tv = await browser.newContext({ baseURL, viewport: { width: 1920, height: 1080 } });
  const page = await tv.newPage();
  await page.clock.install();
  let calls = 0;
  let release!: () => void;
  const held = new Promise<void>((resolve) => { release = resolve; });
  await page.route("**/api/orders/v1/tv?*", async (route) => {
    calls += 1;
    if (calls === 2) {
      await held;
      await route.fulfill({ status: 503, json: { error: {
        code: "configuration_unavailable", message: "Falha de atualização.",
      } } });
    } else await route.fulfill({ json: {
      preparing: { items: calls === 1 ? Array.from({ length: 9 }, (_, index) => ({
        number: 100 + index, fulfillment: "pickup", table_number: null,
      })) : [], total: calls === 1 ? 14 : 0, next_cursor: calls === 1 ? "cursor" : null },
      ready: { items: calls === 1 ? [{ number: 200, fulfillment: "table", table_number: 3 }] : [],
        total: calls === 1 ? 1 : 0, next_cursor: null },
    } });
  });

  try {
    await page.goto("/balcao");
    await page.getByRole("link", { name: "Painel de TV", exact: true }).click();
    await expect(page.getByText("+5 em preparo além dos exibidos", { exact: true })).toBeVisible();
    await expect(page.getByRole("region", { name: "Prontos", exact: true }).getByText("1 pedido", { exact: true }))
      .toBeVisible();
    await expect(page.getByRole("link", { name: "Voltar ao balcão", exact: true })).toHaveCount(0);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth
      && document.documentElement.scrollHeight <= window.innerHeight)).toBe(true);
    const screenshot = info.outputPath("tv-1920x1080.png");
    await page.screenshot({ path: screenshot });
    await info.attach("tv-1920x1080.png", { path: screenshot, contentType: "image/png" });
    await page.clock.runFor(3100);
    await expect.poll(() => calls).toBe(2);
    await page.clock.runFor(6000);
    expect(calls).toBe(2);
    release();
    await expect(page.getByRole("alert")).toContainText("Última sincronização:");
    await expect(page.getByRole("alert")).not.toContainText("Os dados exibidos podem estar desatualizados");
    await expect(page.getByRole("region", { name: "Em preparo", exact: true })).toHaveCount(0);
    await page.clock.runFor(3100);
    await expect(page.getByRole("region", { name: "Em preparo", exact: true })).toBeVisible();
    await expect(page.getByRole("alert")).toHaveCount(0);
    const before = calls;
    await page.goBack();
    await expect(page.getByRole("heading", { name: "Acesse o Balcão", exact: true })).toBeVisible();
    await page.clock.runFor(9000);
    expect(calls).toBe(before);
    expect(await page.evaluate(() => document.body.dataset.role)).toBeUndefined();
  } finally {
    release();
    await tv.close();
  }
});

test("resumo degrada por serviço e o cardápio recebe novos preços sem recarregar", async ({ browser, request, baseURL }) => {
  const { product, headers } = await prepare(request, { pickup: true });
  const admin = await open(browser, baseURL, "/admin", "admin");
  const client = await open(browser, baseURL, "/cliente");

  try {
    await expect(metric(admin.page, "Produtos disponíveis")).not.toHaveText("—");
    await admin.page.route("**/api/catalog/v1/summary", (route) => route.fulfill({
      status: 503, json: { error: { code: "unavailable", message: "Catálogo indisponível." } },
    }));
    await expect(admin.page.getByRole("alert")).toContainText("Catálogo indisponível.");
    await expect(metric(admin.page, "Pedidos em andamento")).not.toHaveText("—");
    const catalog = await (await request.get(catalogPath + "/admin/products")).json();
    expect((await request.patch(catalogPath + "/products/" + product.id, { headers, data: {
      expected_revision: catalog.revision, price_cents: product.price_cents + 125,
    } })).status()).toBe(200);
    const card = client.page.getByRole("article").filter({
      has: client.page.getByRole("heading", { name: product.name, exact: true }),
    });
    await expect(card.locator(".price")).toHaveText(money.format((product.price_cents + 125) / 100), { timeout: 5000 });
    await admin.page.unroute("**/api/catalog/v1/summary");
    await expect(admin.page.getByRole("alert")).toHaveCount(0);
    await admin.page.route("**/api/orders/v1/summary", (route) => route.fulfill({
      status: 401, json: { error: { code: "invalid_session", message: "Entre novamente." } },
    }));
    await expect(metric(admin.page, "Pedidos em andamento")).toHaveText("—");
    await expect(metric(admin.page, "Valor dos pedidos concluídos")).toHaveText("—");
    await expect(admin.page.getByRole("alert").filter({ hasText: "Entre novamente." }))
      .not.toContainText("Os dados exibidos podem estar desatualizados");

    await client.page.route("**/api/catalog/v1/products?*", (route) => route.fulfill({
      status: 503, json: { error: { code: "unavailable", message: "Cardápio indisponível." } },
    }));
    await client.page.reload();
    const unavailable = client.page.getByRole("alert").filter({ hasText: "Cardápio indisponível." });
    await expect(unavailable).toBeVisible();
    await expect(unavailable).not.toContainText("Os dados exibidos podem estar desatualizados");
  } finally {
    await Promise.all([admin.context.close(), client.context.close()]);
  }
});
