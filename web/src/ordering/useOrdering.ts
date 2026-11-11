import { useState } from "react";
import type { Fulfillment, Order, Product } from "../api";
import { useOrderCheckout } from "./checkout";
import { useOrderDraft, type CartItem, type TableChoice } from "./draft";
import { availableFulfillments, feeFor, selectedFulfillment } from "./fulfillment";
import { useOrderMenu } from "./menu";

export function useOrdering(
  origin: Order["origin"],
  csrf: string | undefined,
  onCreated: (order: Order) => void,
  scope?: string,
) {
  // The scope is the operator for the Balcão and the table context for the Comanda.
  const store = useOrderDraft(origin, scope);
  const [feedback, setFeedback] = useState("");
  const menu = useOrderMenu(store, setFeedback);
  const tableContextId = origin === "tablet" ? scope : undefined;
  const checkout = useOrderCheckout({ store, menu, origin, csrf, tableContextId, onCreated, setFeedback });
  const { draft, currentDraft, saveDraft, mounted, storageError } = store;
  const { configuration, loadCatalog } = menu;
  const { busy, setBusy } = checkout;

  const fulfillments = availableFulfillments(configuration, origin);
  // A pending send keeps what was submitted, even if the configuration has changed since.
  const fulfillment = draft.pending?.payload.fulfillment ?? selectedFulfillment(draft, configuration, origin);
  const address = draft.pending?.payload.address ?? draft.address;
  const subtotal = draft.items.reduce((sum, item) => sum + item.quantity * item.unit_price_cents, 0);
  const fee = feeFor(fulfillment);
  const total = draft.items.length ? subtotal + fee : 0;

  function canEdit() {
    const current = currentDraft.current;
    return !current.pending && !busy;
  }

  function changeQuantity(product: Product | CartItem, change: number) {
    const current = currentDraft.current;
    if (!canEdit() || !fulfillment || current.reviewRequired) return;

    const id = "product_id" in product ? product.product_id : product.id;
    const found = current.items.find((item) => item.product_id === id);
    if (!found && current.items.length >= 50) {
      setFeedback("Cada pedido pode ter até 50 produtos diferentes.");
      return;
    }

    const quantity = (found?.quantity ?? 0) + change;
    if (quantity > 99) return;

    const items = current.items.filter((item) => item.product_id !== id);
    if (quantity > 0) items.push({
      product_id: id, name: product.name, quantity,
      unit_price_cents: found?.unit_price_cents
        ?? ("unit_price_cents" in product ? product.unit_price_cents : product.price_cents),
    });
    saveDraft({ ...current, items });
  }

  async function review() {
    if (busy || currentDraft.current.pending) return;

    setBusy(true);
    const value = await loadCatalog();
    if (value) {
      const current = currentDraft.current;
      const items = current.items.flatMap((item) => {
        const product = value.items.find((product) => product.id === item.product_id && product.available);
        return product ? [{ ...item, name: product.name, unit_price_cents: product.price_cents }] : [];
      });
      saveDraft({ ...current, items, reviewRequired: false });
      setFeedback("Carrinho atualizado com os preços atuais. Produtos indisponíveis foram removidos. "
        + "Confira os itens e o total antes de confirmar.");
    }

    if (mounted.current) setBusy(false);
  }

  function changeName(customerName: string) {
    if (canEdit()) saveDraft({ ...currentDraft.current, customerName });
  }

  function changeAddress(address: string) {
    if (canEdit()) saveDraft({ ...currentDraft.current, address });
  }

  function changeTable(table: TableChoice | undefined) {
    if (canEdit()) saveDraft({ ...currentDraft.current, table });
  }

  function changeFulfillment(value: Fulfillment) {
    if (canEdit() && fulfillments.includes(value)) saveDraft({ ...currentDraft.current, fulfillment: value });
  }

  return {
    draft, feedback, storageError, busy,
    configuration, configurationSync: menu.configurationSync,
    catalog: menu.catalog, catalogError: menu.catalogError, catalogSyncedAt: menu.catalogSyncedAt, loadCatalog,
    fulfillments, fulfillment, address, subtotal, fee, total,
    changeQuantity, changeName, changeAddress, changeFulfillment, changeTable, review,
    submit: checkout.submit,
    recoverIdentification: checkout.recoverIdentification,
    restartAfterVerification: checkout.restartAfterVerification,
  };
}
