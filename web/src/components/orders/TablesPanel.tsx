import { useCallback, useState } from "react";
import { api, ApiError, errorMessage, type DiningTable } from "../../api";
import { usePolling } from "../../hooks/usePolling";
import { tableLabel } from "../../ordering/format";

/** Availability only blocks new table orders; accepted orders keep their table. */
export function TablesPanel({ csrf }: { csrf: string }) {
  const read = useCallback(async () => {
    const page = await api.tables(true);
    return page.items.sort((first, second) => first.number - second.number);
  }, []);
  const sync = usePolling(read);
  const [busy, setBusy] = useState<string>();
  const [feedback, setFeedback] = useState("");

  async function toggle(table: DiningTable) {
    setBusy(table.id);
    setFeedback("");

    try {
      await api.setTableAvailability(table, !table.available, csrf);
    } catch (error) {
      setFeedback(error instanceof ApiError && error.code === "table_changed"
        ? tableLabel(table.number) + " foi alterada em outra sessão. Confira o estado atualizado."
        : errorMessage(error));
    } finally {
      setBusy(undefined);
      sync.refresh();
    }
  }

  const empty = sync.value !== undefined && !sync.value.length;

  return <details className="order-section" open={empty || undefined}>
    <summary>Disponibilidade das mesas</summary>
    <p>Mesas indisponíveis não recebem novos pedidos. Pedidos já aceitos continuam na fila.</p>
    {sync.error && <p role="alert">{sync.error} Os dados podem estar desatualizados.</p>}
    {feedback && <p role="status">{feedback}</p>}
    {empty && <p role="alert">
      Nenhuma mesa cadastrada. Pedidos para mesa e a Comanda só funcionam depois de criar as mesas com{" "}
      <code>docker compose exec tables python -m mesa_platform.seed tables</code>.
    </p>}
    <div className="tables-grid">
      {sync.value?.map((table) => <article className="info-card" key={table.id}>
        <strong>{tableLabel(table.number)}</strong>
        <span>{table.available ? "Disponível" : "Indisponível"}</span>
        <button
          className="secondary" disabled={Boolean(busy) || Boolean(sync.error)}
          aria-label={(table.available ? "Marcar como indisponível a " : "Disponibilizar a ") + tableLabel(table.number)}
          onClick={() => void toggle(table)}
        >{busy === table.id ? "Atualizando…" : table.available ? "Marcar indisponível" : "Disponibilizar"}</button>
      </article>)}
    </div>
  </details>;
}
