import { useCallback, useEffect, useRef, useState } from "react";
import { api, ApiError, errorMessage, isCheckoutRejection, type Order } from "../api";
import { emptyDraft, type Draft, type Pending, type OrderDraftStore } from "./draft";
import { selectedFulfillment } from "./fulfillment";
import type { OrderMenu } from "./menu";

type CheckoutOptions = {
  store: OrderDraftStore;
  menu: OrderMenu;
  origin: Order["origin"];
  csrf?: string;
  tableContextId?: string;
  onCreated: (order: Order) => void;
  setFeedback: (message: string) => void;
};

const identityFailures = ["customer_recovery_required", "invalid_customer_context", "invalid_table_context",
  "table_context_changed"];

function usePendingOperation(
  operationId: string | undefined,
  origin: Order["origin"],
  store: OrderDraftStore,
  confirmed: (order: Order) => void,
  reject: (message: string) => void,
  setFeedback: (message: string) => void,
) {
  const { currentDraft, saveDraft } = store;

  useEffect(() => {
    if (!operationId) return;
    const id = operationId;

    let active = true;
    let timer: ReturnType<typeof setTimeout>;

    async function pollOperation() {
      try {
        const operation = await api.operation(id, origin === "client");
        if (!active) return;

        if (operation.state === "succeeded" && operation.order) {
          confirmed(operation.order);
          return;
        }

        if (operation.state === "rejected" && isCheckoutRejection(operation.error?.code)) {
          reject(operation.error?.message ?? "O pedido não foi aceito.");
          return;
        }

        setFeedback(operation.state === "needs_attention" || operation.state === "rejected"
          ? "O envio precisa de verificação no atendimento. O carrinho continua preservado."
          : "Confirmando seu pedido. Aguarde antes de fazer outro envio.");
      } catch (error) {
        if (active) {
          if (error instanceof ApiError && (error.code === "customer_recovery_required" || error.status === 404)) {
            saveDraft({ ...currentDraft.current, recoveryRequired: true });
          }
          setFeedback(errorMessage(error) + " O envio continua pendente de confirmação.");
        }
      }
      if (active) timer = setTimeout(pollOperation, 3000);
    }

    void pollOperation();
    return () => {
      active = false;
      clearTimeout(timer);
    };
  }, [operationId, confirmed, reject, origin, saveDraft, currentDraft, setFeedback]);
}

