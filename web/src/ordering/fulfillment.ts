import type { Configuration, Fulfillment, Origin } from "../api";
import type { Draft } from "./draft";

// Shown before confirmation only; Entregas registers the fee and the server computes the total.
export const deliveryFeeCents = 500;

const fulfillmentOrder: Fulfillment[] = ["pickup", "delivery", "table"];
const fulfillmentFeature = { pickup: "pickup", delivery: "delivery", table: "tables" } as const;

export function availableFulfillments(configuration: Configuration | undefined, origin: Origin) {
  const features = configuration?.features;
  if (!features) return [];

  // The Comanda only orders for its own table, and needs both table service and tablet features.
  if (origin === "tablet") return features.tables && features.tablet ? ["table" as const] : [];

  return fulfillmentOrder.filter((fulfillment) => features[fulfillmentFeature[fulfillment]]);
}

export function selectedFulfillment(draft: Draft, configuration: Configuration | undefined, origin: Origin) {
  const available = availableFulfillments(configuration, origin);
  return draft.fulfillment && available.includes(draft.fulfillment) ? draft.fulfillment : available[0];
}

export function feeFor(fulfillment?: Fulfillment) {
  return fulfillment === "delivery" ? deliveryFeeCents : 0;
}
