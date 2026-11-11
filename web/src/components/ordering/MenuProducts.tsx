import { useState } from "react";
import type { Product } from "../../api";
import { currency } from "../../ordering/format";
import type { CartItem } from "../../ordering/draft";
import { Synchronization } from "../orders/Synchronization";

type MenuProductsProps = {
  catalog?: { items: Product[] };
  catalogError: string;
  syncedAt?: Date;
  onReload: () => void;
  items: CartItem[];
  locked: boolean;
  onAdd: (product: Product) => void;
};

export function MenuProducts({ catalog, catalogError, syncedAt, onReload, items, locked, onAdd }: MenuProductsProps) {
  const [search, setSearch] = useState("");
  const [category, setCategory] = useState("");
  const term = search.trim().toLocaleLowerCase("pt-BR");
  const products = catalog?.items.filter((product) => (!category || product.category_id === category)
    && product.name.toLocaleLowerCase("pt-BR").includes(term)) ?? [];
  const categories = [...new Map(catalog?.items.map((product) => [product.category_id, product.category_name])).entries()];
  const cartFull = items.length >= 50;

  return <section aria-label="Produtos do cardápio">
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
    {catalogError && <div className="info-card">
      <Synchronization error={catalogError} syncedAt={syncedAt} />
      <button className="secondary" onClick={onReload}>Recarregar cardápio</button>
    </div>}
    {!catalog && !catalogError && <p role="status">Carregando cardápio…</p>}
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
              disabled={locked || !product.available || (cartFull && !items.some((item) => item.product_id === product.id))}
              onClick={() => onAdd(product)}
            >+</button>
          </div>
        </div>
      </article>)}
    </div>
  </section>;
}
