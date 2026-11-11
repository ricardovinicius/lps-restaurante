import { createContext, useContext, useState } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter, Link, NavLink, Outlet, Route, Routes } from "react-router";
import { api, type Configuration } from "./api";
import { Load, PageHeading } from "./components";
import { Catalog } from "./pages/Catalog";
import { Settings } from "./pages/Settings";
import { AdminLayout, LegacyEntry, Staff, useStaff } from "./pages/Staff";
import "../../prototypes/mesa-facil/dist/style.css";
import "./style.css";

const ConfigurationChanged = createContext<(value: Configuration) => void>(() => {});

function OptionalAreas({ features }: Pick<Configuration, "features">) {
  return <>
    {features.tablet && <NavLink to="/comanda">Comanda digital</NavLink>}
    {features.tv && <NavLink to="/tv">Painel de TV</NavLink>}
  </>;
}

function Layout() {
  const [configuration, setConfiguration] = useState<Configuration>();

  return <ConfigurationChanged.Provider value={setConfiguration}>
    <aside className="sidebar">
      <Link className="brand" to="/cliente">
        <span aria-hidden="true" className="brand-mark">m<span>·</span></span>
        <span>mesa fácil</span>
      </Link>
      <nav id="role-nav" aria-label="Áreas do Mesa Fácil">
        <NavLink to="/cliente">Cardápio</NavLink>
        <NavLink to="/admin">Administração</NavLink>
        <NavLink to="/balcao">Balcão</NavLink>
        {configuration
          ? <OptionalAreas features={configuration.features} />
          : <Load read={api.configuration}>{({ features }) => <OptionalAreas features={features} />}</Load>}
      </nav>
    </aside>
    <div className="shell"><main><Outlet /></main></div>
  </ConfigurationChanged.Provider>;
}

function SettingsRoute() {
  const { csrf_token } = useStaff();
  const onSaved = useContext(ConfigurationChanged);

  return <Settings csrf={csrf_token} onSaved={onSaved} />;
}

function CatalogRoute() {
  return <Catalog csrf={useStaff().csrf_token} />;
}

function PendingArea({ feature, title }: { feature: "tablet" | "tv"; title: string }) {
  return <>
    <PageHeading title={title} />
    <Load read={api.configuration}>{({ features }) => (
      <p>{features[feature] ? "Esta área será conectada em uma próxima etapa." : "Este recurso está desabilitado."}</p>
    )}</Load>
  </>;
}

createRoot(document.getElementById("root")!).render(
  <BrowserRouter>
    <Routes>
      <Route element={<Layout />}>
        <Route index element={<LegacyEntry />} />
        <Route path="cliente" element={<Catalog />} />
        <Route path="admin" element={<Staff role="admin" />}>
          <Route element={<AdminLayout />}>
            <Route index element={<SettingsRoute />} />
            <Route path="catalogo" element={<CatalogRoute />} />
          </Route>
        </Route>
        <Route path="balcao" element={<Staff role="operator" />}>
          <Route index element={<PageHeading title="Balcão"><p>A fila será conectada na etapa de retirada.</p></PageHeading>} />
        </Route>
        <Route path="comanda" element={<PendingArea feature="tablet" title="Comanda digital" />} />
        <Route path="tv" element={<PendingArea feature="tv" title="Painel de TV" />} />
        <Route path="*" element={<PageHeading title="Página não encontrada"><Link to="/cliente">Abrir cardápio</Link></PageHeading>} />
      </Route>
    </Routes>
  </BrowserRouter>,
);
