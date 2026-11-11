import type { Configuration, Fulfillment } from "../api";
import type { Draft } from "./draft";

// Shown before confirmation only; Entregas registers the fee and the server computes the total.
export const deliveryFeeCents = 500;

const fulfillmentOrder: Fulfillment[] = ["pickup", "delivery"];

export function availableFulfillments(configuration?: Configuration) {
  return fulfillmentOrder.filter((fulfillment) => configuration?.features[fulfillment]);
}

export function selectedFulfillment(draft: Draft, configuration?: Configuration): Fulfillment | undefined {
  const available = availableFulfillments(configuration);
  return draft.fulfillment && available.includes(draft.fulfillment) ? draft.fulfillment : available[0];
}

export function feeFor(fulfillment?: Fulfillment) {
  return fulfillment === "delivery" ? deliveryFeeCents : 0;
}
