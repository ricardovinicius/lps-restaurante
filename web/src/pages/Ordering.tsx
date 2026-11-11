import { useCallback, useEffect, useState, type FormEvent } from "react";
import type { Fulfillment, Order } from "../api";
import { PageHeading } from "../components";
import { OrderFeed } from "../components/orders/OrderFeed";
import { Synchronization } from "../components/orders/Synchronization";
import { currency, fulfillmentNames } from "../ordering/format";
import { useOrdering } from "../ordering/useOrdering";

const fulfillmentChoices: Record<Fulfillment, string> = { pickup: "Retirada no balcão", delivery: "Entrega no endereço" };
const confirmLabels: Record<Fulfillment, string> = { pickup: "Confirmar retirada", delivery: "Confirmar entrega" };

type OrderingProps = {
  csrf?: string;
  staffUsername?: string;
  onCreated?: (order: Order) => void;
};

export function Ordering({ csrf, staffUsername, onCreated }: OrderingProps) {
  const [lastOrder, setLastOrder] = useState<Order>();
  const [search, setSearch] = useState("");
  const [category, setCategory] = useState("");
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
  const products = catalog?.items.filter((product) => (!category || product.category_id === category)
    && product.name.toLocaleLowerCase("pt-BR").includes(search.trim().toLocaleLowerCase("pt-BR"))) ?? [];
  const categories = [...new Map(
    catalog?.items.map((product) => [product.category_id, product.category_name]),
  ).entries()];
  const checkoutDisabled = locked || !draft.items.length || !draft.customerName.trim()
    || (delivery && !draft.address.trim())
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
      Retirada e entrega estão desabilitadas para novos pedidos.
      Os pedidos já confirmados continuam disponíveis para acompanhamento e conclusão.
    </p>}
    {(ordering.feedback || ordering.storageError) && <p role="status" className="info-card">
      {ordering.storageError || ordering.feedback}
    </p>}
    <div className="menu-layout ordering-layout">
      <section aria-label="Produtos do cardápio">
        <div className="toolbar">
          <div className="categories" aria-label="Categorias">
            <button className={!category ? "active" : ""} onClick={() => setCategory("")}>Todos</button>
            {categories.map(([id, name]) => <button
              key={id}
              className={category === id ? "active" : ""}
              onClick={() => setCategory(id)}
            >{name}</button>)}
          </div>
          <input
            className="search" type="search" aria-label="Buscar produtos" placeholder="Buscar produto"
            maxLength={120} value={search} onChange={(event) => setSearch(event.target.value)}
          />
        </div>
        {ordering.catalogError && <div className="info-card">
          <p role="alert">{ordering.catalogError}</p>
          <button className="secondary" onClick={() => void ordering.loadCatalog()}>Recarregar cardápio</button>
        </div>}
        {!catalog && !ordering.catalogError && <p role="status">Carregando cardápio…</p>}
        {catalog && !products.length && <p>Nenhum produto encontrado.</p>}
        <div className="products">
          {products.map((product) => <article className="product" key={product.id}>
            {product.image_url && <div className="product-image">
              <img src={product.image_url} alt="" loading="lazy" />
            </div>}
            <div className="product-body">
              <small>{product.category_name}</small>
              <h3>{product.name}</h3>
              <p>{product.description}</p>
              <div className="product-bottom">
                <strong className="price">{currency.format(product.price_cents / 100)}</strong>
                <button
                  className="add" aria-label={"Adicionar " + product.name}
                  disabled={locked || !product.available
                    || (draft.items.length >= 50 && !draft.items.some((item) => item.product_id === product.id))}
                  onClick={() => ordering.changeQuantity(product, 1)}
                >+</button>
              </div>
            </div>
          </article>)}
        </div>
      </section>
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
          {draft.items.map((item) => <div className="cart-item" key={item.product_id}>
            <div>
              <strong>{item.name}</strong>
              <small>{currency.format(item.unit_price_cents / 100)} por unidade</small>
              <div><small>Subtotal: {currency.format(item.quantity * item.unit_price_cents / 100)}</small></div>
            </div>
            <div className="quantity">
              <button
                type="button" disabled={locked} aria-label={"Diminuir " + item.name}
                onClick={() => ordering.changeQuantity(item, -1)}
              >−</button>
              <span aria-label={"Quantidade de " + item.name}>{item.quantity}</span>
              <button
                type="button" disabled={locked || item.quantity >= 99} aria-label={"Aumentar " + item.name}
                onClick={() => ordering.changeQuantity(item, 1)}
              >+</button>
            </div>
          </div>)}
          <label htmlFor={csrf ? "counter-customer" : "customer-name"}>Nome para identificação</label>
          <input
            id={csrf ? "counter-customer" : "customer-name"} value={draft.customerName}
            required minLength={1} maxLength={120} autoComplete="name" disabled={busy || Boolean(draft.pending)}
            onChange={(event) => ordering.changeName(event.target.value)}
          />
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
