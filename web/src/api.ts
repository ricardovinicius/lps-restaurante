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
  category_name: string;
  name: string;
  description: string;
  image_url: string | null;
  price_cents: number;
  available: boolean;
};

type ProductPage = { revision: number; items: Product[]; next_cursor: string | null };

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

async function request<T>(path: string, method = "GET", body?: unknown, csrf?: string): Promise<T> {
  const headers = new Headers();
  if (body !== undefined) headers.set("Content-Type", "application/json");
  if (csrf) headers.set("X-CSRF-Token", csrf);

  let response: Response;
  try {
    response = await fetch("/api/" + path, {
      method, headers, body: JSON.stringify(body), cache: "no-store",
    });
  } catch {
    throw new ApiError(503, "Serviço indisponível. Tente novamente.");
  }

  if (!response.ok) {
    const data = await response.json().catch(() => null);
    throw new ApiError(response.status, data?.error?.message ?? "Serviço indisponível. Tente novamente.");
  }

  return response.status === 204 ? undefined as T : response.json();
}

const configuration = "configuration/v1/configuration";
const sessions = "configuration/v1/sessions";
const catalog = "catalog/v1/";

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
};

export function errorMessage(error: unknown) {
  return error instanceof Error ? error.message : "Ocorreu um erro. Tente novamente.";
}
