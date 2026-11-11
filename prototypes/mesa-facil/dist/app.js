const products = [
  {
    id: 1,
    name: "Burger da Casa",
    category: "Burgers",
    price: 32.9,
    description: "Blend artesanal, cheddar, alface e nosso molho especial no pão brioche.",
    photo: "photo-1568901346375-23c9450c58cd",
    tag: "O MAIS PEDIDO",
  },
  {
    id: 2,
    name: "Smash Duplo",
    category: "Burgers",
    price: 36.9,
    description: "Dois smash burgers, queijo derretido e picles. Simples e irresistível.",
    photo: "photo-1550547660-d9450f859349",
    tag: "FEITO NA CHAPA",
  },
  {
    id: 3,
    name: "Burger do Jardim",
    category: "Burgers",
    price: 29.9,
    description: "Hambúrguer de grão-de-bico, folhas frescas e maionese de ervas.",
    photo: "photo-1520072959219-c595dc870360",
    tag: "VEGETARIANO",
  },
  {
    id: 4,
    name: "Batata da Casa",
    category: "Porções",
    price: 19.9,
    description: "Douradinha, crocante e finalizada com alecrim e sal da casa.",
    photo: "photo-1573080496219-bb080dd4f877",
    tag: "PARA COMPARTILHAR",
  },
  {
    id: 5,
    name: "Onion Rings",
    category: "Porções",
    price: 22.9,
    description: "Anéis de cebola empanados, acompanhados de molho da casa.",
    photo: "photo-1639024471283-03518883512d",
    tag: "",
  },
  {
    id: 6,
    name: "Limonada fresca",
    category: "Bebidas",
    price: 10.9,
    description: "Limão espremido na hora, gelo e um toque de hortelã. 400 ml.",
    photo: "photo-1513558161293-cdaf765edfd7",
    tag: "REFRESCANTE",
  },
  {
    id: 7,
    name: "Chá gelado da Casa",
    category: "Bebidas",
    price: 9.9,
    description: "Chá artesanal com limão e especiarias, servido bem gelado. 400 ml.",
    photo: "photo-1556679343-c7306c1976bc",
    tag: "",
  },
  {
    id: 8,
    name: "Brownie quentinho",
    category: "Sobremesas",
    price: 16.9,
    description: "Chocolate intenso, casquinha crocante e um final feliz para o pedido.",
    photo: "photo-1606313564200-e75d5e30476c",
    tag: "UM DOCE FINAL",
  },
];
const variants = {
  express: {
    name: "Lanchonete",
    mode: "Retirada no balcão",
    hint: "Fica pronto em 20–30 min",
    feature: "Catálogo + Pedidos",
    fee: 0,
  },
  delivery: {
    name: "Delivery",
    mode: "Entrega no endereço",
    hint: "Estimativa de 35–50 min",
    feature: "+ Microsserviço de entregas",
    fee: 5,
  },
  salao: {
    name: "Restaurante",
    mode: "Atendimento na mesa",
    hint: "Seu pedido vai direto para a cozinha",
    feature: "+ Microsserviço de mesas",
    fee: 0,
  },
};
const storageKey = "mesa-facil-prototype-v1";
let orders = [];
try {
  const data = JSON.parse(localStorage.getItem(storageKey) || "[]");
  if (Array.isArray(data))
    orders = data.filter(
      (o) =>
        o &&
        variants[o.variant] &&
        Array.isArray(o.items) &&
        Number.isFinite(o.total) &&
        Number.isInteger(o.stage) &&
        o.stage >= 0 &&
        o.stage <= 3,
    );
} catch {}
let variant = "express",
  page = "menu",
  category = "Todos",
  query = "",
  cart = {},
  customer = "",
  address = "",
  table = "1";
