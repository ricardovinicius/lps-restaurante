import { useCallback, useEffect, useState, type FormEvent } from "react";
import type { Fulfillment, Order } from "../api";
import { PageHeading } from "../components";
import { CartItems } from "../components/ordering/CartItems";
import { MenuProducts } from "../components/ordering/MenuProducts";
import { TableSelect } from "../components/ordering/TableSelect";
import { OrderFeed } from "../components/orders/OrderFeed";
import { Synchronization } from "../components/orders/Synchronization";
import { currency, fulfillmentNames, tableLabel } from "../ordering/format";
import { useOrdering } from "../ordering/useOrdering";

const fulfillmentChoices: Record<Fulfillment, string> = {
  pickup: "Retirada no balcão", delivery: "Entrega no endereço", table: "Atendimento na mesa",
};
const confirmLabels: Record<Fulfillment, string> = {
  pickup: "Confirmar retirada", delivery: "Confirmar entrega", table: "Confirmar pedido na mesa",
};

type OrderingProps = {
  csrf?: string;
  staffUsername?: string;
  onCreated?: (order: Order) => void;
};

export function Ordering({ csrf, staffUsername, onCreated }: OrderingProps) {
  const [lastOrder, setLastOrder] = useState<Order>();
  const [verified, setVerified] = useState(false);
  const created = useCallback((order: Order) => {
    setLastOrder(order);
    onCreated?.(order);
  }, [onCreated]);
  const ordering = useOrdering(csrf ? "counter" : "client", csrf, created, staffUsername);
  const { draft, configuration, catalog, busy, fulfillment } = ordering;

  useEffect(() => { setVerified(false); }, [draft.pending?.key, draft.recoveryRequired]);

  const editable = !busy && !draft.pending;
  const locked = !editable || draft.reviewRequired || !fulfillment;
  const delivery = fulfillment === "delivery";
  const atTable = fulfillment === "table";
  const checkoutDisabled = locked || !draft.items.length || !draft.customerName.trim()
    || (delivery && !draft.address.trim()) || (atTable && !draft.table)
    || Boolean(ordering.catalogError) || Boolean(ordering.configurationSync.error);

  function checkout(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    void ordering.submit();
  }

  async function restartAfterVerification() {
    setVerified(false);
    if (await ordering.restartAfterVerification()) setLastOrder(undefined);
  }

  return <>
    {!csrf && <PageHeading title="Nosso cardápio">
      <p>Escolha seus produtos e como prefere receber seu pedido.</p>
    </PageHeading>}
    <Synchronization error={ordering.configurationSync.error} syncedAt={ordering.configurationSync.syncedAt} />
    {configuration && !ordering.fulfillments.length && <p role="status" className="info-card">
      Nenhuma modalidade de atendimento está habilitada para novos pedidos.
      Os pedidos já confirmados continuam disponíveis para acompanhamento e conclusão.
    </p>}
    {(ordering.feedback || ordering.storageError) && <p role="status" className="info-card">
      {ordering.storageError || ordering.feedback}
    </p>}
    <div className="menu-layout ordering-layout">
      <MenuProducts
        catalog={catalog} catalogError={ordering.catalogError} syncedAt={ordering.catalogSyncedAt}
        onReload={() => void ordering.loadCatalog()}
        items={draft.items} locked={locked} onAdd={(product) => ordering.changeQuantity(product, 1)}
      />
      <aside className="cart" aria-label="Seu pedido">
        <div className="cart-header">
          <h2>{csrf ? "Novo pedido" : "Seu pedido"}</h2>
          {fulfillment && <span>{fulfillmentNames[fulfillment]}</span>}
        </div>
        {!draft.pending && ordering.fulfillments.length > 1 && <div className="fulfillment-picker">
          <label htmlFor={csrf ? "counter-fulfillment" : "fulfillment"}>Como você prefere receber?</label>
          <select
            id={csrf ? "counter-fulfillment" : "fulfillment"} value={fulfillment} disabled={!editable}
            onChange={(event) => ordering.changeFulfillment(event.target.value as Fulfillment)}
          >{ordering.fulfillments.map((value) => <option key={value} value={value}>{fulfillmentChoices[value]}</option>)}</select>
        </div>}
        <form className="cart-content" onSubmit={checkout}>
          {!draft.items.length && <div className="cart-empty">
            <strong>Seu carrinho está vazio</strong><p>Adicione produtos para começar.</p>
          </div>}
          <CartItems items={draft.items} locked={locked} onChange={ordering.changeQuantity} />
          <label htmlFor={csrf ? "counter-customer" : "customer-name"}>Nome para identificação</label>
          <input
            id={csrf ? "counter-customer" : "customer-name"} value={draft.customerName}
            required minLength={1} maxLength={120} autoComplete="name" disabled={busy || Boolean(draft.pending)}
            onChange={(event) => ordering.changeName(event.target.value)}
          />
          {atTable && (draft.pending
            ? draft.table && <p>{tableLabel(draft.table.number)}</p>
            : <TableSelect
              id={csrf ? "counter-table" : "customer-table"} value={draft.table} disabled={!editable}
              revision={configuration?.revision} onChange={ordering.changeTable}
            />)}
          {delivery && <>
            <label htmlFor={csrf ? "counter-address" : "delivery-address"}>Endereço de entrega</label>
            <input
              id={csrf ? "counter-address" : "delivery-address"} value={ordering.address}
              required maxLength={500} autoComplete="street-address" placeholder="Rua, número e bairro"
              disabled={!editable} onChange={(event) => ordering.changeAddress(event.target.value)}
            />
          </>}
          <div className="totals">
            <div><span>Subtotal</span><span>{currency.format(ordering.subtotal / 100)}</span></div>
            {delivery && <div><span>Taxa de entrega</span><span>{currency.format(ordering.fee / 100)}</span></div>}
            <div className="grand-total">
              <span>Total</span><strong>{currency.format(ordering.total / 100)}</strong>
            </div>
          </div>
          {draft.reviewRequired && <button
            type="button" className="secondary" disabled={busy} onClick={() => void ordering.review()}
          >Revisar preços e disponibilidade</button>}
          {draft.pending ? <>
            <p role="status">Envio pendente de confirmação. Os itens estão preservados e a edição está bloqueada.</p>
            <p>
              Referência do envio: <code>{draft.pending.key}</code>.
              Informe esta referência no Balcão para verificar o resultado.
            </p>
            {draft.recoveryRequired && <>
              <button
                className="secondary" type="button" disabled={busy}
                onClick={() => void ordering.recoverIdentification()}
              >Recuperar identificação</button>
              <p>
                Se a identificação não puder ser recuperada, confira o resultado com o atendimento antes de iniciar
                outro pedido. O envio anterior pode já ter sido aceito.
              </p>
              <label>
                <input type="checkbox" checked={verified} onChange={(event) => setVerified(event.target.checked)} />
                Já conferi o resultado do envio anterior com o atendimento
              </label>
              <button
                className="secondary" type="button" disabled={busy || !verified}
                onClick={() => void restartAfterVerification()}
              >Iniciar novo atendimento</button>
            </>}
            {!draft.pending.operationId && <button className="primary checkout" disabled={busy}>
              {busy ? "Confirmando…" : "Tentar confirmar o mesmo envio"}
            </button>}
          </> : <button className="primary checkout" disabled={checkoutDisabled}>
            {busy ? "Confirmando…" : confirmLabels[fulfillment ?? "pickup"]}
          </button>}
          <p className="cart-note">
            O valor, a taxa e a disponibilidade serão validados ao confirmar.
          </p>
        </form>
      </aside>
    </div>
    {!csrf && <OrderFeed lastOrderId={lastOrder?.id} />}
  </>;
}