export function useOrderCheckout({ store, menu, origin, csrf, tableContextId, onCreated, setFeedback }: CheckoutOptions) {
  const { draft, currentDraft, saveDraft, mounted, archiveVerifiedAttempt } = store;
  const { configuration, currentConfiguration, catalog } = menu;
  const [busy, setBusy] = useState(false);
  const sending = useRef(false);

  const confirmed = useCallback((order: Order) => {
    if (!mounted.current) return;

    saveDraft({
      ...emptyDraft(),
      fulfillment: currentDraft.current.fulfillment,
      table: currentDraft.current.table,
      configurationRevision: currentConfiguration.current?.revision,
    });
    // The Comanda shows its own confirmation banner for each round.
    setFeedback(origin === "tablet" ? "" : "Pedido #" + order.number + " confirmado. Acompanhe o andamento abaixo.");
    onCreated(order);
  }, [saveDraft, onCreated, mounted, currentConfiguration, currentDraft, setFeedback, origin]);

  const reject = useCallback((message: string) => {
    if (!mounted.current) return;

    saveDraft({ ...currentDraft.current, pending: undefined, reviewRequired: true });
    setFeedback(message + " Revise o carrinho antes de confirmar novamente.");
  }, [saveDraft, mounted, currentDraft, setFeedback]);

  usePendingOperation(draft.pending?.operationId, origin, store, confirmed, reject, setFeedback);

  function identificationFor(current: Draft) {
    // The tablet is identified by its credential: no name and no table in the body.
    if (origin === "tablet") return {};
    return { customer_name: current.customerName.trim() };
  }

  function newPending(current: Draft): Pending | undefined {
    const fulfillment = selectedFulfillment(current, configuration, origin);
    const address = current.address.trim();
    if (!configuration || !catalog || !fulfillment || current.reviewRequired || !current.items.length) return undefined;
    if (origin !== "tablet" && !current.customerName.trim()) return undefined;
    if (fulfillment === "delivery" && !address) return undefined;
    if (fulfillment === "table" && origin !== "tablet" && !current.table) return undefined;

    return {
      key: crypto.randomUUID(),
      tableContextId,
      payload: {
        configuration_revision: configuration.revision,
        catalog_revision: catalog.revision,
        origin, fulfillment, ...identificationFor(current),
        ...(fulfillment === "delivery" ? { address } : {}),
        ...(fulfillment === "table" && origin !== "tablet" ? { table_id: current.table!.id } : {}),
        items: current.items.map((item) => ({
          product_id: item.product_id,
          quantity: item.quantity,
          expected_unit_price_cents: item.unit_price_cents,
        })),
      },
    };
  }

  async function submit() {
    if (sending.current) return;

    const current = currentDraft.current;
    if (current.pending?.operationId) return;

    const pending = current.pending ?? newPending(current);
    if (!pending) return;
    if (!saveDraft({ ...current, pending })) return;

    sending.current = true;
    setBusy(true);
    setFeedback("");

    try {
      if (origin === "client") {
        const context = await api.customerContext();
        if (!mounted.current) return;
        if (pending.customerContextId && pending.customerContextId !== context.context_id) {
          saveDraft({ ...currentDraft.current, recoveryRequired: true });
          setFeedback("A identificação deste navegador mudou. Procure o atendimento para verificar o envio anterior "
            + "antes de criar outro pedido.");
          return;
        }
        pending.customerContextId = context.context_id;
        if (!saveDraft({ ...currentDraft.current, pending })) return;
      }
      const owner = origin === "tablet" ? pending.tableContextId : pending.customerContextId;
      const result = await api.createOrder(pending.payload, pending.key, csrf, owner);
      if (!mounted.current) return;
      if ("operation_id" in result) {
        if (result.state === "succeeded" && result.order) confirmed(result.order);
        else if (result.state === "rejected" && isCheckoutRejection(result.error?.code)) {
          reject(result.error?.message ?? "O pedido não foi aceito.");
        } else {
          saveDraft({ ...currentDraft.current, pending: { ...pending, operationId: result.operation_id } });
          setFeedback("Confirmando seu pedido. Aguarde antes de fazer outro envio.");
        }
      } else confirmed(result);
    } catch (error) {
      if (!mounted.current) return;
      if (error instanceof ApiError && isCheckoutRejection(error.code)) reject(error.message);
      else if (error instanceof ApiError && identityFailures.includes(error.code ?? "")) {
        saveDraft({ ...currentDraft.current, recoveryRequired: true });
        setFeedback(error.message);
      } else {
        setFeedback(errorMessage(error) + " Seu carrinho foi preservado. Tente confirmar o mesmo envio novamente.");
      }
    } finally {
      sending.current = false;
      if (mounted.current) setBusy(false);
    }
  }

  async function recoverIdentification() {
    setBusy(true);

    try {
      const context = await api.customerContext(true);
      if (!mounted.current) return;
      if (currentDraft.current.pending?.customerContextId !== context.context_id) {
        throw new Error("Verifique o resultado do envio anterior com o atendimento usando a referência abaixo.");
      }
      saveDraft({ ...currentDraft.current, recoveryRequired: false });
      setFeedback("Identificação recuperada. Continue a confirmação do mesmo envio.");
    } catch (error) {
      if (mounted.current) setFeedback(errorMessage(error));
    } finally {
      if (mounted.current) setBusy(false);
    }
  }

  async function restartAfterVerification() {
    if (busy || !currentDraft.current.recoveryRequired) return;

    setBusy(true);

    try {
      archiveVerifiedAttempt();
      if (origin === "client") await api.startNewCustomerContext();
      if (!mounted.current) return;
      saveDraft({ ...currentDraft.current, pending: undefined, recoveryRequired: false, reviewRequired: true });
      setFeedback("Novo atendimento iniciado. A tentativa anterior continua registrada para consulta no atendimento. "
        + "Revise o carrinho antes de confirmar outro pedido.");
      return true;
    } catch (error) {
      if (mounted.current) setFeedback(errorMessage(error));
    } finally {
      if (mounted.current) setBusy(false);
    }
  }

  return { busy, setBusy, submit, recoverIdentification, restartAfterVerification };
}
