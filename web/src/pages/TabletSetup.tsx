import { useCallback, useState, type FormEvent } from "react";
import { useNavigate } from "react-router";
import { api, ApiError, errorMessage } from "../api";
import { Load, PageHeading } from "../components";
import { tableLabel } from "../ordering/format";
import { unresolvedRound, useTableContext } from "../tablet/useTableContext";
import { useStaff } from "./Staff";

/** Operator-only: binds this browser to a table, then ends the operator session here. */
export function TabletSetup() {
  const { csrf_token } = useStaff();
  const navigate = useNavigate();
  const { state, reload } = useTableContext();
  const [tableId, setTableId] = useState("");
  const [busy, setBusy] = useState(false);
  const [feedback, setFeedback] = useState("");
  const [verified, setVerified] = useState(false);
  const [linked, setLinked] = useState(false);
  const readTables = useCallback(() => api.tables(), []);
  const current = state.status === "ready" ? state.context : undefined;

  // A lost or expired cookie still leaves the round's reference in this browser.
  // Until the current context is known, a pending round cannot be ruled out.
  const checking = state.status === "loading";
  const unresolved = checking ? undefined : unresolvedRound(current);
  const blocked = checking || (Boolean(unresolved) && (Boolean(current) || !verified));

  /** The Comanda is only released once no operator session remains on this device. */
  async function endOperatorSession() {
    try {
      await api.logout(csrf_token);
      navigate("/comanda");
    } catch (error) {
      // 401: the session is already gone, e.g. a logout whose response was lost.
      if (error instanceof ApiError && error.status === 401) {
        navigate("/comanda");
        return;
      }

      setLinked(true);
      setFeedback("A mesa foi vinculada, mas a sessão do operador continua ativa neste navegador ("
        + errorMessage(error) + "). Encerre a sessão antes de entregar o tablet.");
      setBusy(false);
    }
  }

  async function link(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setFeedback("");

    try {
      await api.provisionTable(tableId, csrf_token);
    } catch (error) {
      setFeedback(errorMessage(error));
      setBusy(false);
      return;
    }

    await endOperatorSession();
  }

  async function retryLogout() {
    setBusy(true);
    setFeedback("");
    await endOperatorSession();
  }

  async function unlink() {
    setBusy(true);
    setFeedback("");

    try {
      await api.revokeTableContext(csrf_token);
      setFeedback("Tablet desvinculado.");
      reload();
    } catch (error) {
      setFeedback(errorMessage(error));
    } finally {
      setBusy(false);
    }
  }

  if (linked) return <>
    <PageHeading title="Vincular Comanda digital" />
    <section className="info-card">
      <p role="alert">{feedback}</p>
      <button className="primary" disabled={busy} onClick={() => void retryLogout()}>
        Encerrar sessão do operador e abrir a Comanda
      </button>
    </section>
  </>;

  return <>
    <PageHeading title="Vincular Comanda digital">
      <p>Escolha a mesa deste tablet. Depois de vincular, a conta do operador é encerrada neste navegador.</p>
    </PageHeading>
    <section className="info-card">
      <h2>{current ? "Vinculado à " + tableLabel(current.table_number) : "Tablet sem mesa vinculada"}</h2>
      {current && <p>Vínculo válido até {new Date(current.expires_at).toLocaleString("pt-BR")}.</p>}
      <p>
        O histórico “Já pedi” é permanente por mesa: inclui visitas anteriores e pedidos feitos pelo Cliente e pelo
        Balcão para essa mesa. Use um tablet por mesa; abas do mesmo navegador compartilham o vínculo.
      </p>
      {unresolved && <p role="alert">
        Há uma rodada sem confirmação da {tableLabel(unresolved.context.table_number)} (referência{" "}
        <code>{unresolved.pending.key}</code>). Confira o resultado em Verificação de envios antes de trocar ou
        remover o vínculo; ela pode já ter sido aceita.
      </p>}
      {unresolved && !current && <label>
        <input type="checkbox" checked={verified} onChange={(event) => setVerified(event.target.checked)} />
        Já conferi o resultado dessa rodada em Verificação de envios
      </label>}
      {current && <button className="secondary" disabled={busy || blocked} onClick={() => void unlink()}>
        Desvincular tablet
      </button>}
    </section>
    {feedback && <p role="status">{feedback}</p>}
    <Load read={readTables}>{(page) => !page.items.length ? <p role="status" className="info-card">
      Nenhuma mesa disponível para vincular. Disponibilize uma mesa no Balcão ou, se nenhuma estiver cadastrada,
      peça para rodar o seed de Mesas.
    </p> : <form className="filter-bar" onSubmit={link}>
      <label>Mesa
        <select required value={tableId} onChange={(event) => setTableId(event.target.value)}>
          <option value="">Escolha a mesa</option>
          {[...page.items].sort((first, second) => first.number - second.number).map((table) => (
            <option key={table.id} value={table.id}>{tableLabel(table.number)}</option>
          ))}
        </select>
      </label>
      <button className="primary" disabled={busy || !tableId || blocked}>
        {checking ? "Verificando o tablet…" : "Vincular tablet à mesa"}
      </button>
    </form>}</Load>
  </>;
}
