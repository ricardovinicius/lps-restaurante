import { createRoot } from "react-dom/client";
import { BrowserRouter, Link, NavLink, Outlet, Route, Routes } from "react-router";
import type { Configuration } from "./api";
import { PageHeading } from "./components";
import { ConfigurationProvider, useConfiguration } from "./configuration/ConfigurationProvider";
import { AdministrativeSummary } from "./components/admin/AdministrativeSummary";
import { Dispatches } from "./components/orders/Dispatches";
import { Catalog } from "./pages/Catalog";
import { Counter } from "./pages/Counter";
import { Ordering } from "./pages/Ordering";
import { Operations } from "./pages/Operations";
import { Settings } from "./pages/Settings";
import { Tablet } from "./pages/Tablet";
import { TabletSetup } from "./pages/TabletSetup";
import { TV } from "./pages/TV";
import { AdminLayout, LegacyEntry, Staff, useStaff } from "./pages/Staff";
import "../../prototypes/mesa-facil/dist/style.css";
import "./style.css";

function OptionalAreas({ features }: Pick<Configuration, "features">) {
  return <>
    {features.tablet && <NavLink to="/comanda">Comanda digital</NavLink>}
    {features.tv && <NavLink to="/tv">Painel de TV</NavLink>}
  </>;
}

function Layout() {
  const { configuration } = useConfiguration();

  return <>
    <aside className="sidebar">
      <Link className="brand" to="/cliente">
        <span aria-hidden="true" className="brand-mark">m<span>·</span></span>
        <span>mesa fácil</span>
      </Link>
      <nav id="role-nav" aria-label="Áreas do Mesa Fácil">
        <NavLink to="/cliente">Cardápio</NavLink>
        <NavLink to="/admin">Administração</NavLink>
        <NavLink to="/balcao">Balcão</NavLink>
        {configuration && <OptionalAreas features={configuration.features} />}
      </nav>
    </aside>
    <div className="shell"><main><Outlet /></main></div>
  </>;
}

function SettingsRoute() {
  const { csrf_token } = useStaff();
  const { accept } = useConfiguration();

  return <><AdministrativeSummary /><Settings csrf={csrf_token} onSaved={accept} /></>;
}

function CatalogRoute() {
  return <Catalog csrf={useStaff().csrf_token} />;
}

createRoot(document.getElementById("root")!).render(
  <BrowserRouter>
    <ConfigurationProvider>
    <Routes>
      <Route element={<Layout />}>
        <Route index element={<LegacyEntry />} />
        <Route path="cliente" element={<Ordering />} />
        <Route path="admin" element={<Staff role="admin" />}>
          <Route element={<AdminLayout />}>
            <Route index element={<SettingsRoute />} />
            <Route path="catalogo" element={<CatalogRoute />} />
            <Route path="envios" element={<><Operations /><Dispatches /></>} />
          </Route>
        </Route>
        <Route path="balcao" element={<Staff role="operator" />}>
          <Route index element={<Counter />} />
        </Route>
        <Route path="comanda" element={<Tablet />} />
        <Route path="comanda/configurar" element={<Staff role="operator" />}>
          <Route index element={<TabletSetup />} />
        </Route>
        <Route path="tv" element={<TV />} />
        <Route path="*" element={<PageHeading title="Página não encontrada"><Link to="/cliente">Abrir cardápio</Link></PageHeading>} />
      </Route>
    </Routes>
    </ConfigurationProvider>
  </BrowserRouter>,
);
