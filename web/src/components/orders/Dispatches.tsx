import { useCallback, useState } from "react";
import { api, errorMessage, type DispatchSummary } from "../../api";
import { usePolling } from "../../hooks/usePolling";
import { useStaff } from "../../pages/Staff";

const dispatchNames = { pending: "Em confirmação", needs_attention: "Precisa de atenção", succeeded: "Confirmado" };

export function Dispatches() {
  const { role, csrf_token } = useStaff();
  const [state, setState] = useState<DispatchSummary["state"]>("needs_attention");
  const [cursor, setCursor] = useState<string>();
  const [feedback, setFeedback] = useState("");
  const [busy, setBusy] = useState(false);
  const read = useCallback(() => api.dispatches(state, cursor), [state, cursor]);
  const sync = usePolling(read);
  const items = sync.value?.items ?? [];

  async function resume(dispatch: DispatchSummary) {
    setBusy(true);
    setFeedback("");

    try {
      await api.resumeDispatch(dispatch.operation_id, csrf_token);
      setFeedback("Retomada do pedido #" + dispatch.order_number + " solicitada. O estado será atualizado automaticamente.");
      sync.refresh();
    } catch (error) {
      setFeedback(errorMessage(error));
    } finally {
      setBusy(false);
    }
  }

  return <section className="order-section" aria-label="Saídas para entrega">
    <div className="section-heading">
      <h2>Saídas para entrega</h2>
      <button className="secondary" onClick={sync.refresh}>Atualizar saídas</button>
    </div>
    <p>Saídas registradas no Balcão que ainda aguardam a confirmação do serviço de Entregas.</p>
    <div className="filter-bar">
      <label>Estado da saída<select value={state} onChange={(event) => {
        setState(event.target.value as DispatchSummary["state"]);
        setCursor(undefined);
      }}>{Object.entries(dispatchNames).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label>
    </div>
    {sync.error && <p role="alert">{sync.error} Os dados podem estar desatualizados.</p>}
    {sync.syncedAt && <p className="sync-status">Última sincronização: {sync.syncedAt.toLocaleTimeString("pt-BR")}</p>}
    {feedback && <p role="status">{feedback}</p>}
    {sync.value && !items.length && <p>Nenhuma saída encontrada.</p>}
    {items.map((dispatch) => <article className="info-card" key={dispatch.operation_id}>
      <h3>Pedido #{dispatch.order_number} · {dispatchNames[dispatch.state]}</h3>
      <p>{dispatch.customer_name} · Tentativas: {dispatch.attempts}</p>
      <p>Registrada em {new Date(dispatch.created_at).toLocaleString("pt-BR")}</p>
      {dispatch.error && <p>{dispatch.error.message}</p>}
      {dispatch.state === "needs_attention" && (role === "admin"
        ? <button className="primary" disabled={busy || Boolean(sync.error)} onClick={() => void resume(dispatch)}>
          Retomar saída do pedido #{dispatch.order_number}
        </button>
        : <p>Solicite a retomada a um administrador pela área Administração → Envios.</p>)}
    </article>)}
    <div className="actions pagination">
      {cursor && <button className="secondary" onClick={() => setCursor(undefined)}>Primeira página de saídas</button>}
      {sync.value?.next_cursor && <button
        className="secondary" onClick={() => setCursor(sync.value!.next_cursor!)}
      >Próximas saídas</button>}
    </div>
  </section>;
}
