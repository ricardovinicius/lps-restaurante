import { useCallback, useEffect, useState } from "react";
import { api, ApiError, errorMessage, type TableContext } from "../api";
import { storedPendingSend } from "../ordering/draft";

type TableContextState =
  | { status: "loading" }
  | { status: "ready"; context: TableContext }
  | { status: "missing" }
  | { status: "error"; message: string };

const lastContextKey = "mesa-facil-tablet-context";
type KnownContext = Pick<TableContext, "context_id" | "table_number">;

/** Public metadata only: it finds a pending round after the cookie is lost, and never authorizes. */
function rememberContext(context: TableContext) {
  try {
    localStorage.setItem(lastContextKey, JSON.stringify({
      context_id: context.context_id, table_number: context.table_number,
    }));
  } catch {}
}

export function lastTabletContext(): KnownContext | undefined {
  try {
    const value = JSON.parse(localStorage.getItem(lastContextKey) ?? "null") as KnownContext | null;
    if (value && typeof value.context_id === "string" && typeof value.table_number === "number") return value;
  } catch {}

  return undefined;
}

/** A round sent by this browser that was never confirmed, for the current or the last known context. */
export function unresolvedRound(context?: KnownContext) {
  const known = context ?? lastTabletContext();
  const pending = known ? storedPendingSend("tablet", known.context_id) : undefined;
  return known && pending ? { context: known, pending } : undefined;
}

/** The tablet credential is an HttpOnly cookie; the browser only sees its public metadata. */
export function useTableContext() {
  const [state, setState] = useState<TableContextState>({ status: "loading" });
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    let active = true;
    api.currentTableContext().then(
      (context) => {
        if (!active) return;
        rememberContext(context);
        setState({ status: "ready", context });
      },
      (error: unknown) => {
        if (!active) return;
        if (error instanceof ApiError && error.status === 401) setState({ status: "missing" });
        else setState({ status: "error", message: errorMessage(error) });
      },
    );
    return () => { active = false; };
  }, [attempt]);

  const reload = useCallback(() => setAttempt((value) => value + 1), []);

  return { state, reload };
}

/** Prototype tablet styles target body[data-role="tablet"]; apply them only while this route is open. */
export function useTabletLayout() {
  useEffect(() => {
    document.body.dataset.role = "tablet";
    return () => { delete document.body.dataset.role; };
  }, []);
}
