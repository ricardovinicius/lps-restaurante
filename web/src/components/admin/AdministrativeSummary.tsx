import { api, ApiError } from "../../api";
import { usePolling } from "../../hooks/usePolling";
import { currency } from "../../ordering/format";
import { Synchronization } from "../orders/Synchronization";

function unauthorized(failure: unknown) {
  return failure instanceof ApiError && (failure.status === 401 || failure.status === 403);
}

export function AdministrativeSummary() {
  const orders = usePolling(api.orderSummary);
  const catalog = usePolling(api.catalogSummary);
  const orderValues = unauthorized(orders.failure) ? undefined : orders.value;
  const productValues = unauthorized(catalog.failure) ? undefined : catalog.value;

  return <section className="administrative-summary" aria-label="Resumo administrativo">
    <h2>Resumo da operação</h2>
    <div className="summary-sources">
      <div>
        <div className="stats">
          <div className="stat" aria-label="Pedidos em andamento">
            <span>Pedidos em andamento</span><strong>{orderValues?.active_orders ?? "—"}</strong>
          </div>
          <div className="stat" aria-label="Valor dos pedidos concluídos">
            <span>Valor dos pedidos concluídos</span>
            <strong>{orderValues ? currency.format(orderValues.completed_order_value_cents / 100) : "—"}</strong>
          </div>
        </div>
        <Synchronization error={orders.error} syncedAt={orders.syncedAt} hasDisplayedData={Boolean(orderValues)} />
      </div>
      <div>
        <div className="stat" aria-label="Produtos disponíveis">
          <span>Produtos disponíveis</span>
          <strong>{productValues
            ? productValues.available_products + " / " + productValues.total_products : "—"}</strong>
        </div>
        <Synchronization error={catalog.error} syncedAt={catalog.syncedAt} hasDisplayedData={Boolean(productValues)} />
      </div>
    </div>
    {(!orders.value && !orders.error || !catalog.value && !catalog.error) && <p role="status">Carregando resumo…</p>}
    <p>Valores acumulados do histórico preservado, incluindo taxas de entrega. Não representam receita recebida.</p>
  </section>;
}
