import { expect, test, type Browser, type Page } from "@playwright/test";
import { configurationPath, prepare } from "./helpers";

const money = new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" });
const operatorPassword = process.env.MESA_DEMO_OPERATOR_PASSWORD ?? "DemoOperatorChangeMe";
const allTableFeatures = { pickup: true, tables: true, tablet: true };

async function signIn(page: Page) {
  await page.getByLabel("Usuário", { exact: true }).fill("operator");
  await page.getByLabel("Senha", { exact: true }).fill(operatorPassword);
  await page.getByRole("button", { name: "Entrar", exact: true }).click();
}

async function orderAtTable(page: Page, productName: string, table: string, name: string) {
  await page.goto("/cliente");
  const cart = page.getByRole("complementary", { name: "Seu pedido" });
  await cart.getByLabel("Como você prefere receber?").selectOption({ label: "Atendimento na mesa" });
  await cart.getByLabel("Mesa", { exact: true }).selectOption({ label: table });
  await page.getByRole("button", { name: "Adicionar " + productName, exact: true }).click();
  await cart.getByLabel("Nome para identificação").fill(name);
  await cart.getByRole("button", { name: "Confirmar pedido na mesa", exact: true }).click();
  await expect(cart.getByText("Seu carrinho está vazio")).toBeVisible();
}

/** An operator binds a fresh browser to a table; the operator session ends there. */
async function linkTablet(browser: Browser, baseURL: string | undefined, table: string) {
  const context = await browser.newContext({ baseURL, viewport: { width: 1180, height: 820 } });
  const page = await context.newPage();
  await page.goto("/comanda/configurar");
  await signIn(page);
  // The select sits inside its label, so its accessible name also carries the selected option.
  await page.getByRole("combobox", { name: "Mesa" }).selectOption({ label: table });
  await page.getByRole("button", { name: "Vincular tablet à mesa", exact: true }).click();
  await expect(page.getByLabel("Mesa deste tablet")).toHaveText(table);
  return { context, page };
}

