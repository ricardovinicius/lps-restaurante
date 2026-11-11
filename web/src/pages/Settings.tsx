import { useState, type FormEvent } from "react";
import { api, ApiError, errorMessage, type Configuration, type Features, type Preset } from "../api";
import { Load, PageHeading } from "../components";

const groups = [
  { title: "Modalidades de atendimento", options: [
    { key: "pickup", name: "Retirada no balcão", text: "O cliente retira o pedido no estabelecimento." },
    { key: "delivery", name: "Entrega", text: "Receba pedidos com endereço de entrega." },
    { key: "tables", name: "Atendimento em mesa", text: "Vincule pedidos à mesa do cliente." },
  ] },
  { title: "Recursos opcionais", options: [
    { key: "tablet", name: "Comanda digital", text: "O cliente faz pedidos na mesa. Requer atendimento em mesa." },
    { key: "tv", name: "Painel de TV", text: "Exiba números de pedidos em preparo e prontos." },
  ] },
] as const;

const names: Record<string, string> = {
  lanchonete: "Lanchonete", delivery: "Delivery", restaurante: "Restaurante", personalizado: "Personalizado",
};

function sameFeatures(left: Features, right: Features) {
  return Object.keys(left).every((key) => left[key as keyof Features] === right[key as keyof Features]);
}

async function readSettings() {
  return Promise.all([api.configuration(), api.presets()]);
}

type SettingsAccess = { csrf: string; onSaved: (value: Configuration) => void };

export function Settings({ csrf, onSaved }: SettingsAccess) {
  return <>
    <PageHeading title="Seu negócio, do seu jeito.">
      <p>Escolha as funcionalidades da sua operação.</p>
    </PageHeading>
    <Load read={readSettings}>
      {([saved, presets]) => <SettingsForm initial={saved} presets={presets} csrf={csrf} onSaved={onSaved} />}
    </Load>
  </>;
}

function SettingsForm({ initial, presets, csrf, onSaved }: SettingsAccess & {
  initial: Configuration;
  presets: Preset[];
}) {
  const [saved, setSaved] = useState(initial);
  const [draft, setDraft] = useState(initial.features);
  const [feedback, setFeedback] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);
  const [conflict, setConflict] = useState(false);

  const dirty = !sameFeatures(saved.features, draft);
  const errors = [];
  if (!draft.pickup && !draft.delivery && !draft.tables) errors.push("Selecione pelo menos uma modalidade de atendimento.");
  if (draft.tablet && !draft.tables) errors.push("Comanda digital exige atendimento em mesa.");

  const name = presets.find((preset) => sameFeatures(preset.features, draft))?.name ?? "personalizado";
  const services = ["Configuração", "Catálogo", "Pedidos"];
  if (draft.delivery) services.push("Entregas");
  if (draft.tables) services.push("Mesas");

  async function save(event: FormEvent) {
    event.preventDefault();
    if (busy || conflict || !dirty || errors.length) return;

    setBusy(true);
    setFeedback("");
    setNotice("");
    try {
      const updated = await api.saveConfiguration(draft, saved.revision, csrf);
      setSaved(updated);
      onSaved(updated);
      setDraft(updated.features);
      setNotice("Configuração salva.");
    } catch (error) {
      const changed = error instanceof ApiError && error.status === 409;
      setConflict(changed);
      setFeedback(changed ? "Outra sessão salvou uma alteração. Atualize a versão salva para revisar seu rascunho." : errorMessage(error));
    } finally {
      setBusy(false);
    }
  }

  async function refresh() {
    setBusy(true);
    setFeedback("");
    try {
      const updated = await api.configuration();
      setSaved(updated);
      onSaved(updated);
      setConflict(false);
      setNotice("Versão salva atualizada. Confira o rascunho antes de salvar.");
    } catch (error) {
      setFeedback(errorMessage(error));
    } finally {
      setBusy(false);
    }
  }

  async function download() {
    setFeedback("");
    try {
      const preset = await api.exportConfiguration();
      const blob = new Blob([JSON.stringify(preset, null, 2) + "\n"], { type: "application/json" });
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = "mesa-facil-" + preset.name + ".json";
      link.click();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
    } catch (error) {
      setFeedback(errorMessage(error));
    }
  }

  return <form onSubmit={save}>
    <section className="settings-intro">
      <div><h2>Modelos de configuração</h2><p>Carregue um modelo no rascunho e ajuste os recursos antes de salvar.</p></div>
      <div className="preset-options">{presets.map((preset) => (
        <button className="secondary" type="button" key={preset.name} disabled={busy}
          onClick={() => { setDraft(preset.features); setNotice(""); }}>
          {names[preset.name]}
        </button>
      ))}</div>
    </section>
    <div className="settings-layout">
      <div>
        <section className="settings-group">
          <h2>Funcionalidades obrigatórias</h2>
          <div className="core-features">
            <div><strong>Cardápio digital</strong><p>Produtos, categorias, preços e disponibilidade.</p></div>
            <div><strong>Pedidos e operação</strong><p>Carrinho, acompanhamento e fila do balcão.</p></div>
          </div>
        </section>
        {groups.map(({ title, options }) => (
          <section className="settings-group" key={title}>
            <div className="section-heading"><h2>{title}</h2></div>
            <div className="feature-grid">{options.map(({ key, name, text }) => (
              <label className={draft[key] ? "feature-card selected" : "feature-card"} key={key}>
                <div className="feature-card-top">
                  <strong>{name}</strong>
                  <input type="checkbox" aria-label={name} checked={draft[key]} disabled={busy}
                    onChange={(event) => { setDraft({ ...draft, [key]: event.target.checked }); setNotice(""); }} />
                </div>
                <p>{text}</p>
              </label>
            ))}</div>
          </section>
        ))}
      </div>
      <aside className="settings-summary">
        <span className="eyebrow">PRÉVIA DA COMPOSIÇÃO</span>
        <h2>{names[name]}</h2>
        <p>Serviços necessários</p>
        <ul>{services.map((service) => <li key={service}>{service}</li>)}</ul>
        <div className="config-validation" role="status">
          {errors.length ? errors.map((error) => <p className="config-error" key={error}>{error}</p>) : <p>Combinação válida</p>}
        </div>
        {feedback && <p role="alert">{feedback}</p>}
        {notice && <p role="status">{notice}</p>}
        {conflict && <button type="button" className="secondary" disabled={busy} onClick={refresh}>Atualizar versão salva</button>}
        <button className="primary" disabled={busy || conflict || !dirty || errors.length > 0}>Salvar configuração</button>
        <button type="button" className="secondary" disabled={busy || conflict || !dirty}
          onClick={() => { setDraft(saved.features); setFeedback(""); setNotice("Alterações descartadas."); }}>
          Descartar alterações
        </button>
        <button type="button" className="secondary" disabled={busy} onClick={download}>Exportar configuração salva</button>
        <small>Revisão salva {saved.revision}{dirty && " · Rascunho com alterações"}</small>
      </aside>
    </div>
  </form>;
}
