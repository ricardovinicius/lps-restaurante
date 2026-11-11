import { useEffect, useState } from "react";
import { api, errorMessage, type DiningTable } from "../../api";
import type { TableChoice } from "../../ordering/draft";
import { tableLabel } from "../../ordering/format";

type TableSelectProps = {
  id: string;
  value?: TableChoice;
  disabled: boolean;
  revision?: number;
  onChange: (table: TableChoice | undefined) => void;
};

/** Available tables only; Mesas is consulted just when the table modality is chosen. */
export function TableSelect({ id, value, disabled, revision, onChange }: TableSelectProps) {
  const [tables, setTables] = useState<DiningTable[]>();
  const [error, setError] = useState("");
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    let active = true;
    api.tables().then(
      (page) => { if (active) { setTables(page.items); setError(""); } },
      (failure: unknown) => { if (active) setError(errorMessage(failure)); },
    );
    return () => { active = false; };
  }, [revision, attempt]);

  const options = [...(tables ?? [])].sort((first, second) => first.number - second.number);
  const missing = value && tables && !tables.some((table) => table.id === value.id);
  const empty = tables !== undefined && !tables.length;

  return <>
    <label htmlFor={id}>Mesa</label>
    <select
      id={id} required value={value?.id ?? ""} disabled={disabled || !tables || (empty && !value)}
      onChange={(event) => {
        const table = options.find((option) => option.id === event.target.value);
        onChange(table ? { id: table.id, number: table.number } : undefined);
      }}
    >
      <option value="">{tables ? "Escolha a mesa" : "Carregando mesas…"}</option>
      {value && missing && <option value={value.id}>{tableLabel(value.number)} (indisponível)</option>}
      {options.map((table) => <option key={table.id} value={table.id}>{tableLabel(table.number)}</option>)}
    </select>
    {empty && <p role="status">Nenhuma mesa disponível para novos pedidos no momento.</p>}
    {error && <p role="alert">
      {error} <button type="button" className="secondary" onClick={() => setAttempt((value) => value + 1)}>
        Recarregar mesas
      </button>
    </p>}
  </>;
}