async function sendRound(page: Page, productName: string) {
  const banner = page.locator(".tablet-success strong");
  const previous = await banner.count() ? await banner.textContent() : null;
  await page.getByRole("button", { name: "Adicionar " + productName, exact: true }).click();
  await page.getByRole("button", { name: "Enviar para a cozinha", exact: true }).click();
  if (previous) await expect(banner).not.toHaveText(previous);
  await expect(banner).toContainText("enviado");
  return Number((await banner.textContent())!.match(/#(\d+)/)![1]);
}

test("cliente escolhe a mesa e o Balcão conclui o atendimento", async ({ browser, request, baseURL }) => {
  const { product } = await prepare(request, allTableFeatures);
  const customer = await browser.newContext({ baseURL, viewport: { width: 390, height: 844 } });
  const staff = await browser.newContext({ baseURL });

  try {
    const page = await customer.newPage();
    const name = "Mesa do cliente " + Date.now();
    await orderAtTable(page, product.name, "Mesa 03", name);
    const tracked = page.getByRole("region", { name: "Meus pedidos" }).getByRole("article").filter({ hasText: name });
    await expect(tracked).toContainText("Mesa 03");

    const counter = await staff.newPage();
    await counter.goto("/balcao");
    await signIn(counter);
    const ticket = counter.getByRole("region", { name: "Fila de pedidos" }).getByRole("article").filter({ hasText: name });
    await expect(ticket).toContainText("Mesa 03");
    await ticket.getByRole("button", { name: "Iniciar preparo", exact: true }).click();
    await ticket.getByRole("button", { name: "Marcar como pronto", exact: true }).click();
    await ticket.getByRole("button", { name: "Concluir atendimento", exact: true }).click();
    await expect(ticket).toHaveCount(0);
    await expect(tracked.locator("[aria-current=step]")).toHaveText("Concluído");
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  } finally {
    await customer.close();
    await staff.close();
  }
});

test("tablet envia duas rodadas e “Já pedi” mostra todo o histórico da mesa", async ({ browser, request, baseURL }) => {
  const { product } = await prepare(request, allTableFeatures);
  const customer = await browser.newContext({ baseURL });
  const staff = await browser.newContext({ baseURL });
  const tablet = await linkTablet(browser, baseURL, "Mesa 05");

  try {
    await orderAtTable(await customer.newPage(), product.name, "Mesa 05", "Cliente da mesa 5 " + Date.now());

    const first = await sendRound(tablet.page, product.name);
    const second = await sendRound(tablet.page, product.name);
    expect(second).not.toBe(first);
    await expect(tablet.page.getByLabel("Mesa deste tablet")).toHaveText("Mesa 05");

    const counter = await staff.newPage();
    await counter.goto("/balcao");
    await signIn(counter);
    const ticket = counter.getByRole("region", { name: "Fila de pedidos" }).getByRole("article")
      .filter({ has: counter.getByRole("heading", { name: "Pedido #" + first, exact: true }) });
    await expect(ticket).toContainText("Mesa 05 · Mesa · Comanda");
    for (const action of ["Iniciar preparo", "Marcar como pronto", "Concluir atendimento"]) {
      await ticket.getByRole("button", { name: action, exact: true }).click();
    }
    await expect(ticket).toHaveCount(0);

    await tablet.page.getByRole("button", { name: "Já pedi", exact: true }).click();
    const history = tablet.page.getByRole("region", { name: "Já pedi" });
    await expect(history.getByText("3 pedidos")).toBeVisible();
    await expect(history.getByText("Total histórico: " + money.format(product.price_cents * 3 / 100))).toBeVisible();
    const finished = history.getByRole("article").filter({
      has: tablet.page.getByRole("heading", { name: "Pedido #" + first, exact: true }),
    });
    await expect(finished.locator("[aria-current=step]")).toHaveText("Concluído");
    await expect(history.getByText("Não representa conta aberta.", { exact: false })).toBeVisible();
    await expect(history.getByText("Cliente da mesa 5", { exact: false })).toHaveCount(0);
  } finally {
    await customer.close();
    await staff.close();
    await tablet.context.close();
  }
});

test("outra mesa começa vazia e não vê o histórico da mesa A", async ({ browser, request, baseURL }) => {
  const { product } = await prepare(request, allTableFeatures);
  const tabletA = await linkTablet(browser, baseURL, "Mesa 08");
  const tabletB = await linkTablet(browser, baseURL, "Mesa 09");

  try {
    await sendRound(tabletA.page, product.name);
    await tabletB.page.getByRole("button", { name: "Já pedi", exact: true }).click();
    const history = tabletB.page.getByRole("region", { name: "Já pedi" });
    await expect(history.getByText("A mesa ainda não fez pedidos.")).toBeVisible();
    await expect(history.getByText("Total histórico: " + money.format(0))).toBeVisible();
    await expect(history.getByText("0 pedidos")).toBeVisible();
  } finally {
    await tabletA.context.close();
    await tabletB.context.close();
  }
});

test("desabilitar Comanda e Mesas bloqueia novas rodadas e preserva o histórico", async ({ browser, request, baseURL }) => {
  const { product, headers } = await prepare(request, allTableFeatures);
  const tablet = await linkTablet(browser, baseURL, "Mesa 11");
  const staff = await browser.newContext({ baseURL });

  async function setFeatures(features: Record<string, boolean>) {
    const configuration = await (await request.get(configurationPath)).json();
    expect((await request.put(configurationPath, { headers, data: {
      expected_revision: configuration.revision, features: { ...configuration.features, ...features },
    } })).status()).toBe(200);
  }

  try {
    const round = await sendRound(tablet.page, product.name);

    await setFeatures({ tablet: false });
    await expect(tablet.page.getByText("A Comanda digital está desabilitada para novos pedidos.", { exact: false })).toBeVisible();
    await expect(tablet.page.getByRole("button", { name: "Adicionar " + product.name, exact: true })).toBeDisabled();

    await setFeatures({ tables: false });
    await tablet.page.getByRole("button", { name: "Já pedi", exact: true }).click();
    const history = tablet.page.getByRole("region", { name: "Já pedi" });
    const kept = history.getByRole("article").filter({
      has: tablet.page.getByRole("heading", { name: "Pedido #" + round, exact: true }),
    });
    await expect(kept).toBeVisible();

    const counter = await staff.newPage();
    await counter.goto("/balcao");
    await signIn(counter);
    const ticket = counter.getByRole("region", { name: "Fila de pedidos" }).getByRole("article")
      .filter({ has: counter.getByRole("heading", { name: "Pedido #" + round, exact: true }) });
    for (const action of ["Iniciar preparo", "Marcar como pronto", "Concluir atendimento"]) {
      await ticket.getByRole("button", { name: action, exact: true }).click();
    }
    await expect(kept.locator("[aria-current=step]")).toHaveText("Concluído");
  } finally {
    await setFeatures(allTableFeatures);
    await tablet.context.close();
    await staff.close();
  }
});

test("a Comanda só abre depois que a sessão do operador é encerrada", async ({ browser, request, baseURL }) => {
  await prepare(request, allTableFeatures);
  const context = await browser.newContext({ baseURL });

  try {
    const page = await context.newPage();
    let failures = 1;
    await page.route("**/api/configuration/v1/sessions/current", async (route) => {
      if (route.request().method() === "DELETE" && failures-- > 0) {
        await route.fulfill({ status: 503, json: { error: { code: "configuration_unavailable", message: "Indisponível." } } });
      } else await route.continue();
    });

    await page.goto("/comanda/configurar");
    await signIn(page);
    await page.getByRole("combobox", { name: "Mesa" }).selectOption({ label: "Mesa 12" });
    await page.getByRole("button", { name: "Vincular tablet à mesa", exact: true }).click();
    await expect(page.getByRole("alert")).toContainText("sessão do operador continua ativa");
    await expect(page).toHaveURL(/\/comanda\/configurar$/);
    expect((await page.request.get("/api/orders/v1/queue")).status()).toBe(200);

    await page.getByRole("button", { name: "Encerrar sessão do operador e abrir a Comanda", exact: true }).click();
    await expect(page.getByLabel("Mesa deste tablet")).toHaveText("Mesa 12");
    expect((await page.request.get("/api/orders/v1/queue")).status()).toBe(401);
  } finally {
    await context.close();
  }
});

test("cookie perdido mantém a referência da rodada pendente antes de novo vínculo", async ({ browser, request, baseURL }) => {
  const { product } = await prepare(request, allTableFeatures);
  const tablet = await linkTablet(browser, baseURL, "Mesa 10");

  try {
    // The round is accepted by the server, but the response never reaches the tablet.
    await tablet.page.route("**/api/orders/v1/orders", async (route) => {
      await route.fetch();
      await route.abort("failed");
    });
    await tablet.page.getByRole("button", { name: "Adicionar " + product.name, exact: true }).click();
    await tablet.page.getByRole("button", { name: "Enviar para a cozinha", exact: true }).click();
    await expect(tablet.page.getByRole("button", { name: "Tentar enviar a mesma rodada", exact: true })).toBeVisible();
    const reference = (await tablet.page.locator(".cart code").textContent())!;

    await tablet.context.clearCookies({ name: "mesa_table" });
    await tablet.page.reload();
    await expect(tablet.page.getByText("Este tablet não está vinculado a uma mesa.")).toBeVisible();
    await expect(tablet.page.getByText(reference, { exact: true })).toBeVisible();

    // While the current context is still being checked, linking must stay blocked.
    let release!: () => void;
    const held = new Promise<void>((resolve) => { release = resolve; });
    await tablet.page.route("**/api/tables/v1/table-contexts/current", async (route) => {
      await held;
      await route.continue();
    });
    await tablet.page.goto("/comanda/configurar");
    await signIn(tablet.page);
    await tablet.page.getByRole("combobox", { name: "Mesa" }).selectOption({ label: "Mesa 10" });
    await expect(tablet.page.getByRole("button", { name: "Verificando o tablet…", exact: true })).toBeDisabled();
    release();
    await expect(tablet.page.getByText(reference, { exact: true })).toBeVisible();
    const linkButton = tablet.page.getByRole("button", { name: "Vincular tablet à mesa", exact: true });
    await expect(linkButton).toBeDisabled();
    await tablet.page.getByRole("checkbox", { name: "Já conferi o resultado dessa rodada em Verificação de envios" }).check();
    await linkButton.click();
    await expect(tablet.page.getByLabel("Mesa deste tablet")).toHaveText("Mesa 10");
  } finally {
    await tablet.context.close();
  }
});

test("logout concluído com resposta perdida abre a Comanda na nova tentativa", async ({ browser, request, baseURL }) => {
  await prepare(request, allTableFeatures);
  const context = await browser.newContext({ baseURL });

  try {
    const page = await context.newPage();
    let lost = 1;
    await page.route("**/api/configuration/v1/sessions/current", async (route) => {
      if (route.request().method() !== "DELETE" || lost-- <= 0) return route.continue();
      await route.fetch();
      await route.abort("failed");
    });

    await page.goto("/comanda/configurar");
    await signIn(page);
    await page.getByRole("combobox", { name: "Mesa" }).selectOption({ label: "Mesa 07" });
    await page.getByRole("button", { name: "Vincular tablet à mesa", exact: true }).click();
    await expect(page.getByRole("alert")).toContainText("sessão do operador continua ativa");
    expect((await page.request.get("/api/orders/v1/queue")).status()).toBe(401);

    await page.getByRole("button", { name: "Encerrar sessão do operador e abrir a Comanda", exact: true }).click();
    await expect(page.getByLabel("Mesa deste tablet")).toHaveText("Mesa 07");
  } finally {
    await context.close();
  }
});
