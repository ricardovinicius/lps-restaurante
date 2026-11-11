import { useCallback, useEffect, useRef, useState } from "react";
import { api, errorMessage, type Product } from "../api";
import { useConfiguration } from "../configuration/ConfigurationProvider";
import { usePolling } from "../hooks/usePolling";
import { emptyDraft, type OrderDraftStore } from "./draft";

type MenuCatalog = { revision: number; items: Product[] };

export async function readCatalog(previous?: MenuCatalog) {
  const first = await api.products(false);
  if (previous && first.revision <= previous.revision) return previous;

  const items = [...first.items];
  let cursor = first.next_cursor;

  while (cursor) {
    const page = await api.products(false, cursor);
    if (page.revision !== first.revision) {
      throw new Error("O catálogo mudou durante a consulta. Tente novamente.");
    }

    items.push(...page.items);
    cursor = page.next_cursor;
  }

  return { revision: first.revision, items };
}

export function useOrderMenu(store: OrderDraftStore, setFeedback: (message: string) => void) {
  const { mounted, currentDraft, saveDraft } = store;
  const configurationSync = useConfiguration();
  const { configuration } = configurationSync;
  const currentConfiguration = useRef(configuration);
  currentConfiguration.current = configuration;
  const [catalog, setCatalog] = useState<MenuCatalog>();
  const snapshot = useRef<MenuCatalog | undefined>(undefined);
  const pending = useRef<Promise<MenuCatalog> | undefined>(undefined);
  const [catalogError, setCatalogError] = useState("");
  const [catalogSyncedAt, setCatalogSyncedAt] = useState<Date>();

  useEffect(() => {
    if (!configuration) return;
    const current = currentDraft.current;

    if (current.configurationRevision !== configuration.revision && !current.pending) {
      if (current.items.length) {
        setFeedback("A configuração mudou. O carrinho foi reiniciado; revise as opções disponíveis.");
      }

      saveDraft({ ...emptyDraft(), configurationRevision: configuration.revision });
    }

  }, [configuration, saveDraft, currentDraft, setFeedback]);

  const refreshCatalog = useCallback(() => {
    if (!pending.current) pending.current = readCatalog(snapshot.current).then((value) => {
      if (!mounted.current) return value;

      const current = currentDraft.current;
      const changedItem = current.items.some((item) => {
        const product = value.items.find((product) => product.id === item.product_id);
        return !product || product.price_cents !== item.unit_price_cents;
      });
      if (!current.pending && !current.reviewRequired && changedItem) {
        saveDraft({ ...current, reviewRequired: true });
        setFeedback("Preços ou disponibilidade mudaram. Revise o carrinho antes de enviar.");
      }

      snapshot.current = value;
      setCatalog(value);
      setCatalogError("");
      setCatalogSyncedAt(new Date());
      return value;
    }).catch((error: unknown) => {
      if (mounted.current) setCatalogError(errorMessage(error));
      throw error;
    }).finally(() => { pending.current = undefined; });

    return pending.current;
  }, [mounted, currentDraft, saveDraft, setFeedback]);
  usePolling(refreshCatalog);

  const loadCatalog = useCallback(() => refreshCatalog().catch(() => undefined), [refreshCatalog]);

  return { configuration, currentConfiguration, configurationSync, catalog, catalogError, catalogSyncedAt, loadCatalog };
}

export type OrderMenu = ReturnType<typeof useOrderMenu>;
