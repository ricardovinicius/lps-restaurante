import type { CartItem } from "../../ordering/draft";
import { currency } from "../../ordering/format";

type CartItemsProps = {
  items: CartItem[];
  locked: boolean;
  onChange: (item: CartItem, change: number) => void;
};

export function CartItems({ items, locked, onChange }: CartItemsProps) {
  return <>
    {items.map((item) => <div className="cart-item" key={item.product_id}>
      <div>
        <strong>{item.name}</strong>
        <small>{currency.format(item.unit_price_cents / 100)} por unidade</small>
        <div><small>Subtotal: {currency.format(item.quantity * item.unit_price_cents / 100)}</small></div>
      </div>
      <div className="quantity">
        <button
          type="button" disabled={locked} aria-label={"Diminuir " + item.name}
          onClick={() => onChange(item, -1)}
        >−</button>
        <span aria-label={"Quantidade de " + item.name}>{item.quantity}</span>
        <button
          type="button" disabled={locked || item.quantity >= 99} aria-label={"Aumentar " + item.name}
          onClick={() => onChange(item, 1)}
        >+</button>
      </div>
    </div>)}
  </>;
}