const roles = {
  tablet: "Comanda digital",
  client: "Cliente",
  admin: "Administração",
  counter: "Balcão",
  tv: "Painel de TV",
};
const defaultPages = {
  tablet: "menu",
  client: "menu",
  admin: "settings",
  counter: "orders",
  tv: "tv",
};
const params = new URLSearchParams(location.search);
let role = roles[params.get("view")] ? params.get("view") : "client";
const configurationKey = "mesa-establishment-variant-v1";
const featureDefinitions = [
  {
    id: "pickup",
    title: "Retirada no balcão",
    description: "O cliente faz o pedido e retira no estabelecimento.",
    icon: "↗",
    group: "Atendimento",
  },
  {
    id: "delivery",
    title: "Entrega",
    description: "Pedidos com endereço e taxa fixa de R$ 5,00.",
    icon: "♧",
    group: "Atendimento",
  },
  {
    id: "tables",
    title: "Atendimento em mesa",
    description: "Identifica a mesa e organiza os pedidos do salão.",
    icon: "▦",
    group: "Atendimento",
  },
  {
    id: "tablet",
    title: "Comanda digital",
    description: "Cardápio para tablet, novas rodadas e histórico da mesa.",
    icon: "▤",
    group: "Experiência",
  },
  {
    id: "tv",
    title: "Painel de TV",
    description: "Exibe os pedidos em preparo e prontos para o público.",
    icon: "▣",
    group: "Experiência",
  },
];
const presets = {
  express: { pickup: true, delivery: false, tables: false, tablet: false, tv: true },
  delivery: { pickup: false, delivery: true, tables: false, tablet: false, tv: false },
  salao: { pickup: false, delivery: false, tables: true, tablet: true, tv: true },
};
function configErrors(f) {
  const errors = [];
  if (!f.pickup && !f.delivery && !f.tables)
    errors.push("Selecione pelo menos uma modalidade de atendimento.");
  if (f.tablet && !f.tables) errors.push("Comanda digital exige Atendimento em mesa.");
  return errors;
}
function readFeatures() {
  try {
    const raw = localStorage.getItem(configurationKey);
    if (presets[raw]) return { ...presets[raw] };
    const parsed = JSON.parse(raw);
    if (parsed?.version === 2 && parsed.features) {
      const f = Object.fromEntries(
        featureDefinitions.map((item) => [item.id, parsed.features[item.id] === true]),
      );
      if (!configErrors(f).length) return f;
    }
  } catch {}
  return { ...presets.express };
}
let features = readFeatures();
let draftFeatures = { ...features };
function modes(f = features) {
  return ["express", "delivery", "salao"].filter(
    (v) => f[{ express: "pickup", delivery: "delivery", salao: "tables" }[v]],
  );
}
function configuredVariant() {
  return modes(readFeatures())[0];
}
function featureSignature(f) {
  return featureDefinitions.map((item) => Number(f[item.id])).join("");
}
function configurationName(f = features) {
  const match = Object.keys(presets).find(
    (key) => featureSignature(presets[key]) === featureSignature(f),
  );
  return match ? variants[match].name : "Personalizado";
}
function enabledRole(r) {
  return r === "tablet" ? features.tablet && features.tables : r === "tv" ? features.tv : true;
}
function servicesFor(f) {
  return [
    "catalog",
    "orders",
    ...(f.delivery ? ["deliveries"] : []),
    ...(f.tables ? ["table-service"] : []),
  ];
}
variant = role === "tablet" && features.tables ? "salao" : modes()[0];
page = defaultPages[role];

let myOrderIds = [];
try {
  myOrderIds = JSON.parse(sessionStorage.getItem("mesa-my-orders") || "[]");
} catch {}
if (!Array.isArray(myOrderIds)) myOrderIds = [];
const catalogKey = "mesa-catalog-v1";
function loadCatalog() {
  try {
    const data = JSON.parse(localStorage.getItem(catalogKey) || "{}");
    for (const p of products) {
      const entry = data[p.id];
      if (entry && Number.isFinite(entry.price) && entry.price > 0) p.price = entry.price;
      p.available = entry?.available !== false;
    }
  } catch {}
}
loadCatalog();
function updateUrl() {
  const url = new URL(location.href);
  url.searchParams.set("view", role);
  url.searchParams.delete("variant");
  history.replaceState(null, "", url);
}
function roleLink(target) {
  return "?view=" + target;
}
function loadOrders() {
  try {
    const value = JSON.parse(localStorage.getItem(storageKey) || "[]");
    if (Array.isArray(value))
      orders = value.filter(
        (o) =>
          o &&
          variants[o.variant] &&
          Array.isArray(o.items) &&
          Number.isFinite(o.total) &&
          Number.isInteger(o.stage) &&
          o.stage >= 0 &&
          o.stage <= 3,
      );
  } catch {}
}
const money = (n) =>
  new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" }).format(n);
