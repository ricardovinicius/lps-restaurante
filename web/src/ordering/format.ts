import type { Fulfillment, Order, OrderState, Origin } from "../api";

export const currency = new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" });

export const stateNames: Record<OrderState, string> = {
  received: "Recebido",
  preparing: "Em preparo",
  ready: "Pronto",
  dispatched: "Saiu para entrega",
  completed: "Concluído",
};

export const fulfillmentNames: Record<Fulfillment, string> = { pickup: "Retirada", delivery: "Entrega", table: "Mesa" };

export const originNames: Record<Origin, string> = { client: "Cliente", counter: "Balcão", tablet: "Comanda" };

const steps: Record<Fulfillment, OrderState[]> = {
  pickup: ["received", "preparing", "ready", "completed"],
  delivery: ["received", "preparing", "ready", "dispatched", "completed"],
  table: ["received", "preparing", "ready", "completed"],
};

type OperatorAction = { state: OrderState; label: string };

const prepare: Partial<Record<OrderState, OperatorAction>> = {
  received: { state: "preparing", label: "Iniciar preparo" },
  preparing: { state: "ready", label: "Marcar como pronto" },
};

const operatorActions: Record<Fulfillment, Partial<Record<OrderState, OperatorAction>>> = {
  pickup: { ...prepare, ready: { state: "completed", label: "Concluir retirada" } },
  delivery: {
    ...prepare,
    ready: { state: "dispatched", label: "Saiu para entrega" },
    dispatched: { state: "completed", label: "Concluir entrega" },
  },
  table: { ...prepare, ready: { state: "completed", label: "Concluir atendimento" } },
};

export function stepsFor(order: Order) {
  return steps[order.fulfillment];
}

export function nextAction(order: Order) {
  return operatorActions[order.fulfillment][order.state];
}

export function tableLabel(number: number) {
  return "Mesa " + String(number).padStart(2, "0");
}

/** Tablet rounds have no customer name: the table identifies them. */
export function identification(order: Pick<Order, "customer_name" | "table_number">) {
  if (order.customer_name) return order.customer_name;
  return order.table_number ? tableLabel(order.table_number) : "Comanda";
}
