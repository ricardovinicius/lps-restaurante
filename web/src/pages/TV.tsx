import { useEffect, useState } from "react";
import { api, ApiError, errorMessage, type TVPage } from "../api";
import { Synchronization } from "../components/orders/Synchronization";
import { usePolling } from "../hooks/usePolling";
import { fulfillmentNames, tableLabel } from "../ordering/format";

function Column({ title, page, ready = false }: { title: string; page: TVPage; ready?: boolean }) {
  const remaining = page.total - page.items.length;

  return <section className={"tv-column" + (ready ? " ready" : "")} aria-label={title}>
    <div className="tv-heading"><h2>{title}</h2><span>{page.total} {page.total === 1 ? "pedido" : "pedidos"}</span></div>
    <div className="tv-numbers" aria-live="polite">
      {page.items.map((ticket) => <div className="ticket" key={ticket.number}>
        <small>PEDIDO</small><strong>{ticket.number}</strong>
        <span>{ticket.fulfillment === "table"
          ? ticket.table_number ? tableLabel(ticket.table_number) : "Mesa não identificada"
          : fulfillmentNames[ticket.fulfillment]}</span>
      </div>)}
      {!page.items.length && <p className="tv-empty">Novos pedidos aparecerão aqui.</p>}
    </div>
    {remaining > 0 && <p className="tv-overflow">+{remaining} {ready ? "prontos" : "em preparo"} além dos exibidos</p>}
  </section>;
}

export function TV() {
  const sync = usePolling(api.tv);
  const [feedback, setFeedback] = useState("");
  const disabled = sync.failure instanceof ApiError
    && sync.failure.status === 403 && sync.failure.code === "feature_disabled";

  useEffect(() => {
    document.body.dataset.role = "tv";
    return () => { delete document.body.dataset.role; };
  }, []);

  async function fullscreen() {
    try {
      if (document.fullscreenElement) await document.exitFullscreen();
      else await document.documentElement.requestFullscreen();
    } catch (error) {
      setFeedback(errorMessage(error));
    }
  }

  return <>
    <div className="tv-top">
      <div><span className="tv-brand">mesa fácil<span>·</span></span><p>ACOMPANHE SEU PEDIDO</p></div>
      <div className="tv-tools">
        <button className="secondary" onClick={() => void fullscreen()}>Tela cheia</button>
      </div>
    </div>
    {feedback && <p role="status">{feedback}</p>}
    <Synchronization error={disabled ? "" : sync.error} syncedAt={sync.syncedAt} hasDisplayedData={false} />
    {disabled && <p role="alert" className="sync-status">O painel de TV está desabilitado.</p>}
    {!sync.value && !sync.error && <p role="status">Carregando painel…</p>}
    {sync.value && !sync.failure && <div className="tv-board">
      <Column title="Em preparo" page={sync.value.preparing} />
      <Column title="Prontos" page={sync.value.ready} ready />
    </div>}
  </>;
}
