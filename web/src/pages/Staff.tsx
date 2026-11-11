import { useEffect, useState, type FormEvent } from "react";
import { Navigate, NavLink, Outlet, useOutletContext } from "react-router";
import { api, ApiError, errorMessage, type Session } from "../api";
import { PageHeading } from "../components";

export function Staff({ role }: { role: Session["role"] }) {
  const [session, setSession] = useState<Session | null>();
  const [feedback, setFeedback] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    let active = true;
    api.session().then(
      (value) => { if (active) setSession(value); },
      (error: unknown) => {
        if (!active) return;
        setSession(null);
        if (!(error instanceof ApiError && error.status === 401)) setFeedback(errorMessage(error));
      },
    );
    return () => { active = false; };
  }, []);

  useEffect(() => {
    if (!session) return;

    const remaining = Date.parse(session.expires_at) - Date.now();
    const timer = setTimeout(() => {
      setSession(null);
      setFeedback("Sua sessão expirou. Entre novamente.");
    }, Math.max(0, remaining));
    return () => clearTimeout(timer);
  }, [session]);

  async function login(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const fields = new FormData(form);
    setBusy(true);
    setFeedback("");
    try {
      setSession(await api.login(String(fields.get("username")), String(fields.get("password"))));
    } catch (error) {
      setFeedback(errorMessage(error));
    } finally {
      form.reset();
      setBusy(false);
    }
  }

  async function logout() {
    if (!session) return;

    setBusy(true);
    setFeedback("");
    try {
      await api.logout(session.csrf_token);
      setSession(null);
    } catch (error) {
      if (error instanceof ApiError && error.status === 401) setSession(null);
      else setFeedback(errorMessage(error));
    } finally {
      setBusy(false);
    }
  }

  if (session === undefined) return <p role="status">Verificando sessão…</p>;
  if (!session) return <>
    <PageHeading title={role === "admin" ? "Acesse a Administração" : "Acesse o Balcão"} />
    <form className="info-card stacked-form login-form" onSubmit={login}>
      <label>Usuário<input name="username" autoComplete="username" maxLength={80} required /></label>
      <label>Senha<input name="password" type="password" autoComplete="current-password" maxLength={256} required /></label>
      {feedback && <p role="alert">{feedback}</p>}
      <button className="primary" disabled={busy}>Entrar</button>
    </form>
  </>;

  return <>
    <div className="staff-bar">
      <span>{session.username} · {session.role === "admin" ? "Administração" : "Balcão"}</span>
      <button className="secondary" disabled={busy} onClick={logout}>Sair</button>
    </div>
    {feedback && <p role="alert">{feedback}</p>}
    {session.role === role ? <Outlet context={session} /> : (
      <section className="info-card">
        <h1>Área restrita</h1>
        <p>Sua conta tem acesso a {session.role === "admin" ? "Administração" : "Balcão"}.</p>
        <NavLink to={session.role === "admin" ? "/admin" : "/balcao"}>Ir para sua área</NavLink>
      </section>
    )}
  </>;
}

export function useStaff() {
  return useOutletContext<Session>();
}

export function AdminLayout() {
  return <>
    <nav className="view-links" aria-label="Administração">
      <NavLink end to="/admin" className={({ isActive }) => isActive ? "primary" : "secondary"}>Configurações</NavLink>
      <NavLink to="/admin/catalogo" className={({ isActive }) => isActive ? "primary" : "secondary"}>Editar cardápio</NavLink>
      <NavLink to="/admin/envios" className={({ isActive }) => isActive ? "primary" : "secondary"}>Envios</NavLink>
    </nav>
    <Outlet context={useStaff()} />
  </>;
}

export function LegacyEntry() {
  const view = new URLSearchParams(location.search).get("view");
  const paths: Record<string, string> = { admin: "/admin", counter: "/balcao", tablet: "/comanda", tv: "/tv" };
  return <Navigate replace to={view && Object.hasOwn(paths, view) ? paths[view] : "/cliente"} />;
}
