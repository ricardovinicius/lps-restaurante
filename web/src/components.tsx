import { useEffect, useState, type ReactNode } from "react";
import { errorMessage } from "./api";

export function PageHeading({ title, children }: { title: string; children?: ReactNode }) {
  return <section className="page-heading"><div><h1>{title}</h1>{children}</div></section>;
}

export function Load<T>({ read, children }: {
  read: () => Promise<T>;
  children: (value: T) => ReactNode;
}) {
  const [result, setResult] = useState<{ value: T } | { error: string }>();
  const [attempt, retry] = useState(0);

  useEffect(() => {
    let active = true;
    read().then(
      (value) => { if (active) setResult({ value }); },
      (error: unknown) => { if (active) setResult({ error: errorMessage(error) }); },
    );
    return () => { active = false; };
  }, [read, attempt]);

  if (!result) return <p role="status">Carregando…</p>;
  if ("error" in result) return (
    <section className="info-card">
      <p role="alert">{result.error}</p>
      <button className="secondary" onClick={() => { setResult(undefined); retry(attempt + 1); }}>
        Tentar novamente
      </button>
    </section>
  );

  return children(result.value);
}
