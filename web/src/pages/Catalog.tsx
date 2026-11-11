import { useState, type FormEvent } from "react";
import { api, ApiError, errorMessage, type Product } from "../api";
import { Load, PageHeading } from "../components";

const currency = new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" });
const readAdmin = () => api.products(true);
const readPublic = () => api.products(false);
type Page = Awaited<ReturnType<typeof api.products>>;

export function Catalog({ csrf }: { csrf?: string }) {
  return <>
    <PageHeading title={csrf ? "Gerencie seu cardápio" : "Nosso cardápio"}>
      {csrf && <p>Ajuste os preços e a disponibilidade dos produtos.</p>}
    </PageHeading>
    <Load read={csrf ? readAdmin : readPublic}>
      {(page) => <CatalogList initial={page} csrf={csrf} />}
    </Load>
  </>;
}

function CatalogList({ initial, csrf }: { initial: Page; csrf?: string }) {
  const [page, setPage] = useState(initial);
  const [editing, setEditing] = useState<string>();
  const [busy, setBusy] = useState(false);
  const [feedback, setFeedback] = useState("");
  const [notice, setNotice] = useState("");
  const [conflict, setConflict] = useState(false);

  async function load(cursor?: string) {
    setBusy(true);
    setFeedback("");
    setNotice("");
    try {
      const result = await api.products(Boolean(csrf), cursor);
      setPage(result);
      setConflict(false);
      setEditing(undefined);
    } catch (error) {
      setFeedback(errorMessage(error));
    } finally {
      setBusy(false);
    }
  }

  async function save(event: FormEvent<HTMLFormElement>, product: Product) {
    event.preventDefault();
    if (!csrf || busy || conflict) return;

    const fields = new FormData(event.currentTarget);
    const price = String(fields.get("price")).replace(",", ".");
    if (!/^\d+(\.\d{1,2})?$/.test(price) || Number(price) <= 0 || Number(price) > 21474836.47) {
      setFeedback("Informe um preço positivo com até duas casas decimais.");
      return;
    }

    setBusy(true);
    setFeedback("");
    setNotice("");
    try {
      const result = await api.saveProduct(product.id, page.revision, Math.round(Number(price) * 100), fields.has("available"), csrf);
      setPage({
        ...page, revision: result.revision,
        items: page.items.map((item) => item.id === product.id ? result.product : item),
      });
      setEditing(undefined);
      setNotice("Produto atualizado.");
    } catch (error) {
      const changed = error instanceof ApiError && error.status === 409;
      setConflict(changed);
      setFeedback(changed ? "Outra sessão alterou o catálogo. Recarregue para editar a versão atual." : errorMessage(error));
    } finally {
      setBusy(false);
    }
  }

  return <>
    {feedback && <p role="alert" className="config-error">{feedback}</p>}
    {notice && <p role="status">{notice}</p>}
    {conflict && <button className="secondary" disabled={busy} onClick={() => load()}>Recarregar catálogo</button>}
    {!page.items.length && <p>Nenhum produto disponível.</p>}
    <div className="products">
      {page.items.map((product) => (
        <article className="product" key={product.id}>
          {product.image_url && <div className="product-image"><img src={product.image_url} alt="" loading="lazy" /></div>}
          <div className="product-body">
            <small>{product.category_name}</small>
            <h3>{product.name}</h3>
            <p>{product.description}</p>
            {editing === product.id ? (
              <form className="stacked-form" onSubmit={(event) => save(event, product)}>
                <label>Preço (R$)<input name="price" inputMode="decimal" required defaultValue={(product.price_cents / 100).toFixed(2)} /></label>
                <label className="availability"><input name="available" type="checkbox" defaultChecked={product.available} /> Disponível</label>
                <div className="actions">
                  <button className="primary" disabled={busy || conflict}>Salvar</button>
                  <button className="secondary" type="button" disabled={busy} onClick={() => setEditing(undefined)}>Cancelar</button>
                </div>
              </form>
            ) : (
              <div className="product-bottom">
                <div><strong className="price">{currency.format(product.price_cents / 100)}</strong>
                  {csrf && <div>{product.available ? "Disponível" : "Indisponível"}</div>}
                </div>
                {csrf && <button className="secondary" aria-label={"Editar " + product.name} disabled={busy || conflict}
                  onClick={() => { setEditing(product.id); setFeedback(""); setNotice(""); }}>Editar</button>}
              </div>
            )}
          </div>
        </article>
      ))}
    </div>
    <div className="actions pagination">
      {page !== initial && <button className="secondary" disabled={busy} onClick={() => load()}>Primeira página</button>}
      {page.next_cursor && <button className="secondary" disabled={busy || conflict} onClick={() => load(page.next_cursor ?? undefined)}>Próxima página</button>}
    </div>
  </>;
}
