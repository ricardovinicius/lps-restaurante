import { expect, type APIRequestContext } from "@playwright/test";

export const configurationPath = "/api/configuration/v1/configuration";
export const catalogPath = "/api/catalog/v1";
export const ordersPath = "/api/orders/v1";

export async function prepare(request: APIRequestContext, features: Record<string, boolean> = { pickup: true }) {
  const login = await request.post("/api/configuration/v1/sessions", { data: {
    username: "admin", password: process.env.MESA_DEMO_ADMIN_PASSWORD ?? "DemoAdminChangeMe",
  } });
  expect(login.status()).toBe(201);
  const session = await (await request.get("/api/configuration/v1/sessions/current")).json();
  const configuration = await (await request.get(configurationPath)).json();
  const headers = { "X-CSRF-Token": session.csrf_token };
  expect((await request.put(configurationPath, { headers, data: {
    expected_revision: configuration.revision, features: { ...configuration.features, ...features },
  } })).status()).toBe(200);
  const catalog = await (await request.get(catalogPath + "/admin/products")).json();
  const product = catalog.items[0];
  const updated = await request.patch(catalogPath + "/products/" + product.id, { headers, data: {
    expected_revision: catalog.revision, available: true,
  } });
  expect(updated.status()).toBe(200);
  return { product: (await updated.json()).product, headers };
}

