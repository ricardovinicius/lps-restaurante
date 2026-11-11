export type Features = {
  catalog: true;
  orders: true;
  pickup: boolean;
  delivery: boolean;
  tables: boolean;
  tablet: boolean;
  tv: boolean;
};

export type Configuration = { revision: number; features: Features; updated_at: string };
export type Preset = { version: 1; name: string; features: Features; services: string[] };
export type Session = { username: string; role: "admin" | "operator"; expires_at: string; csrf_token: string };

export type Product = {
  id: string;
  category_id: string;
  category_name: string;
  name: string;
  description: string;
  image_url: string | null;
  price_cents: number;
  available: boolean;
};

type ProductPage = { revision: number; items: Product[]; next_cursor: string | null };

export class ApiError extends Error {
  constructor(public status: number, message: string, public code?: string, public details?: unknown) {
    super(message);
  }
}

async function request<T>(path: string, method = "GET", body?: unknown, csrf?: string, extraHeaders?: HeadersInit): Promise<T> {
  const headers = new Headers(extraHeaders);
  if (body !== undefined) headers.set("Content-Type", "application/json");
  if (csrf) headers.set("X-CSRF-Token", csrf);

  let response: Response;
  try {
    response = await fetch("/api/" + path, {
      method, headers, body: JSON.stringify(body), cache: "no-store", signal: AbortSignal.timeout(12000),
    });
  } catch {
    throw new ApiError(503, "Serviço indisponível. Tente novamente.");
  }

  if (!response.ok) {
    const data = await response.json().catch(() => null);
    throw new ApiError(response.status, data?.error?.message ?? "Serviço indisponível. Tente novamente.", data?.error?.code, data?.error?.details);
  }

  return response.status === 204 ? undefined as T : response.json();
}

const configuration = "configuration/v1/configuration";
const sessions = "configuration/v1/sessions";
const catalog = "catalog/v1/";
const orders = "orders/v1/";
let customerContextRequest: Promise<{ context_id: string }> | undefined;
const customerAccessKey = "mesa-facil-customer-access";
type CustomerAccess = { context_id?: string; recovery_token: string };

function newCustomerAccess(): CustomerAccess {
  return { recovery_token: (crypto.randomUUID() + crypto.randomUUID()).replaceAll("-", "") };
}

async function initializeCustomer(newContext = false) {
  const access: CustomerAccess = !newContext && localStorage.getItem(customerAccessKey)
    ? JSON.parse(localStorage.getItem(customerAccessKey)!) : newCustomerAccess();
  localStorage.setItem(customerAccessKey, JSON.stringify(access));
  const context = access.context_id
    ? await request<{ context_id: string }>(orders + "customer-contexts/recover", "POST", access)
    : await request<{ context_id: string }>(orders + "customer-contexts", "POST", {
      recovery_token: access.recovery_token, new_context: newContext,
    });
  localStorage.setItem(customerAccessKey, JSON.stringify({ ...access, context_id: context.context_id }));
  return context;
}

function customerContext(refresh = false) {
  if (refresh) customerContextRequest = undefined;
  if (!customerContextRequest) {
    customerContextRequest = initializeCustomer().catch((error: unknown) => {
      customerContextRequest = undefined;
      throw error;
    });
  }
  return customerContextRequest;
}

async function customerRequest<T>(read: () => Promise<T>, recoverMissing = false) {
  await customerContext();
  try {
    return await read();
  } catch (error) {
    if (!(error instanceof ApiError) || !(error.code === "invalid_customer_context" || (recoverMissing && error.status === 404))) throw error;
    await customerContext(true);
    return read();
  }
}

export function isCheckoutRejection(code?: string) {
  return Boolean(code && ["feature_disabled", "configuration_changed", "catalog_changed", "price_changed",
    "product_unavailable", "idempotency_conflict", "invalid_input"].includes(code));
}

export type OrderState = "received" | "preparing" | "ready" | "completed";
export type Order = {
  id: string;
  number: number;
  origin: "client" | "counter";
  fulfillment: "pickup";
  customer_name: string;
  state: OrderState;
  version: number;
  configuration_revision: number;
  catalog_revision: number;
  items: { product_id: string; name: string; unit_price_cents: number; quantity: number; subtotal_cents: number }[];
  fee_cents: number;
  total_cents: number;
  created_at: string;
  updated_at: string;
};

