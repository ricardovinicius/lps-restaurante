import { execFileSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import { expect, test } from "@playwright/test";
import { ordersPath, prepare } from "./helpers";

test("cookie perdido recupera o mesmo cliente e repete o envio sem duplicar", async ({ page, request, context }) => {
  const { product } = await prepare(request);
  await page.goto("/cliente");
  await page.getByRole("button", { name: "Adicionar " + product.name, exact: true }).click();
  await page.getByLabel("Nome para identificação").fill("Recuperação de cookie");
  let first = true;
  await page.route("**/api/orders/v1/orders", async (route) => {
    if (!first) return route.continue();
    first = false;
    await route.fetch();
    await route.abort("failed");
  });
  await page.getByRole("button", { name: "Confirmar retirada", exact: true }).click();
  await expect(page.getByRole("button", { name: "Tentar confirmar o mesmo envio" })).toBeEnabled();
  const originalId = await page.evaluate(() => JSON.parse(localStorage.getItem("mesa-facil-customer-access")!).context_id);
  await context.clearCookies({ name: "mesa_customer" });
  await page.reload();
  await page.getByRole("button", { name: "Tentar confirmar o mesmo envio" }).click();
  await expect(page.getByRole("complementary", { name: "Seu pedido" }).getByText("Seu carrinho está vazio")).toBeVisible();
  await expect(page.getByRole("region", { name: "Meus pedidos" }).getByRole("article")).toHaveCount(1);
  expect(await page.evaluate(() => JSON.parse(localStorage.getItem("mesa-facil-customer-access")!).context_id)).toBe(originalId);
});

test("tentativa antiga sem credencial tem saída explícita após verificar com atendimento", async ({ page, request, context }) => {
  const { product } = await prepare(request);
  await page.goto("/cliente");
  await page.getByRole("button", { name: "Adicionar " + product.name, exact: true }).click();
  await page.getByLabel("Nome para identificação").fill("Tentativa antiga");
  let reference = "";
  await page.route("**/api/orders/v1/orders", async (route) => {
    reference = route.request().headers()["idempotency-key"];
    await route.fetch();
    await route.abort("failed");
  });
  await page.getByRole("button", { name: "Confirmar retirada", exact: true }).click();
  await expect(page.getByRole("button", { name: "Tentar confirmar o mesmo envio" })).toBeEnabled();
  await context.clearCookies({ name: "mesa_customer" });
  await page.evaluate(() => localStorage.removeItem("mesa-facil-customer-access"));
  await page.reload();
  await page.getByRole("button", { name: "Tentar confirmar o mesmo envio" }).click();
  const restart = page.getByRole("button", { name: "Iniciar novo atendimento", exact: true });
  await expect(restart).toBeDisabled();
  const found = await (await request.get(ordersPath + "/operations?reference=" + reference)).json();
  expect(found.items[0].state).toBe("succeeded");
  const detail = await (await request.get(ordersPath + "/operations/" + found.items[0].operation_id)).json();
  expect(detail.order.customer_name).toBe("Tentativa antiga");
  await page.getByRole("checkbox", { name: "Já conferi o resultado do envio anterior com o atendimento" }).check();
  await restart.click();
  await expect(page.getByRole("button", { name: "Revisar preços e disponibilidade" })).toBeVisible();
  await expect(page.getByText("Envio pendente de confirmação.", { exact: false })).toHaveCount(0);
  expect(await page.evaluate(() => Boolean(localStorage.getItem("mesa-facil-pickup-client-verified-attempt")))).toBe(true);
  const unchanged = await (await request.get(ordersPath + "/operations/" + found.items[0].operation_id)).json();
  expect(unchanged.order.id).toBe(detail.order.id);
});

test("histórico não é baixado a cada polling e o contexto é inicializado uma vez", async ({ page, request }) => {
  await prepare(request);
  let contexts = 0;
  let active = 0;
  let completed = 0;
  page.on("request", (request) => {
    const url = new URL(request.url());
    if (url.pathname === ordersPath + "/customer-contexts") contexts += 1;
    if (url.pathname === ordersPath + "/my-orders") {
      if (url.searchParams.get("status") === "active") active += 1;
      if (url.searchParams.get("status") === "completed") completed += 1;
      expect(url.searchParams.has("cursor")).toBe(false);
    }
  });
  await page.goto("/cliente");
  await expect.poll(() => active, { timeout: 12000 }).toBeGreaterThanOrEqual(3);
  expect(contexts).toBe(1);
  expect(completed).toBe(0);
  await page.getByRole("button", { name: "Histórico de concluídos", exact: true }).click();
  await expect.poll(() => completed).toBe(1);
  await expect(page.getByText("Histórico atualizado sob demanda.", { exact: false })).toBeVisible();
  await page.getByRole("region", { name: "Meus pedidos" }).getByRole("button", { name: "Atualizar", exact: true }).click();
  await expect.poll(() => completed).toBe(2);
  expect(contexts).toBe(1);
});

test("Balcão encontra envio pendente e administrador retoma pela interface", async ({ page, request, browser, baseURL }) => {
  const project = process.env.MESA_TEST_COMPOSE_PROJECT;
  test.skip(!project, "Informe MESA_TEST_COMPOSE_PROJECT de um ambiente descartável para simular falha real.");
  if (!project || !/^mesa-(pickup|recovery)-(browser|test)-[a-z0-9-]+$/.test(project)) throw new Error("Use um projeto Compose descartável de testes.");
  test.setTimeout(60000);
  const compose = (...args: string[]) => execFileSync("docker", ["compose", "-p", project, "--env-file", ".env.example", ...args], {
    cwd: fileURLToPath(new URL("../../", import.meta.url)), encoding: "utf8", stdio: ["ignore", "pipe", "pipe"],
  });
  const { product } = await prepare(request);
  await page.goto("/cliente");
  await page.getByRole("button", { name: "Adicionar " + product.name, exact: true }).click();
  await page.getByLabel("Nome para identificação").fill("Intervenção do atendimento");
  let operationId = "";
  let reference = "";
  compose("stop", "catalog");
  try {
    const sent = page.waitForResponse((response) => response.url().endsWith(ordersPath + "/orders") && response.request().method() === "POST");
    await page.getByRole("button", { name: "Confirmar retirada", exact: true }).click();
    const response = await sent;
    expect(response.status()).toBe(202);
    operationId = (await response.json()).operation_id;
    reference = response.request().headers()["idempotency-key"];
    compose("exec", "-T", "orders", "python", "-c", `
from sqlalchemy import text
from mesa_platform.database import create_database_engine
from mesa_platform.settings import Settings
engine = create_database_engine(Settings())
with engine.begin() as connection:
    result = connection.execute(text("UPDATE checkout_operations SET state='needs_attention', attempts=10, lease_id=NULL, lease_expires_at=NULL WHERE id=:id AND state='pending'"), {"id": ${JSON.stringify(operationId)}})
    assert result.rowcount == 1
engine.dispose()
`);
  } finally {
    compose("start", "catalog");
  }
  await expect(page.getByText("O envio precisa de verificação no atendimento.", { exact: false })).toBeVisible();
  const staff = await browser.newContext({ baseURL });
  try {
    const counter = await staff.newPage();
    await counter.goto("/balcao");
    await counter.getByLabel("Usuário", { exact: true }).fill("operator");
    await counter.getByLabel("Senha", { exact: true }).fill(process.env.MESA_DEMO_OPERATOR_PASSWORD ?? "DemoOperatorChangeMe");
    await counter.getByRole("button", { name: "Entrar", exact: true }).click();
    await counter.getByLabel("Referência do envio", { exact: true }).fill(reference);
    await counter.getByRole("button", { name: "Buscar envio", exact: true }).click();
    await counter.getByRole("button", { name: "Verificar envio", exact: true }).click();
    await expect(counter.getByRole("region", { name: "Resultado do envio" })).toContainText("Solicite a retomada a um administrador");
    await expect(counter.getByRole("button", { name: "Retomar envio", exact: true })).toHaveCount(0);
    await counter.getByRole("button", { name: "Sair", exact: true }).click();
    await counter.goto("/admin/envios");
    await counter.getByLabel("Usuário", { exact: true }).fill("admin");
    await counter.getByLabel("Senha", { exact: true }).fill(process.env.MESA_DEMO_ADMIN_PASSWORD ?? "DemoAdminChangeMe");
    await counter.getByRole("button", { name: "Entrar", exact: true }).click();
    await counter.getByLabel("Referência do envio", { exact: true }).fill(reference);
    await counter.getByRole("button", { name: "Buscar envio", exact: true }).click();
    await counter.getByRole("button", { name: "Verificar envio", exact: true }).click();
    await counter.getByRole("button", { name: "Retomar envio", exact: true }).click();
    await expect(counter.getByRole("region", { name: "Resultado do envio" })).toContainText("Confirmado");
    await expect(page.getByRole("region", { name: "Meus pedidos" }).getByRole("article")).toHaveCount(1);
    await expect(page.getByRole("complementary", { name: "Seu pedido" }).getByText("Seu carrinho está vazio")).toBeVisible();
  } finally {
    await staff.close();
  }
});
