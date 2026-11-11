import type { Order } from "../../api";
import {
  currency, fulfillmentNames, identification, nextAction, originNames, stateNames, stepsFor, tableLabel,
} from "../../ordering/format";

type OrderCardProps = {
  order: Order;
  staff: boolean;
  highlightCompleted: boolean;
  busy: boolean;
  actionsDisabled: boolean;
  onAdvance: (order: Order) => void;
};

const dispatchMessages = {
  staff: {
    pending: "Saída para entrega em confirmação com o serviço de Entregas.",
    needs_attention: "A saída para entrega precisa de retomada pelo administrador em Envios.",
  },
  customer: {
    pending: "Saída para entrega em confirmação.",
    needs_attention: "Saída para entrega em verificação pelo atendimento.",
  },
};

function TableLine({ order }: { order: Order }) {
  if (order.fulfillment !== "table" || !order.customer_name || !order.table_number) return null;

  return <p>{tableLabel(order.table_number)}</p>;
}

function DeliveryLine({ order }: { order: Order }) {
  if (order.fulfillment !== "delivery") return null;

  if (!order.delivery?.available) {
    return <p role="status">Endereço indisponível no momento. Ele será exibido quando o serviço de Entregas responder.</p>;
  }

  return <p>Entregar em: {order.delivery.address}</p>;
}

function Totals({ order }: { order: Order }) {
  return <div className="totals">
    {order.fee_cents > 0 && <>
      <div><span>Subtotal</span><span>{currency.format((order.total_cents - order.fee_cents) / 100)}</span></div>
      <div><span>Taxa de entrega</span><span>{currency.format(order.fee_cents / 100)}</span></div>
    </>}
    <div className="grand-total">
      <span>Total</span><strong>{currency.format(order.total_cents / 100)}</strong>
    </div>
  </div>;
}

export function OrderCard({ order, staff, highlightCompleted, busy, actionsDisabled, onAdvance }: OrderCardProps) {
  const steps = stepsFor(order);
  const reached = steps.indexOf(order.state);
  const action = nextAction(order);
  const dispatching = order.dispatch_state ? dispatchMessages[staff ? "staff" : "customer"][order.dispatch_state] : "";
  const needsDeliveryDetails = action?.state === "dispatched" && !order.delivery?.available;

  return <article className="info-card">
    {highlightCompleted && <small>Último pedido concluído</small>}
    <div className="section-heading"><h3>Pedido #{order.number}</h3><strong>{stateNames[order.state]}</strong></div>
    <p>{identification(order)} · {fulfillmentNames[order.fulfillment]} · {originNames[order.origin]}</p>
    <TableLine order={order} />
    <DeliveryLine order={order} />
    <p><time dateTime={order.created_at}>{new Date(order.created_at).toLocaleString("pt-BR")}</time></p>
    <ol className="order-items">{order.items.map((item) => <li key={item.product_id}>
      <span>{item.quantity} × {item.name}</span><strong>{currency.format(item.subtotal_cents / 100)}</strong>
    </li>)}</ol>
    <Totals order={order} />
    <div className="progress-steps" aria-label="Etapas do pedido">
      {steps.map((state, index) => <span
        key={state} className={index <= reached ? "reached" : ""}
        aria-current={state === order.state ? "step" : undefined}
      >{stateNames[state]}</span>)}
    </div>
    {dispatching && <p role="status">{dispatching}</p>}
    {staff && action && !order.dispatch_state && <>
      {needsDeliveryDetails && <p>Aguarde os dados de entrega para registrar a saída.</p>}
      <button
        className="primary" disabled={actionsDisabled || needsDeliveryDetails}
        onClick={() => onAdvance(order)}
      >{busy ? "Atualizando…" : action.label}</button>
    </>}
  </article>;
}
