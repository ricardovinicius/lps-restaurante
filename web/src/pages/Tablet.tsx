import { useCallback, useState, type FormEvent } from "react";
import { Link } from "react-router";
import type { Order, TableContext } from "../api";
import { CartItems } from "../components/ordering/CartItems";
import { MenuProducts } from "../components/ordering/MenuProducts";
import { Synchronization } from "../components/orders/Synchronization";
import { TableHistory } from "../components/tablet/TableHistory";
import { currency, tableLabel } from "../ordering/format";
import { useOrdering } from "../ordering/useOrdering";
import { unresolvedRound, useTableContext, useTabletLayout } from "../tablet/useTableContext";

export function Tablet() {
  useTabletLayout();
  const { state, reload } = useTableContext();

  if (state.status === "loading") return <p role="status">Verificando a mesa deste tablet…</p>;

  const unresolved = state.status === "missing" ? unresolvedRound() : undefined;

  if (state.status !== "ready") return <section className="info-card">
    <span className="eyebrow">COMANDA DIGITAL</span>
    <h1>{state.status === "missing" ? "Este tablet não está vinculado a uma mesa." : "Mesa indisponível no momento."}</h1>
    <p>
      {state.status === "missing"
        ? "Peça ao atendimento para vincular o tablet. O vínculo expira e pode ser substituído pelo operador."
        : state.message}
    </p>
    {unresolved && <p role="alert">
      A última rodada da {tableLabel(unresolved.context.table_number)} não teve confirmação (referência{" "}
      <code>{unresolved.pending.key}</code>). Informe essa referência ao atendimento antes de enviar outra.
    </p>}
    <div className="actions">
      {state.status === "error" && <button className="secondary" onClick={reload}>Tentar novamente</button>}
      <Link className="secondary" to="/comanda/configurar">Vincular mesa (atendimento)</Link>
    </div>
  </section>;

  // Each context has its own cart: re-linking never carries a pending round to another table.
  return <TabletSession key={state.context.context_id} context={state.context} onLost={reload} />;
}

function TabletSession({ context, onLost }: { context: TableContext; onLost: () => void }) {
  const [page, setPage] = useState<"menu" | "history">("menu");
  const [lastOrder, setLastOrder] = useState<Order>();
  const [historyRevision, setHistoryRevision] = useState(0);
  const created = useCallback((order: Order) => {
    setLastOrder(order);
    setHistoryRevision((value) => value + 1);
  }, []);
  const ordering = useOrdering("tablet", context.csrf_token, created, context.context_id);
  const { draft, configuration, busy, fulfillment } = ordering;
  const table = tableLabel(context.table_number);
  const editable = !busy && !draft.pending;
  const locked = !editable || draft.reviewRequired || !fulfillment;
  const count = draft.items.reduce((sum, item) => sum + item.quantity, 0);
  const sendDisabled = locked || !draft.items.length
    || Boolean(ordering.catalogError) || Boolean(ordering.configurationSync.error);
  const canRetry = draft.pending && !draft.pending.operationId && !draft.recoveryRequired;

  function send(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    void ordering.submit();
  }

  return <>
    <section className="tablet-toolbar">
      <div><span className="eyebrow">COMANDA DIGITAL</span><h2>À vontade, a casa é sua.</h2></div>
      <div className="tablet-table">
        <span>Pedido para a mesa</span>
        <strong aria-label="Mesa deste tablet">{table}</strong>
      </div>
      <Link className="secondary" to="/comanda/configurar">Atendimento</Link>
    </section>
    <div className="tablet-tabs" role="group" aria-label="Comanda digital">
      <button className={page === "menu" ? "active" : ""} aria-pressed={page === "menu"} onClick={() => setPage("menu")}>
        Fazer pedido
      </button>
      <button
        className={page === "history" ? "active" : ""} aria-pressed={page === "history"}
        onClick={() => setPage("history")}
      >Já pedi</button>
    </div>
    {lastOrder && <div className="tablet-success" role="status">
      <strong>✓ Pedido #{lastOrder.number} enviado · {table}</strong>
      <span>A cozinha recebeu seu pedido. Você já pode montar a próxima rodada.</span>
    </div>}
    {configuration && !fulfillment && <p role="status" className="info-card">
      A Comanda digital está desabilitada para novos pedidos. O histórico desta mesa continua em “Já pedi”.
    </p>}
    {page === "history"
      ? <TableHistory revision={historyRevision} onLost={onLost} onOrder={() => setPage("menu")} />
      : <>
        <Synchronization error={ordering.configurationSync.error} syncedAt={ordering.configurationSync.syncedAt} />
        {(ordering.feedback || ordering.storageError) && <p role="status" className="info-card">
          {ordering.storageError || ordering.feedback}
        </p>}
        <div className="menu-layout ordering-layout">
          <MenuProducts
            catalog={ordering.catalog} catalogError={ordering.catalogError} onReload={() => void ordering.loadCatalog()}
            items={draft.items} locked={locked} onAdd={(product) => ordering.changeQuantity(product, 1)}
          />
          <aside className="cart" aria-label="Comanda da mesa">
            <div className="cart-header"><h2>Comanda · {table}</h2><span>{count} {count === 1 ? "item" : "itens"}</span></div>
            <form className="cart-content" onSubmit={send}>
              {!draft.items.length && <div className="cart-empty">
                <strong>O que vai ser hoje?</strong><p>Toque no + dos seus favoritos para montar o pedido da mesa.</p>
              </div>}
              <CartItems items={draft.items} locked={locked} onChange={ordering.changeQuantity} />
              <div className="totals"><div className="grand-total">
                <span>Total desta rodada</span><strong>{currency.format(ordering.total / 100)}</strong>
              </div></div>
              {draft.reviewRequired && <button
                type="button" className="secondary" disabled={busy} onClick={() => void ordering.review()}
              >Revisar preços e disponibilidade</button>}
              {draft.pending ? <>
                <p role="status">Rodada pendente de confirmação. Os itens estão preservados.</p>
                <p>Referência do envio: <code>{draft.pending.key}</code>.</p>
                {draft.recoveryRequired && <p>
                  A identificação deste tablet mudou. Confira o resultado desta rodada com o atendimento usando a
                  referência acima antes de enviar outra.
                </p>}
                {canRetry && <button className="primary checkout" disabled={busy}>
                  {busy ? "Enviando…" : "Tentar enviar a mesma rodada"}
                </button>}
              </> : <button className="primary checkout" disabled={sendDisabled}>
                {busy ? "Enviando…" : "Enviar para a cozinha"}
              </button>}
              <p className="cart-note">Pagamento no fechamento · Sem cobrança online</p>
            </form>
          </aside>
        </div>
      </>}
  </>;
}
