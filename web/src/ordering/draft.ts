import { useCallback, useEffect, useRef, useState } from "react";
import type { CreateOrder, Fulfillment, Order } from "../api";

export type CartItem = { product_id: string; name: string; unit_price_cents: number; quantity: number };

export type Pending = {
  key: string;
  payload: CreateOrder;
  operationId?: string;
  customerContextId?: string;
  tableContextId?: string;
};

export type TableChoice = { id: string; number: number };

export type Draft = {
  items: CartItem[];
  customerName: string;
  fulfillment?: Fulfillment;
  address: string;
  table?: TableChoice;
  configurationRevision?: number;
  pending?: Pending;
  reviewRequired?: boolean;
  recoveryRequired?: boolean;
};

export const emptyDraft = (): Draft => ({ items: [], customerName: "", address: "" });

function readDraft(key: string): Draft {
  try {
    const value = JSON.parse(localStorage.getItem(key) ?? "null") as Draft | null;
    if (value && Array.isArray(value.items) && typeof value.customerName === "string") {
      return { ...emptyDraft(), ...value };
    }
  } catch {}

  return emptyDraft();
}

// The key predates deliveries; keeping it preserves carts and pending sends across upgrades.
// The scope separates carts per operator and per tablet context.
function storageKeyFor(origin: Order["origin"], scope?: string) {
  return "mesa-facil-pickup-" + origin + (scope ? ":" + scope : "");
}

export function storedPendingSend(origin: Order["origin"], scope: string) {
  try {
    return readDraft(storageKeyFor(origin, scope)).pending;
  } catch {
    return undefined;
  }
}

export function useOrderDraft(origin: Order["origin"], scope?: string) {
  const storageKey = storageKeyFor(origin, scope);
  const mounted = useRef(true);
  const [draft, setDraft] = useState(() => readDraft(storageKey));
  const currentDraft = useRef(draft);
  const [storageError, setStorageError] = useState("");

  useEffect(() => {
    mounted.current = true;
    return () => { mounted.current = false; };
  }, []);

  const saveDraft = useCallback((value: Draft) => {
    if (!mounted.current) return false;

    try {
      localStorage.setItem(storageKey, JSON.stringify(value));
      setStorageError("");
    } catch {
      setStorageError("Não foi possível preservar o carrinho neste navegador. "
        + "Libere o armazenamento antes de enviar.");
      return false;
    }

    currentDraft.current = value;
    setDraft(value);
    return true;
  }, [storageKey]);

  function archiveVerifiedAttempt() {
    localStorage.setItem(storageKey + "-verified-attempt", JSON.stringify({
      pending: currentDraft.current.pending,
      verified_at: new Date().toISOString(),
    }));
  }

  return { draft, currentDraft, saveDraft, archiveVerifiedAttempt, mounted, storageError };
}

export type OrderDraftStore = ReturnType<typeof useOrderDraft>;
