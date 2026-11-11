import { useCallback, useEffect, useState } from "react";
import { api, ApiError } from "../../api";
import { usePolling } from "../../hooks/usePolling";
import { currency, stateNames, stepsFor, tableLabel } from "../../ordering/format";
import { Synchronization } from "../orders/Synchronization";

type TableHistoryProps = {
  revision: number;
  onLost: () => void;
  onOrder: () => void;
};

/** “Já pedi”: the table's permanent history from every origin, one page at a time. */
export function TableHistory({ revision, onLost, onOrder }: TableHistoryProps) {
  const [cursor, setCursor] = useState<string>();
  const read = useCallback(async () => {
    try {
      return await api.tableOrders(cursor);
    } catch (error) {
      if (error instanceof ApiError && error.status === 401) onLost();
      throw error;
    }
  }, [cursor, onLost]);
  const sync = usePolling(read, 3000, revision);
  const page = sync.value;

  useEffect(() => { setCursor(undefined); }, [revision]);

  return <section aria-label="Já pedi">
    <Synchronization error={sync.error} syncedAt={sync.syncedAt} />
    {!page && !sync.error && <p role="status">Carregando histórico da mesa…</p>}
    {page && <div className="page-actions">
      <p>
        Histórico da {tableLabel(page.table.number)} · {page.order_count} {page.order_count === 1 ? "pedido" : "pedidos"}
      </p>
      <strong>Total histórico: {currency.format(page.historical_total_cents / 100)}</strong>
    </div>}
    {page && !page.items.length && <section className="info-card">
      <h2>A mesa ainda não fez pedidos.</h2>
      <p>Assim que enviar sua primeira rodada, ela aparecerá aqui.</p>
      <button className="primary" onClick={onOrder}>Escolher algo no cardápio</button>
    </section>}
    <div className="tracking-list">
      {page?.items.map((order) => <article className="info-card tablet-history" key={order.id}>
        <div className="order-head">
          <div>
            <h2>Pedido #{order.number}</h2>
            <small>
              <time dateTime={order.created_at}>{new Date(order.created_at).toLocaleString("pt-BR")}</time>
              {order.table_number && " · " + tableLabel(order.table_number)}
            </small>
          </div>
          <span>{stateNames[order.state]}</span>
        </div>
        <div className="progress-steps" aria-label="Etapas do pedido">
          {stepsFor(order).map((state, index) => <span
            key={state} className={index <= stepsFor(order).indexOf(order.state) ? "reached" : ""}
            aria-current={state === order.state ? "step" : undefined}
          >{stateNames[state]}</span>)}
        </div>
        {order.items.map((item) => <div className="history-item" key={item.product_id}>
          <span><b>{item.quantity}×</b> {item.name} · {currency.format(item.unit_price_cents / 100)}</span>
          <strong>{currency.format(item.subtotal_cents / 100)}</strong>
        </div>)}
        <div className="history-total">
          <span>Total desta rodada</span><strong>{currency.format(order.total_cents / 100)}</strong>
        </div>
      </article>)}
    </div>
    <div className="actions pagination">
      {cursor && <button className="secondary" onClick={() => setCursor(undefined)}>Pedidos mais recentes</button>}
      {page?.next_cursor && <button className="secondary" onClick={() => setCursor(page.next_cursor!)}>
        Pedidos anteriores
      </button>}
    </div>
    <p className="history-note">
      Total histórico da mesa; inclui pedidos concluídos e de visitas anteriores. Não representa conta aberta.
    </p>
  </section>;
}
