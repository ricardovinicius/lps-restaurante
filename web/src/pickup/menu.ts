import { useCallback, useEffect, useRef, useState } from "react";
import { api, errorMessage, type Configuration } from "../api";
import { usePolling } from "../hooks/usePolling";
import { emptyDraft, type PickupDraftStore } from "./draft";

export async function readCatalog() {
  const first = await api.products(false);
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

export function usePickupMenu(store: PickupDraftStore, setFeedback: (message: string) => void) {
  const { mounted, currentDraft, saveDraft } = store;
  const [configuration, setConfiguration] = useState<Configuration>();
  const currentConfiguration = useRef(configuration);
  const [catalog, setCatalog] = useState<Awaited<ReturnType<typeof readCatalog>>>();
  const [catalogError, setCatalogError] = useState("");

  const readConfiguration = useCallback(async () => {
    const value = await api.configuration();
    if (!mounted.current) return value;

    currentConfiguration.current = value;
    setConfiguration(value);
    const current = currentDraft.current;

    if (current.configurationRevision !== value.revision && !current.pending) {
      if (current.items.length) {
        setFeedback("A configuração mudou. O carrinho foi reiniciado; revise as opções disponíveis.");
      }

      saveDraft({ ...emptyDraft(), configurationRevision: value.revision });
    }

    return value;
  }, [saveDraft, mounted, currentDraft, setFeedback]);
  const configurationSync = usePolling(readConfiguration);

  const loadCatalog = useCallback(async () => {
    try {
      const value = await readCatalog();
      if (!mounted.current) return;

      setCatalog(value);
      setCatalogError("");
      return value;
    } catch (error) {
      if (mounted.current) setCatalogError(errorMessage(error));
    }
  }, [mounted]);

  useEffect(() => { void loadCatalog(); }, [loadCatalog, configuration?.revision]);

  return { configuration, currentConfiguration, configurationSync, catalog, catalogError, loadCatalog };
}

export type PickupMenu = ReturnType<typeof usePickupMenu>;
