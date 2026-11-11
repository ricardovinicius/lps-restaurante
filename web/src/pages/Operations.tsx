import { useCallback, useState, type FormEvent } from "react";
import { api, errorMessage, type OrderOperation } from "../api";
import { usePolling } from "../hooks/usePolling";
import { currency, fulfillmentNames, identification, stateNames } from "../ordering/format";
import { useStaff } from "./Staff";

const operationNames = { pending: "Em processamento", needs_attention: "Precisa de atenção", rejected: "Rejeitado", succeeded: "Confirmado" };

export function Operations() {
  const { role, csrf_token } = useStaff();
  const [state, setState] = useState("needs_attention");
  const [reference, setReference] = useState("");
  const [search, setSearch] = useState("");
  const [cursor, setCursor] = useState<string>();
  const [selected, setSelected] = useState<string>();
  const [feedback, setFeedback] = useState("");
  const [busy, setBusy] = useState(false);
  const read = useCallback(async () => {
    const [page, detail] = await Promise.all([
      api.operations(state, reference, cursor),
      selected ? api.operation(selected) : Promise.resolve(undefined),
    ]);
    return { page, detail };
  }, [state, reference, cursor, selected]);
  const sync = usePolling(read);

  function find(event: FormEvent) {
    event.preventDefault();
    setReference(search.trim());
    setCursor(undefined);
    setSelected(undefined);
    sync.refresh();
  }

  async function resume(operation: OrderOperation) {
    setBusy(true);
    setFeedback("");
    try {
      await api.resumeOperation(operation.operation_id, csrf_token);
      setFeedback("Retomada solicitada. O resultado será atualizado automaticamente.");
      sync.refresh();
    } catch (error) {
      setFeedback(errorMessage(error));
    } finally {
      setBusy(false);
    }
  }

  const detail = sync.value?.detail;
  return <section className="order-section" aria-label="Verificação de envios">
    <div className="section-heading"><h2>Verificação de envios</h2>
      <button className="secondary" onClick={sync.refresh}>Atualizar envios</button></div>
    <p>Consulte tentativas que ainda não entraram na fila e verifique o resultado pela referência informada pelo cliente.</p>
    <form className="filter-bar" onSubmit={find}>
      <label>Referência do envio<input value={search} onChange={(event) => setSearch(event.target.value)}
        maxLength={36} pattern="[a-fA-F0-9-]{36}" /></label>
      <button className="secondary">Buscar envio</button>
      <label>Estado do envio<select value={state} onChange={(event) => {
        setState(event.target.value); setReference(""); setSearch(""); setCursor(undefined); setSelected(undefined);
      }}>{Object.entries(operationNames).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label>
    </form>
    {reference && <p>A busca pela referência inclui todos os estados.</p>}
    {sync.error && <p role="alert">{sync.error} Os dados podem estar desatualizados.</p>}
    {sync.syncedAt && <p className="sync-status">Última sincronização: {sync.syncedAt.toLocaleTimeString("pt-BR")}</p>}
    {feedback && <p role="status">{feedback}</p>}
    {sync.value?.page.items.length === 0 && <p>Nenhum envio encontrado.</p>}
    {sync.value?.page.items.map((operation) => <article className="info-card" key={operation.operation_id}>
      <h3>{identification(operation)} · {fulfillmentNames[operation.fulfillment]} · {operationNames[operation.state]}</h3>
      <p>Referência: <code>{operation.idempotency_key}</code></p>
      <p>{new Date(operation.created_at).toLocaleString("pt-BR")} · Tentativas: {operation.attempts}</p>
      {operation.error && <p>{operation.error.message}</p>}
      <button className="secondary" onClick={() => setSelected(operation.operation_id)}>Verificar envio</button>
    </article>)}
    <div className="actions pagination">
      {cursor && <button className="secondary" onClick={() => setCursor(undefined)}>Primeira página de envios</button>}
      {sync.value?.page.next_cursor && <button className="secondary" onClick={() => setCursor(sync.value!.page.next_cursor!)}>Próximos envios</button>}
    </div>
    {detail && <section className="info-card" aria-label="Resultado do envio">
      <h3>{operationNames[detail.state]}</h3>
      {detail.error && <p>{detail.error.message}</p>}
      {detail.order && <p>Pedido #{detail.order.number} · {identification(detail.order)} · {stateNames[detail.order.state]} · {currency.format(detail.order.total_cents / 100)}</p>}
      {detail.state === "needs_attention" && (role === "admin"
        ? <button className="primary" disabled={busy || Boolean(sync.error)} onClick={() => void resume(detail)}>Retomar envio</button>
        : <p>Solicite a retomada a um administrador pela área Administração → Envios.</p>)}
    </section>}
  </section>;
}
