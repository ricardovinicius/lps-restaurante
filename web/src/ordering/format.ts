import type { Fulfillment, Order, OrderState } from "../api";

export const currency = new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" });

export const stateNames: Record<OrderState, string> = {
  received: "Recebido",
  preparing: "Em preparo",
  ready: "Pronto",
  dispatched: "Saiu para entrega",
  completed: "Concluído",
};

export const fulfillmentNames: Record<Fulfillment, string> = { pickup: "Retirada", delivery: "Entrega" };

const steps: Record<Fulfillment, OrderState[]> = {
  pickup: ["received", "preparing", "ready", "completed"],
  delivery: ["received", "preparing", "ready", "dispatched", "completed"],
};

type OperatorAction = { state: OrderState; label: string };

const operatorActions: Record<Fulfillment, Partial<Record<OrderState, OperatorAction>>> = {
  pickup: {
    received: { state: "preparing", label: "Iniciar preparo" },
    preparing: { state: "ready", label: "Marcar como pronto" },
    ready: { state: "completed", label: "Concluir retirada" },
  },
  delivery: {
    received: { state: "preparing", label: "Iniciar preparo" },
    preparing: { state: "ready", label: "Marcar como pronto" },
    ready: { state: "dispatched", label: "Saiu para entrega" },
    dispatched: { state: "completed", label: "Concluir entrega" },
  },
};

export function stepsFor(order: Order) {
  return steps[order.fulfillment];
}

export function nextAction(order: Order) {
  return operatorActions[order.fulfillment][order.state];
}
