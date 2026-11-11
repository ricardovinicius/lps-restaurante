import { useCallback, useState } from "react";
import { PageHeading } from "../components";
import { OrderFeed } from "../components/orders/OrderFeed";
import { Operations } from "./Operations";
import { Pickup } from "./Pickup";
import { useStaff } from "./Staff";

export function Counter() {
  const { csrf_token, username } = useStaff();
  const [queueRevision, setQueueRevision] = useState(0);
  const refreshQueue = useCallback(() => setQueueRevision((value) => value + 1), []);

  return <>
    <PageHeading title="Balcão"><p>Organize os pedidos e acompanhe cada etapa da retirada.</p></PageHeading>
    <details className="new-counter-order">
      <summary>Criar pedido de retirada</summary>
      <Pickup csrf={csrf_token} staffUsername={username} onCreated={refreshQueue} />
    </details>
    <OrderFeed csrf={csrf_token} refreshKey={queueRevision} />
    <Operations />
  </>;
}