export type CreateOrder = {
  configuration_revision: number;
  catalog_revision: number;
  origin: Order["origin"];
  fulfillment: "pickup";
  customer_name: string;
  items: { product_id: string; quantity: number; expected_unit_price_cents: number }[];
};

export type OrderOperation = {
  operation_id: string;
  state: "pending" | "succeeded" | "rejected" | "needs_attention";
  status_url?: string;
  order?: Order;
  error?: { code: string; message: string; details?: unknown };
};

export type OrderPage = { items: Order[]; next_cursor: string | null };
export type OperationSummary = {
  operation_id: string; idempotency_key: string; state: OrderOperation["state"];
  customer_name: string; origin: Order["origin"]; attempts: number;
  created_at: string; updated_at: string; error: OrderOperation["error"] | null;
};
export type OperationPage = { items: OperationSummary[]; next_cursor: string | null };

export const api = {
  session: () => request<Session>(sessions + "/current"),
  login: async (username: string, password: string) => {
    await request(sessions, "POST", { username, password });
    return request<Session>(sessions + "/current");
  },
  logout: (csrf: string) => request<void>(sessions + "/current", "DELETE", undefined, csrf),
  configuration: () => request<Configuration>(configuration),
  presets: () => request<Preset[]>(configuration + "/presets"),
  exportConfiguration: () => request<Preset>(configuration + "/export"),
  saveConfiguration: (features: Features, revision: number, csrf: string) =>
    request<Configuration>(configuration, "PUT", { features, expected_revision: revision }, csrf),
  products: (admin: boolean, cursor?: string) => {
    const query = new URLSearchParams();
    if (cursor) query.set("cursor", cursor);
    return request<ProductPage>(catalog + (admin ? "admin/products?" : "products?") + query);
  },
  saveProduct: (id: string, revision: number, price_cents: number, available: boolean, csrf: string) =>
    request<{ revision: number; product: Product }>(
      catalog + "products/" + id, "PATCH", { expected_revision: revision, price_cents, available }, csrf,
    ),
  customerContext,
  startNewCustomerContext: () => {
    customerContextRequest = initializeCustomer(true).catch((error: unknown) => {
      customerContextRequest = undefined;
      throw error;
    });
    return customerContextRequest;
  },
  createOrder: (body: CreateOrder, key: string, csrf?: string, contextId?: string) => {
    const send = () => request<Order | OrderOperation>(orders + "orders", "POST", body, csrf, {
      "Idempotency-Key": key, ...(contextId ? { "X-Customer-Context": contextId } : {}),
    });
    return body.origin === "client" ? customerRequest(send) : send();
  },
  operation: (id: string, customer = false) => {
    const read = () => request<OrderOperation>(orders + "operations/" + id);
    return customer ? customerRequest(read, true) : read();
  },
  operations: (state: string, reference: string, cursor?: string) =>
    request<OperationPage>(orders + "operations?" + new URLSearchParams({ state, ...(reference ? { reference } : {}), ...(cursor ? { cursor } : {}) })),
  resumeOperation: (id: string, csrf: string) => request<OrderOperation>(orders + "operations/" + id + "/resume", "POST", undefined, csrf),
  myOrders: (cursor?: string, status?: "active" | "completed") => customerRequest(() =>
    request<OrderPage>(orders + "my-orders?" + new URLSearchParams({ ...(cursor ? { cursor } : {}), ...(status ? { status } : {}) }))),
  queue: (cursor?: string) => request<OrderPage>(orders + "queue?" + new URLSearchParams({ fulfillment: "pickup", ...(cursor ? { cursor } : {}) })),
  order: (id: string) => request<Order>(orders + "orders/" + id),
  transition: (id: string, expected_version: number, target_state: OrderState, key: string, csrf: string) =>
    request<Order>(orders + "orders/" + id + "/transitions", "POST", { expected_version, target_state }, csrf, { "Idempotency-Key": key }),
};

export function errorMessage(error: unknown) {
  return error instanceof Error ? error.message : "Ocorreu um erro. Tente novamente.";
}
