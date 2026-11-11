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
    "product_unavailable", "idempotency_conflict", "invalid_input", "table_not_found", "table_unavailable"].includes(code));
}

export type OrderState = "received" | "preparing" | "ready" | "dispatched" | "completed";
export type Fulfillment = "pickup" | "delivery" | "table";
export type Origin = "client" | "counter" | "tablet";
export type DeliveryDetails = { available: boolean; address: string | null; dispatched_at: string | null };
export type Order = {
  id: string;
  number: number;
  origin: Origin;
  fulfillment: Fulfillment;
  customer_name: string | null;
  table_id?: string | null;
  table_number?: number | null;
  state: OrderState;
  version: number;
  configuration_revision: number;
  catalog_revision: number;
  items: { product_id: string; name: string; unit_price_cents: number; quantity: number; subtotal_cents: number }[];
  fee_cents: number;
  total_cents: number;
  created_at: string;
  updated_at: string;
  delivery?: DeliveryDetails | null;
  dispatch_state?: "pending" | "needs_attention" | null;
};

export type CreateOrder = {
  configuration_revision: number;
  catalog_revision: number;
  origin: Order["origin"];
  fulfillment: Fulfillment;
  customer_name?: string;
  address?: string;
  table_id?: string;
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
  customer_name: string | null; origin: Origin; fulfillment: Fulfillment; table_number: number | null; attempts: number;
  created_at: string; updated_at: string; error: OrderOperation["error"] | null;
};
export type OperationPage = { items: OperationSummary[]; next_cursor: string | null };
export type PendingDispatch = { operation_id: string; order_id: string; state: "pending" | "needs_attention"; status_url: string };
export type DispatchSummary = {
  operation_id: string; order_id: string; order_number: number; customer_name: string | null;
  state: "pending" | "succeeded" | "needs_attention"; attempts: number;
  created_at: string; updated_at: string; error: OrderOperation["error"] | null;
};
export type DispatchPage = { items: DispatchSummary[]; next_cursor: string | null };
export type DiningTable = { id: string; number: number; available: boolean; version: number };
export type TablePage = { items: DiningTable[]; next_cursor: string | null };
export type TableContext = {
  context_id: string; table_id: string; table_number: number; expires_at: string; csrf_token: string;
};
export type TableOrderPage = {
  table: { id: string; number: number }; items: Order[]; next_cursor: string | null;
  historical_total_cents: number; order_count: number;
};
const tables = "tables/v1/";

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
    // The owner context of the pending send: a retry from another identity is refused by the server.
    const contextHeader = body.origin === "tablet" ? "X-Table-Context" : "X-Customer-Context";
    const send = () => request<Order | OrderOperation>(orders + "orders", "POST", body, csrf, {
      "Idempotency-Key": key, ...(contextId ? { [contextHeader]: contextId } : {}),
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
  queue: (cursor?: string) => request<OrderPage>(orders + "queue?" + new URLSearchParams(cursor ? { cursor } : {})),
  order: (id: string) => request<Order>(orders + "orders/" + id),
  transition: (id: string, expected_version: number, target_state: OrderState, key: string, csrf: string) =>
    request<Order | PendingDispatch>(
      orders + "orders/" + id + "/transitions", "POST", { expected_version, target_state }, csrf, { "Idempotency-Key": key },
    ),
  dispatches: (state: string, cursor?: string) =>
    request<DispatchPage>(orders + "dispatches?" + new URLSearchParams({ state, ...(cursor ? { cursor } : {}) })),
  resumeDispatch: (id: string, csrf: string) =>
    request<PendingDispatch>(orders + "dispatches/" + id + "/resume", "POST", undefined, csrf),
  tables: (includeUnavailable = false, cursor?: string) => request<TablePage>(tables + "tables?" + new URLSearchParams({
    limit: "100", ...(includeUnavailable ? { include_unavailable: "true" } : {}), ...(cursor ? { cursor } : {}),
  })),
  setTableAvailability: (table: DiningTable, available: boolean, csrf: string) =>
    request<DiningTable>(tables + "tables/" + table.id, "PATCH", { expected_version: table.version, available }, csrf),
  provisionTable: (tableId: string, csrf: string) =>
    request<TableContext>(tables + "table-contexts", "POST", { table_id: tableId }, csrf),
  currentTableContext: () => request<TableContext>(tables + "table-contexts/current"),
  revokeTableContext: (csrf: string) => request<void>(tables + "table-contexts/current", "DELETE", undefined, csrf),
  tableOrders: (cursor?: string) =>
    request<TableOrderPage>(orders + "table-orders?" + new URLSearchParams(cursor ? { cursor } : {})),
};

export function errorMessage(error: unknown) {
  return error instanceof Error ? error.message : "Ocorreu um erro. Tente novamente.";
}
