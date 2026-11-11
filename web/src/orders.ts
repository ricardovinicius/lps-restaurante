import { useState } from "react";
import type { Order, Product } from "./api";
import { usePickupCheckout } from "./pickup/checkout";
import { usePickupDraft, type CartItem } from "./pickup/draft";
import { usePickupMenu } from "./pickup/menu";

export const currency = new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" });
export const stateNames = { received: "Recebido", preparing: "Em preparo", ready: "Pronto", completed: "Concluído" };

export function usePickup(
  origin: Order["origin"],
  csrf: string | undefined,
  onCreated: (order: Order) => void,
  staffUsername?: string,
) {
  const store = usePickupDraft(origin, staffUsername);
  const [feedback, setFeedback] = useState("");
  const menu = usePickupMenu(store, setFeedback);
  const checkout = usePickupCheckout({ store, menu, origin, csrf, onCreated, setFeedback });
  const { draft, currentDraft, saveDraft, mounted, storageError } = store;
  const { configuration, loadCatalog } = menu;
  const { busy, setBusy } = checkout;

  function changeQuantity(product: Product | CartItem, change: number) {
    const current = currentDraft.current;
    if (current.pending || busy || !configuration?.features.pickup || current.reviewRequired) return;

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
    if (!currentDraft.current.pending) saveDraft({ ...currentDraft.current, customerName });
  }

  return {
    draft, feedback, storageError, busy,
    configuration, configurationSync: menu.configurationSync,
    catalog: menu.catalog, catalogError: menu.catalogError, loadCatalog,
    changeQuantity, changeName, review,
    submit: checkout.submit,
    recoverIdentification: checkout.recoverIdentification,
    restartAfterVerification: checkout.restartAfterVerification,
  };
}