const esc = (s) =>
  String(s).replace(
    /[&<>"']/g,
    (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c],
  );
const count = () => Object.values(cart).reduce((a, b) => a + b, 0);
const subtotal = () => products.reduce((sum, p) => sum + p.price * (cart[p.id] || 0), 0);
function save() {
  try {
    localStorage.setItem(storageKey, JSON.stringify(orders));
  } catch {
    toast("Armazenamento indisponível. Pedidos mantidos nesta sessão.");
  }
}
let toastTimer;
function toast(message) {
  const el = document.querySelector("#toast");
  el.textContent = message;
  el.classList.add("visible");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => el.classList.remove("visible"), 2800);
}
function applyConfiguration() {
  const next = readFeatures();
  if (featureSignature(next) === featureSignature(features)) return;
  features = next;
  draftFeatures = { ...next };
  variant = role === "tablet" && features.tables ? "salao" : modes()[0];
  cart = {};
  customer = "";
  address = "";
  tabletLastOrder = null;
  updateUrl();
  render();
  toast("Funcionalidades atualizadas. Carrinho reiniciado.");
}
function render() {
  document.body.dataset.role = role;
  document.querySelector("#role-select").innerHTML = Object.entries(roles)
    .filter(([r]) => enabledRole(r) || r === role)
    .map(([r, label]) => `<option value="${r}">${label}</option>`)
    .join("");
  document.querySelector("#role-select").value = role;
  document.title = "Mesa Fácil · " + roles[role];
  const menus = {
    tablet: [
      ["menu", "Fazer pedido"],
      ["tablet-orders", "Já pedi"],
    ],
    client: [
      ["menu", "Cardápio"],
      ["tracking", "Meus pedidos"],
    ],
    admin: [
      ["admin", "Resumo"],
      ["settings", "Configurações"],
      ["catalog", "Gerenciar cardápio"],
      ["architecture", "Linha de produtos"],
    ],
    counter: [
      ["orders", "Fila de pedidos"],
      ["menu", "Pedido no balcão"],
    ],
    tv: [],
  };
  document.querySelector("#role-nav").innerHTML = menus[role]
    .map(
      ([id, label]) =>
        `<button data-page="${id}" class="${page === id ? "active" : ""}">${label}</button>`,
    )
    .join("");

  document.querySelectorAll("[data-variant]").forEach((b) => {
    b.classList.toggle("active", b.dataset.variant === variant);
    b.setAttribute("aria-pressed", b.dataset.variant === variant);
  });
  document
    .querySelectorAll("[data-page]")
    .forEach((b) => b.classList.toggle("active", b.dataset.page === page));
  const titles = {
    menu: ["Cardápio", "O que vamos servir hoje?", "Comida de verdade. Pedidos sem complicação."],
    orders: [
      "Pedidos",
      "Cada pedido, no seu tempo.",
      "Acompanhe o preparo e faça o próximo sabor acontecer.",
    ],
    architecture: [
      "Linha de produtos",
      "Uma base. Muitos jeitos de servir.",
      "Explore as funcionalidades que compõem cada produto.",
    ],
  };
  Object.assign(titles, {
    admin: [
      "Administração",
      "Seu restaurante, por inteiro.",
      "Acompanhe a operação e gerencie o que chega ao cliente.",
    ],
    catalog: [
      "Cardápio",
      "Cada sabor, sob seu controle.",
      "Ajuste os preços e a disponibilidade do cardápio.",
    ],
    tracking: [
      "Meus pedidos",
      "Agora é com a nossa cozinha.",
      "Acompanhe os pedidos feitos nesta aba.",
    ],
    tv: ["Painel de TV", "Seu pedido está chegando.", "Acompanhe seu número no painel."],
  });
  if (role === "tablet")
    titles.menu = [
      "Comanda digital",
      "Escolha. Toque. Peça.",
      "Seu pedido vai direto para a cozinha.",
    ];
  titles["tablet-orders"] = [
    "Já pedi",
    "Tudo o que chegou à cozinha.",
    "Confira os pedidos e acompanhe o preparo da sua mesa.",
  ];
  titles.settings = [
    "Configurações",
    "Seu negócio, do seu jeito.",
    "Escolha as funcionalidades que fazem sentido para a sua operação.",
  ];
  const t = titles[page];
  document.querySelector("#crumb").textContent = t[0];
  document.querySelector("#page-title").textContent = t[1];
  document.querySelector("#page-subtitle").textContent = t[2];

  document.querySelector("#view").innerHTML = {
    settings: settingsView,
    menu: menuView,
    orders: ordersView,
    architecture: architectureView,
    admin: adminView,
    catalog: catalogView,
    tracking: trackingView,
    "tablet-orders": tabletOrdersView,
    tv: tvView,
  }[page]();
  if (!enabledRole(role)) {
    document.querySelector("#view").innerHTML =
      `<section class="info-card disabled-area"><h2>${roles[role]} não está habilitado.</h2><p>Habilite este recurso nas configurações do estabelecimento para utilizá-lo.</p><a class="secondary" href="?view=admin">Abrir configurações →</a></section>`;
  } else if (page === "menu") renderProducts();
}
function fulfillmentPicker() {
  const available = modes();
  if (available.length < 2) return "";
  return `<div class="fulfillment-picker"><label for="fulfillment">Como você prefere receber?</label><select id="fulfillment">${available.map((v) => `<option value="${v}" ${variant === v ? "selected" : ""}>${variants[v].mode}</option>`).join("")}</select></div>`;
}
function settingsView() {
  const errors = configErrors(draftFeatures),
    dirty = featureSignature(features) !== featureSignature(draftFeatures);
  return `<form id="settings-form"><section class="settings-intro"><div><span class="eyebrow">MONTE SEU PRODUTO</span><h2>Comece com um modelo. Ajuste à sua maneira.</h2><p>Combine canais de atendimento e recursos. As alterações só entram em vigor ao salvar.</p></div><div class="preset-options">${Object.keys(
    presets,
  )
    .map(
      (key) =>
        `<button type="button" class="secondary" data-preset="${key}">${variants[key].name}</button>`,
    )
    .join(
      "",
    )}</div></section><div class="settings-layout"><div><section class="settings-group"><div class="section-heading"><h2>O essencial, sempre incluído</h2><span>OBRIGATÓRIO</span></div><div class="core-features"><div><strong>▦ Cardápio digital</strong><p>Produtos, categorias, preços e disponibilidade.</p></div><div><strong>▤ Pedidos e operação</strong><p>Carrinho, acompanhamento e fila do balcão.</p></div></div></section>${[
    "Atendimento",
    "Experiência",
  ]
    .map(
      (group, i) =>
        `<section class="settings-group"><div class="section-heading"><h2>${i === 0 ? "01 · Como você atende?" : "02 · Como você quer servir?"}</h2><span>${i === 0 ? "UMA OU MAIS OPÇÕES" : "OPCIONAIS"}</span></div><div class="feature-grid">${featureDefinitions
          .filter((f) => f.group === group)
          .map(
            (f) =>
              `<label class="feature-card ${draftFeatures[f.id] ? "selected" : ""}"><div class="feature-card-top"><span class="feature-icon">${f.icon}</span><input type="checkbox" data-feature="${f.id}" ${draftFeatures[f.id] ? "checked" : ""} aria-label="${f.title}"></div><strong>${f.title}</strong><p>${f.description}</p><small>${f.id === "tablet" ? "Requer atendimento em mesa" : f.group === "Atendimento" ? "Pode combinar com outras modalidades" : "Recurso independente"}</small></label>`,
          )
          .join("")}</div></section>`,
    )
    .join(
      "",
    )}</div><aside class="settings-summary"><span class="eyebrow">SEU PRODUTO</span><h2>${configurationName(draftFeatures)}</h2><p>Prévia da composição</p><ul><li>✓ Cardápio digital</li><li>✓ Pedidos e operação</li>${featureDefinitions
    .filter((f) => draftFeatures[f.id])
    .map((f) => `<li>✓ ${f.title}</li>`)
    .join(
      "",
    )}</ul><div class="config-validation" role="status">${errors.length ? errors.map((e) => `<p class="config-error">! ${e}</p>`).join("") : "<p>✓ Combinação válida</p>"}</div><button class="primary" type="submit" ${errors.length || !dirty ? "disabled" : ""}>Salvar configuração</button><button class="secondary" type="button" id="discard-settings" ${dirty ? "" : "disabled"}>Descartar alterações</button><small>${dirty ? "Alterações ainda não salvas." : "Tudo salvo."} Ao salvar mudanças, os carrinhos em andamento são reiniciados. Pedidos existentes são preservados.</small></aside></div></form>`;
}
function menuView() {
  return `${role === "tablet" ? tabletHeader() : ""}<div class="menu-layout"><div><section class="hero"><div class="hero-label">FRESCO. ARTESANAL. DO NOSSO JEITO.</div><h2>Feito com calma.<br>Saboreado com vontade.</h2><p>Conheça os favoritos da nossa cozinha.</p><span class="hero-tag">✧ Ingredientes selecionados</span></section><div class="toolbar"><div class="categories" role="group" aria-label="Categorias">${["Todos", "Burgers", "Porções", "Bebidas", "Sobremesas"].map((c) => `<button data-category="${c}" class="${c === category ? "active" : ""}" aria-pressed="${c === category}">${c}</button>`).join("")}</div><input class="search" id="search" type="search" aria-label="Buscar no cardápio" placeholder="⌕  Buscar no cardápio" value="${esc(query)}"></div><div class="section-heading"><h2 id="category-title">${category === "Todos" ? "Nosso cardápio" : category} <span class="accent">✧</span></h2><span id="result-count"></span></div><div class="products" id="products"></div></div><aside class="cart" aria-label="Seu pedido">${cartView()}</aside></div>`;
}
function renderProducts() {
  const filtered = products.filter(
    (p) =>
      p.available !== false &&
      (category === "Todos" || p.category === category) &&
      p.name.toLocaleLowerCase("pt-BR").includes(query.toLocaleLowerCase("pt-BR")),
  );
  document.querySelector("#result-count").textContent = filtered.length + " opções para você";
  document.querySelector("#products").innerHTML = filtered.length
    ? filtered
        .map(
          (p) =>
            `<article class="product"><div class="product-image"><img src="https://images.unsplash.com/${p.photo}?w=640&auto=format&fit=crop&q=80" alt="${p.name}" loading="lazy">${p.tag ? `<span class="product-tag">${p.tag}</span>` : ""}</div><div class="product-body"><h3>${p.name}</h3><p>${p.description}</p><div class="product-bottom"><span class="price">${money(p.price)}</span><button class="add" data-add="${p.id}" aria-label="Adicionar ${p.name}">+</button></div></div></article>`,
        )
        .join("")
    : '<div class="empty-search">Nenhum sabor encontrado. Tente outro nome.</div>';
}
let tabletLastOrder = null;
function tabletHeader() {
  return `<section class="tablet-toolbar"><div><span class="eyebrow">COMANDA DIGITAL</span><h2>À vontade, a casa é sua.</h2></div><label for="tablet-table">Pedido para a mesa<select id="tablet-table">${Array.from({ length: 12 }, (_, i) => `<option value="${i + 1}" ${table == i + 1 ? "selected" : ""}>Mesa ${String(i + 1).padStart(2, "0")}</option>`).join("")}</select></label><button class="secondary" id="fullscreen">Tela cheia ⛶</button></section><div class="tablet-tabs" role="group" aria-label="Comanda digital"><button class="${page === "menu" ? "active" : ""}" data-page="menu" aria-pressed="${page === "menu"}">Fazer pedido</button><button class="${page === "tablet-orders" ? "active" : ""}" data-page="tablet-orders" aria-pressed="${page === "tablet-orders"}">Já pedi <span>${tabletOrders().length}</span></button></div>${tabletLastOrder ? `<div class="tablet-success" role="status"><strong>✓ Pedido #${esc(tabletLastOrder.number)} enviado · Mesa ${esc(tabletLastOrder.table)}</strong><span>A cozinha recebeu seu pedido. Você já pode montar o próximo.</span></div>` : ""}`;
}
function tabletOrders() {
  return orders
    .filter((o) => o.variant === "salao" && String(o.table) === String(table))
    .slice()
    .reverse();
}
function tabletOrdersView() {
  const list = tabletOrders();
  return `${tabletHeader()}<div class="page-actions"><p>Histórico salvo da mesa ${esc(table)} · Inclui pedidos concluídos</p><strong>Total pedido: ${money(list.reduce((sum, o) => sum + o.total, 0))}</strong></div><div class="tracking-list">${list.length ? list.map((o) => `<article class="info-card tablet-history"><div class="order-head"><div><h2>Pedido #${esc(o.number)}</h2><small>${esc(new Date(o.createdAt).toLocaleString("pt-BR", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" }))} · Mesa ${esc(o.table)}</small></div><span>${["Recebido", "Em preparo", "Pronto", "Concluído"][o.stage]}</span></div><div class="progress-steps">${["Recebido", "Em preparo", "Pronto", "Concluído"].map((label, i) => `<span class="${i <= o.stage ? "reached" : ""}">${i + 1}. ${label}</span>`).join("")}</div>${o.items.map((item) => `<div class="history-item"><span><b>${item.qty}×</b> ${esc(item.name)}</span><strong>${money(item.price * item.qty)}</strong></div>`).join("")}<div class="history-total"><span>Total desta rodada</span><strong>${money(o.total)}</strong></div></article>`).join("") : '<section class="info-card"><h2>A mesa ainda não fez pedidos.</h2><p>Assim que enviar sua primeira rodada, ela aparecerá aqui.</p><button class="primary" data-page="menu">Escolher algo no cardápio →</button></section>'}</div><p class="history-note">Histórico do protótipo: os pedidos ficam salvos por mesa, sem separação por visita. O total não representa uma conta em aberto.</p>`;
}
function cartView() {
  if (role === "tablet") return tabletCartView();
  return standardCartView();
}
function tabletCartView() {
  const items = products.filter((p) => cart[p.id]);
  return `<div class="cart-header"><h2>Comanda · Mesa ${esc(table)}</h2><span>${count()} itens</span></div><form id="checkout-form"><div class="cart-content">${items.length ? items.map((p) => `<div class="cart-item"><div><strong>${p.name}</strong><small>${money(p.price * cart[p.id])}</small></div><div class="quantity"><button type="button" data-remove="${p.id}" aria-label="Remover um ${p.name}">−</button><span>${cart[p.id]}</span><button type="button" data-add="${p.id}" aria-label="Adicionar um ${p.name}">+</button></div></div>`).join("") : '<div class="cart-empty"><div class="empty-icon">▦</div><strong>O que vai ser hoje?</strong><p>Toque no + dos seus favoritos<br>para montar o pedido da mesa.</p></div>'}<div class="totals"><div class="grand-total"><span>Total desta rodada</span><span>${money(subtotal())}</span></div></div><button class="primary checkout" type="submit" ${count() ? "" : "disabled"}><span>Enviar para a cozinha</span><span>→</span></button><p class="cart-note">Pagamento no fechamento · Sem cobrança online</p></div></form>`;
}
function standardCartView() {
  const v = variants[variant];
  return `${fulfillmentPicker()}<div class="cart-header"><h2>▤ &nbsp; Seu pedido</h2><span>${count()} ${count() === 1 ? "item" : "itens"}</span></div><form id="checkout-form"><div class="cart-content"><div class="cart-mode"><span>${variant === "salao" ? "▦" : "♧"}</span><div>${v.mode}<small>${v.hint}</small></div></div>${
    count()
      ? products
          .filter((p) => cart[p.id])
          .map(
            (p) =>
              `<div class="cart-item"><div><strong>${p.name}</strong><small>${money(p.price * cart[p.id])}</small></div><div class="quantity"><button type="button" data-remove="${p.id}" aria-label="Remover um ${p.name}">−</button><span>${cart[p.id]}</span><button type="button" data-add="${p.id}" aria-label="Adicionar um ${p.name}">+</button></div></div>`,
          )
          .join("")
      : '<div class="cart-empty"><div class="empty-icon">♧</div><strong>Seu próximo favorito está aqui</strong><p>Adicione algo gostoso do cardápio<br>para começar seu pedido.</p></div>'
  }${count() ? `<label for="customer">Seu nome</label><input id="customer" required maxlength="60" placeholder="Como podemos chamar você?" value="${esc(customer)}">${variant === "delivery" ? `<label for="address">Endereço de entrega</label><input id="address" required minlength="8" maxlength="200" placeholder="Rua, número e bairro" value="${esc(address)}">` : variant === "salao" ? `<label for="table">Sua mesa</label><select id="table">${Array.from({ length: 12 }, (_, i) => `<option value="${i + 1}" ${table == i + 1 ? "selected" : ""}>Mesa ${String(i + 1).padStart(2, "0")}</option>`).join("")}</select>` : ""}` : ""}<div class="totals"><div><span>Subtotal</span><span>${money(subtotal())}</span></div><div><span>${variant === "delivery" ? "Taxa de entrega" : "Taxa de serviço"}</span><span>${v.fee ? money(v.fee) : "Grátis"}</span></div><div class="grand-total"><span>Total</span><span>${money(subtotal() + (count() ? v.fee : 0))}</span></div></div><button class="primary checkout" type="submit" ${count() ? "" : "disabled"}><span>Confirmar pedido</span><span>→</span></button><p class="cart-note">Pagamento ${variant === "delivery" ? "na entrega" : variant === "salao" ? "no fechamento da comanda" : "na retirada"} · Sem cobrança online</p></div></form><div class="cart-bottom"><b>♡ Preparado com carinho.</b><br>Ao confirmar, seu pedido aparece no painel da cozinha.</div>`;
}
function ordersView() {
  const list = orders.slice(),
    active = list.filter((o) => o.stage < 3),
    done = list.filter((o) => o.stage === 3);
  return `<div class="stats"><div class="stat"><span>Em andamento</span><strong>${active.length}</strong></div><div class="stat"><span>Concluídos</span><strong>${done.length}</strong></div><div class="stat"><span>Total dos pedidos</span><strong>${money(list.reduce((s, o) => s + o.total, 0))}</strong></div></div><div class="page-actions"><p>Todos os canais · atualização manual</p><div class="view-links">${features.tv ? `<a class="secondary" href="${roleLink("tv")}" target="_blank" rel="noopener">Abrir painel de TV ↗</a>` : ""}<button class="secondary" data-page="menu">+ Novo pedido</button></div></div><div class="board">${[
    "Recebidos",
    "Em preparo",
    "Prontos / Em entrega",
  ]
    .map(
      (name, stage) =>
        `<section class="column"><h2>${name}<span>${active.filter((o) => Math.min(o.stage, 2) === stage).length}</span></h2>${
          active
            .filter((o) => Math.min(o.stage, 2) === stage)
            .map(
              (o) =>
                `<article class="order"><div class="order-head"><h3>#${esc(o.number)} · ${variants[o.variant].mode}</h3><span>${esc(o.customer)}</span></div><p>${o.items.map((i) => `${i.qty}× ${esc(i.name)}`).join("<br>")}</p><p>${o.variant === "delivery" ? esc(o.address) : o.variant === "salao" ? "Mesa " + esc(o.table) : "Retirada no balcão"}</p><strong>${money(o.total)}</strong><button class="primary" data-advance="${esc(o.id)}">${stage === 0 ? "Iniciar preparo →" : stage === 1 ? "Marcar como pronto →" : o.variant === "delivery" && !o.dispatched ? "Saiu para entrega →" : "Concluir pedido ✓"}</button>${o.dispatched ? "<p>● Saiu para entrega</p>" : ""}</article>`,
            )
            .join("") || '<p class="empty-column">Tudo em dia por aqui.</p>'
        }</section>`,
    )
    .join(
      "",
    )}</div>${done.length ? `<div class="info-card" style="margin-top:20px"><h2>Pedidos concluídos</h2>${done.map((o) => `<p>#${esc(o.number)} · ${esc(o.customer)} · ${money(o.total)} · ${o.variant === "salao" ? "Comanda encerrada" : "Concluído"}</p>`).join("")}</div>` : ""}`;
}
function architectureView() {
  return `<section class="info-card"><div class="eyebrow">LINHA DE PRODUTOS DE SOFTWARE</div><h2>Uma base comum. Funcionalidades combináveis.</h2><p>Catálogo e Pedidos formam o núcleo obrigatório. Retirada, entrega e mesas podem coexistir. Comanda digital depende de atendimento em mesa. O painel de TV é opcional.</p><table class="matrix"><thead><tr><th>Funcionalidade</th><th>Configuração salva</th></tr></thead><tbody><tr><td>Catálogo e Pedidos</td><td>Obrigatórios</td></tr>${featureDefinitions.map((f) => `<tr><td>${f.title}</td><td>${features[f.id] ? "Habilitada" : "Desabilitada"}</td></tr>`).join("")}</tbody></table><h2 style="margin-top:24px">Serviços propostos</h2><p>${servicesFor(features).join(" · ")}</p><p>Este protótipo simula os serviços no navegador. Configurar recursos não implanta microsserviços reais.</p><button class="primary" id="export-config">Baixar configuração JSON ↓</button></section>`;
}
document.addEventListener("click", (e) => {
  const b = e.target.closest("button");
  if (!b) return;
  if (b.dataset.page) {
    const allowed = {
      tablet: ["menu", "tablet-orders"],
      client: ["menu", "tracking"],
      admin: ["admin", "settings", "catalog", "architecture"],
      counter: ["orders", "menu"],
      tv: ["tv"],
    };
    if (!allowed[role].includes(b.dataset.page)) return;
    if (b.dataset.page === "settings") draftFeatures = { ...features };
    page = b.dataset.page;
    render();
  } else if (b.dataset.preset) {
    if (role !== "admin" || !presets[b.dataset.preset]) return;
    draftFeatures = { ...presets[b.dataset.preset] };
    render();
  } else if (b.id === "discard-settings") {
    draftFeatures = { ...features };
    render();
  } else if (b.dataset.category) {
    category = b.dataset.category;
    render();
  } else if (b.dataset.add) {
    if (!products.some((p) => p.id === Number(b.dataset.add) && p.available !== false)) return;
    cart[b.dataset.add] = (cart[b.dataset.add] || 0) + 1;
    document.querySelector(".cart").innerHTML = cartView();
    toast("Adicionado ao pedido");
  } else if (b.dataset.remove) {
    if (--cart[b.dataset.remove] <= 0) delete cart[b.dataset.remove];
    document.querySelector(".cart").innerHTML = cartView();
  } else if (b.dataset.advance) {
    if (role !== "counter") return;
    loadOrders();
    const o = orders.find((o) => o.id === b.dataset.advance);
    if (o && o.stage < 3) {
      if (o.stage === 2 && o.variant === "delivery" && !o.dispatched) o.dispatched = true;
      else o.stage++;
      save();
      render();
      toast("Pedido atualizado");
    }
  } else if (b.id === "export-config") {
    const config = {
      version: 2,
      name: configurationName(),
      features: { catalog: true, orders: true, ...features },
      services: servicesFor(features),
      fulfillment: modes(),
      deliveryFee: features.delivery ? 5 : 0,
      prototype: true,
    };
    const url = URL.createObjectURL(
      new Blob([JSON.stringify(config, null, 2)], { type: "application/json" }),
    );
    const a = document.createElement("a");
    a.href = url;
    a.download = "mesa-facil-configuracao.json";
    a.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
});
document.addEventListener("input", (e) => {
  if (e.target.id === "search") {
    query = e.target.value;
    renderProducts();
  }
  if (e.target.id === "customer") customer = e.target.value;
  if (e.target.id === "address") address = e.target.value;
  if (e.target.id === "table") table = e.target.value;
});
document.addEventListener("submit", (e) => {
  if (e.target.id === "settings-form") {
    e.preventDefault();
    if (role !== "admin") return;
    const errors = configErrors(draftFeatures);
    if (errors.length) {
      toast(errors.join(" "));
      return;
    }
    try {
      localStorage.setItem(
        configurationKey,
        JSON.stringify({ version: 2, features: draftFeatures }),
      );
    } catch {
      toast("Não foi possível salvar a configuração.");
      return;
    }
    applyConfiguration();
    toast("Configuração salva e aplicada a todas as áreas.");
    render();
    return;
  }
  if (e.target.id === "catalog-form") {
    e.preventDefault();
    if (role !== "admin") return;
    const data = {};
    for (const p of products) {
      const price = Number(document.querySelector("#price-" + p.id).value);
      if (!Number.isFinite(price) || price <= 0 || price > 9999) {
        toast("Informe preços entre R$ 0,01 e R$ 9.999,00.");
        return;
      }
      data[p.id] = {
        price: Math.round(price * 100) / 100,
        available: document.querySelector("#available-" + p.id).checked,
      };
    }
    try {
      localStorage.setItem(catalogKey, JSON.stringify(data));
      loadCatalog();
      toast("Cardápio atualizado para os clientes.");
    } catch {
      toast("Não foi possível salvar o cardápio.");
    }
    return;
  }
  if (e.target.id !== "checkout-form" || !["client", "counter", "tablet"].includes(role)) return;
  e.preventDefault();
  if (featureSignature(readFeatures()) !== featureSignature(features)) {
    applyConfiguration();
    return;
  }
  if (!enabledRole(role) || !modes().includes(variant)) {
    toast("Esta modalidade não está habilitada.");
    return;
  }
  if (role === "tablet") {
    if (!/^(?:[1-9]|1[0-2])$/.test(table)) {
      toast("Selecione uma mesa válida.");
      return;
    }
    if (variant !== "salao") {
      toast("Comanda exige atendimento em mesa.");
      return;
    }
    customer = "Mesa " + table;
  }
  if (!count() || !customer.trim() || (variant === "delivery" && address.trim().length < 8)) {
    toast("Preencha os dados do pedido.");
    return;
  }
  loadCatalog();
  if (products.some((p) => cart[p.id] && p.available === false)) {
    toast("Um item ficou indisponível. Remova-o do pedido.");
    render();
    return;
  }
  loadOrders();
  const order = {
    id: crypto.randomUUID(),
    number: 1001 + orders.length,
    variant,
    customer: customer.trim(),
    address: variant === "delivery" ? address.trim() : "",
    table: variant === "salao" ? table : null,
    items: products
      .filter((p) => cart[p.id])
      .map((p) => ({ name: p.name, price: p.price, qty: cart[p.id] })),
    total: Math.round((subtotal() + variants[variant].fee) * 100) / 100,
    stage: 0,
    createdAt: new Date().toISOString(),
  };
  orders.push(order);
  if (role === "tablet") tabletLastOrder = { number: order.number, table: order.table };
  if (role === "client") {
    myOrderIds.push(order.id);
    try {
      sessionStorage.setItem("mesa-my-orders", JSON.stringify(myOrderIds));
    } catch {}
  }
  save();
  cart = {};
  customer = "";
  address = "";
  page = role === "tablet" ? "menu" : role === "client" ? "tracking" : "orders";
  render();
  toast("Pedido #" + order.number + " enviado para a cozinha!");
});

function adminView() {
  const list = orders.slice();
  return `<div class="stats"><div class="stat"><span>Pedidos em andamento</span><strong>${list.filter((o) => o.stage < 3).length}</strong></div><div class="stat"><span>Valor dos pedidos concluídos</span><strong>${money(list.filter((o) => o.stage === 3).reduce((s, o) => s + o.total, 0))}</strong></div><div class="stat"><span>Produtos disponíveis</span><strong>${products.filter((p) => p.available !== false).length} / ${products.length}</strong></div></div><div class="architecture-grid"><section class="info-card"><div class="eyebrow">GESTÃO DO RESTAURANTE</div><h2>Um cardápio sempre atualizado.</h2><p>Altere preços e pause produtos esgotados. As outras áreas recebem suas alterações automaticamente.</p><button class="primary" data-page="catalog">Gerenciar cardápio →</button></section><section class="info-card"><div class="eyebrow">CADA PESSOA, SUA EXPERIÊNCIA</div><h2>Abra os espaços da operação.</h2><div class="view-links">${[
    "client",
    "tablet",
    "counter",
    "tv",
  ]
    .filter(enabledRole)
    .map(
      (r) =>
        `<a class="secondary" href="${roleLink(r)}" target="_blank" rel="noopener">${roles[r]} ↗</a>`,
    )
    .join(
      "",
    )}</div><p>Sincronização entre abas do mesmo navegador. O painel da TV mostra somente os números dos pedidos.</p></section></div><section class="info-card" style="margin-top:20px"><h2>Configuração: ${configurationName()}</h2><p>${modes()
    .map((v) => variants[v].mode)
    .join(
      " · ",
    )}</p><button class="secondary" data-page="architecture">Explorar linha de produtos →</button></section>`;
}
function catalogView() {
  return `<form id="catalog-form" class="info-card"><div class="page-actions"><p>Catálogo compartilhado entre as três variantes.</p><button class="primary" type="submit">Salvar alterações</button></div><div class="catalog-table">${products.map((p) => `<div class="catalog-row"><div><strong>${p.name}</strong><small>${p.category}</small></div><label>Preço (R$)<input id="price-${p.id}" type="number" min="0.01" max="9999" step="0.01" required value="${p.price.toFixed(2)}"></label><label class="availability"><input type="checkbox" id="available-${p.id}" ${p.available !== false ? "checked" : ""}> Disponível</label></div>`).join("")}</div></form>`;
}
function trackingView() {
  const list = orders
    .filter((o) => myOrderIds.includes(o.id))
    .slice()
    .reverse();
  return `<div class="page-actions"><p>Atualizado automaticamente nesta aba.</p><button class="secondary" data-page="menu">Voltar ao cardápio</button></div><div class="tracking-list">${list.map((o) => `<article class="info-card"><div class="order-head"><h2>Pedido #${esc(o.number)}</h2><span>${o.dispatched && o.stage === 2 ? "Saiu para entrega" : ["Recebido", "Em preparo", "Pronto", "Concluído"][o.stage]}</span></div><div class="progress-steps">${["Recebido", "Em preparo", "Pronto", "Concluído"].map((t, i) => `<span class="${i <= o.stage ? "reached" : ""}">${i + 1}. ${t}</span>`).join("")}</div><p>${o.items.map((i) => `${i.qty}× ${esc(i.name)}`).join(" · ")}</p><strong>${money(o.total)}</strong><p>${o.variant === "express" ? "Aguarde seu número aparecer no painel de retirada." : o.variant === "salao" ? "Atendimento na mesa " + esc(o.table) : "Entrega em " + esc(o.address)}</p></article>`).join("") || '<div class="info-card"><h2>Seu primeiro pedido começa no cardápio.</h2><p>Os pedidos feitos nesta aba aparecerão aqui.</p></div>'}</div>`;
}
function tvView() {
  const list = orders.slice();
  return `<div class="tv-top"><div><span class="tv-brand">mesa fácil<span>·</span></span><p>QUINTAL DA CASA · ${configurationName().toUpperCase()}</p></div><div class="tv-tools"><a href="${roleLink("counter")}">Voltar ao balcão</a><button class="secondary" id="fullscreen">Tela cheia ⛶</button><span id="tv-clock">${new Date().toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" })}</span></div></div><div class="tv-board">${[
    1, 2,
  ]
    .map((stage) => {
      const items = list.filter((o) => o.stage === stage && !o.dispatched);
      return `<section class="tv-column ${stage === 2 ? "ready" : ""}"><div class="tv-heading"><h2>${stage === 1 ? "Em preparo" : "Prontos"}</h2><span>${stage === 1 ? "Estamos caprichando por aqui." : variant === "express" ? "Pode retirar no balcão!" : variant === "salao" ? "A caminho da sua mesa." : "Aguardando saída para entrega."}</span></div><div class="tv-numbers" aria-live="polite">${items.map((o) => `<div class="ticket"><small>PEDIDO</small><strong>${esc(o.number)}</strong><span>${o.table ? `Mesa ${esc(o.table)}` : o.variant === "delivery" ? "Entrega" : "Retirada"}</span></div>`).join("") || '<p class="tv-empty">Novos pedidos aparecerão aqui.</p>'}</div></section>`;
    })
    .join(
      "",
    )}</div><div class="tv-footer"><span>Feito com carinho. Servido com um sorriso.</span><span>● Atualização automática</span></div>`;
}
document.addEventListener("change", (e) => {
  if (e.target.dataset?.feature && role === "admin") {
    draftFeatures[e.target.dataset.feature] = e.target.checked;
    render();
    return;
  }
  if (
    e.target.id === "fulfillment" &&
    ["client", "counter"].includes(role) &&
    modes().includes(e.target.value)
  ) {
    variant = e.target.value;
    address = "";
    document.querySelector(".cart").innerHTML = cartView();
    return;
  }
  if (e.target.id === "tablet-table") {
    table = e.target.value;
    tabletLastOrder = null;
    render();
  }
  if (e.target.id === "role-select") {
    role = e.target.value;
    if (role === "tablet" && features.tables) variant = "salao";
    else if (!modes().includes(variant)) variant = modes()[0];
    page = defaultPages[role];

    updateUrl();
    render();
  }
});
document.addEventListener("click", async (e) => {
  if (e.target.closest("#fullscreen")) {
    try {
      if (document.fullscreenElement) await document.exitFullscreen();
      else await document.documentElement.requestFullscreen();
    } catch {
      toast("Tela cheia indisponível neste navegador.");
    }
  }
});
window.addEventListener("storage", (e) => {
  if (e.key === configurationKey || e.key === null) applyConfiguration();
  if (e.key === storageKey || e.key === null) {
    loadOrders();
    if (role === "tablet" && page === "menu") render();
    if (["orders", "tracking", "tv", "admin", "tablet-orders"].includes(page)) render();
  }
  if (e.key === catalogKey || e.key === null) {
    loadCatalog();
    if (page === "menu" && enabledRole(role)) {
      renderProducts();
      document.querySelector(".cart").innerHTML = cartView();
    } else if (page === "admin") render();
  }
});
setInterval(() => {
  const clock = document.querySelector("#tv-clock");
  if (clock)
    clock.textContent = new Date().toLocaleTimeString("pt-BR", {
      hour: "2-digit",
      minute: "2-digit",
    });
}, 1000);
render();
