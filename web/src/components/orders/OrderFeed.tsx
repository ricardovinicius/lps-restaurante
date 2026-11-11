import { useCallback, useRef, useState } from "react";
import { api, ApiError, errorMessage, type Order } from "../../api";
import { usePolling } from "../../hooks/usePolling";
import { nextAction } from "../../ordering/format";
import { OrderCard } from "./OrderCard";
import { Synchronization } from "./Synchronization";

export function OrderFeed({ csrf, lastOrderId, refreshKey }: {
  csrf?: string;
  lastOrderId?: string;
  refreshKey?: number;
}) {
  const [history, setHistory] = useState(false);
  const [cursor, setCursor] = useState<string>();
  const lastCompleted = useRef<{ contextId: string; order: Order } | undefined>(undefined);
  const read = useCallback(async () => {
    if (csrf) return api.queue(cursor);

    const context = await api.customerContext();
    const page = await api.myOrders(cursor, history ? "completed" : "active");
    if (!history && !cursor && lastOrderId && !page.items.some((order) => order.id === lastOrderId)) {
      let completed = lastCompleted.current;
      if (!completed || completed.contextId !== context.context_id || completed.order.id !== lastOrderId) {
        try {
          const order = await api.order(lastOrderId);
          if (order.state === "completed") completed = { contextId: context.context_id, order };
          else completed = undefined;
          lastCompleted.current = completed;
        } catch (error) {
          if (!(error instanceof ApiError && error.status === 404)) throw error;
          completed = undefined;
        }
      }
      if (completed) page.items.push(completed.order);
    }

    return page;
  }, [csrf, lastOrderId, cursor, history]);
  const sync = usePolling(read, !csrf && history ? null : 3000, refreshKey);
  const [feedback, setFeedback] = useState("");
  const [busy, setBusy] = useState<string>();
  const keys = useRef(new Map<string, string>());
  const orders = sync.value?.items ?? [];

  async function transition(order: Order) {
    const target = nextAction(order)?.state;
    if (!csrf || busy || !target) return;

    const action = order.id + ":" + order.version + ":" + target;
    const key = keys.current.get(action) ?? crypto.randomUUID();
    keys.current.set(action, key);
    setBusy(order.id);
    setFeedback("");

    try {
      const result = await api.transition(order.id, order.version, target, key, csrf);
      if ("operation_id" in result) {
        setFeedback("Saída do pedido #" + order.number + " registrada. Aguardando confirmação do serviço de Entregas.");
      }
      sync.refresh();
    } catch (error) {
      setFeedback(errorMessage(error) + " Atualize a fila antes de repetir a ação.");
      sync.refresh();
    } finally {
      setBusy(undefined);
    }
  }

  return <section className="order-section" aria-label={csrf ? "Fila de pedidos" : "Meus pedidos"}>
    <div className="section-heading">
      <h2>{csrf ? "Fila de pedidos" : "Meus pedidos"}</h2>
      <button className="secondary" onClick={sync.refresh}>Atualizar</button>
    </div>
    {!csrf && <div className="actions">
      <button
        className="secondary" aria-pressed={!history}
        onClick={() => { setHistory(false); setCursor(undefined); }}
      >Em andamento</button>
      <button
        className="secondary" aria-pressed={history}
        onClick={() => { setHistory(true); setCursor(undefined); }}
      >Histórico de concluídos</button>
    </div>}
    <Synchronization error={sync.error} syncedAt={sync.syncedAt} automatic={Boolean(csrf) || !history} />
    {feedback && <p role="alert">{feedback}</p>}
    {!sync.value && !sync.error && <p role="status">Carregando pedidos…</p>}
    {sync.value && !orders.length && <p>
      {csrf ? "Nenhum pedido na fila." : "Você ainda não tem pedidos neste navegador."}
    </p>}
    <div className="tracking-list">
      {orders.map((order) => <OrderCard
        key={order.id} order={order} staff={Boolean(csrf)}
        highlightCompleted={!csrf && !history && order.state === "completed"}
        busy={busy === order.id} actionsDisabled={Boolean(busy) || Boolean(sync.error)}
        onAdvance={(value) => void transition(value)}
      />)}
    </div>
    <div className="actions pagination">
      {cursor && <button className="secondary" onClick={() => setCursor(undefined)}>Primeira página de pedidos</button>}
      {sync.value?.next_cursor && <button
        className="secondary" onClick={() => setCursor(sync.value!.next_cursor!)}
      >Próxima página de pedidos</button>}
    </div>
  </section>;
}

