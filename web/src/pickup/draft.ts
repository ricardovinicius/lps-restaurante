import { useCallback, useEffect, useRef, useState } from "react";
import type { CreateOrder, Order } from "../api";

export type CartItem = { product_id: string; name: string; unit_price_cents: number; quantity: number };

export type Pending = {
  key: string;
  payload: CreateOrder;
  operationId?: string;
  customerContextId?: string;
};

export type Draft = {
  items: CartItem[];
  customerName: string;
  configurationRevision?: number;
  pending?: Pending;
  reviewRequired?: boolean;
  recoveryRequired?: boolean;
};

export const emptyDraft = (): Draft => ({ items: [], customerName: "" });

function readDraft(key: string): Draft {
  try {
    const value = JSON.parse(localStorage.getItem(key) ?? "null") as Draft | null;
    if (value && Array.isArray(value.items) && typeof value.customerName === "string") return value;
  } catch {}

  return emptyDraft();
}

export function usePickupDraft(origin: Order["origin"], staffUsername?: string) {
  const storageKey = "mesa-facil-pickup-" + origin + (staffUsername ? ":" + staffUsername : "");
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

export type PickupDraftStore = ReturnType<typeof usePickupDraft>;
