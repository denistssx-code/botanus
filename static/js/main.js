// Démarrage, routeur à base de hash, navigation.
import { $, mount, html, raw, state, load, subscribe, actions, toast, fail, emptyState, icon } from './core.js';
import { today } from './today.js';
import { plants, search } from './plants.js';
import { tasks, inventory, journal } from './work.js';
import { zones, settings, more, applyTheme } from './more.js';

applyTheme();
const VIEWS = { today, plants, search, tasks, inventory, journal, zones, settings, more };
const NAV = [
  ['today', "Aujourd'hui", 'sun'], ['plants', 'Plantes', 'leaf'], ['search', 'Recherche', 'search'], ['tasks', 'Tâches', 'check'],
  ['inventory', 'Inventaire', 'box'], ['journal', 'Journal', 'book'], ['zones', 'Zones', 'map'], ['settings', 'Réglages', 'gear'],
];
const TABS = [['today', "Aujourd'hui", 'sun'], ['plants', 'Plantes', 'leaf'], ['tasks', 'Tâches', 'check'], ['journal', 'Journal', 'book'], ['more', 'Plus', 'more']];
const MORE_GROUP = new Set(['search', 'inventory', 'zones', 'settings', 'more']);

let mounted = null, mountedName = null;

function parse() {
  const [path, query = ''] = location.hash.replace(/^#\/?/, '').split('?');
  const [name = 'today', id] = path.split('/');
  return { name: VIEWS[name] ? name : 'today', id: id ? Number(id) || id : null, query: new URLSearchParams(query) };
}

function counts() {
  return {
    plants: state.plants.length,
    tasks: state.tasks.filter((t) => t.status !== 'done').length,
    inventory: state.inventory.filter((i) => i.statut === 'À acheter' || (i.statut === 'Possédé' && Number(i.seuil_alerte) > 0 && Number(i.quantite) <= Number(i.seuil_alerte))).length,
  };
}

function drawNav(active) {
  const c = counts();
  mount($('#rail-nav'), html`${NAV.map(([k, label, ic]) => html`<a class="nav-link" href="#/${k}" ${raw(active === k ? 'aria-current="page"' : '')} title="${label}">${icon(ic)}<span>${label}</span>${c[k] ? html`<span class="nav-count">${c[k]}</span>` : ''}</a>`)}`);
  const tabKey = (k) => (MORE_GROUP.has(active) ? 'more' : active) === k;
  mount($('#tabbar'), html`${TABS.map(([k, label, ic]) => html`<a href="#/${k}" ${raw(tabKey(k) ? 'aria-current="page"' : '')}>${icon(ic)}<span>${label}</span></a>`)}`);
}

function route() {
  const r = parse();
  const view = VIEWS[r.name];
  drawNav(r.name);
  document.title = `${view.title} · Botanus`;
  if (!state.loaded) return;
  const stage = $('#stage');
  if (mountedName === r.name && view.route && mounted === stage.firstElementChild) {
    view.route(r);
  } else {
    stage.replaceChildren();
    const holder = document.createElement('div');
    stage.append(holder);
    mounted = holder; mountedName = r.name;
    view.render(holder, r);
    window.scrollTo(0, 0);
  }
}

actions.back = () => {
  const v = VIEWS[mountedName];
  if (v && v.back) v.back(); else location.hash = '#/' + mountedName;
};
actions['toggle-theme'] = () => {};

subscribe(() => {
  drawNav(parse().name);
  const v = VIEWS[mountedName];
  if (v && v.update) v.update();
});
window.addEventListener('hashchange', route);

(async function start() {
  const stage = $('#stage');
  mount(stage, html`<div class="page"><div class="skeleton" style="height:40px;width:40%"></div><div class="skeleton" style="height:120px"></div><div class="skeleton" style="height:220px"></div></div>`);
  try {
    await load();
    stage.replaceChildren(); mounted = null; mountedName = null;
    route();
  } catch (e) {
    mount(stage, html`<div class="page">${emptyState('Impossible de charger le jardin', e.message || 'Le serveur ne répond pas.', html`<button class="btn" onclick="location.reload()">Réessayer</button>`)}
      <p class="small muted" style="text-align:center"><a href="/classic">Ouvrir l'ancienne interface</a></p></div>`);
  }
})();
