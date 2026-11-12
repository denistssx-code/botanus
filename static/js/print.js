// Impression d'une sélection de plantes (une zone, une liste filtrée ou un choix libre) : fiches courtes avec photo.
import { $, html, raw, mount, icon, state, actions, changes, inputs, monthsOf, MONTHS, norm, cleanName, zoneById, esc, debounce, fmtDate } from './core.js';
import { glue } from './plants.js';

let root, lastQuery = null;
let sel = new Set();
let title = 'Ma sélection';
let pickFilter = '';
const opts = { photos: true, calendar: true, facts: true };

const name = (p) => cleanName(p.nom_francais) || p.nom_latin;
const byName = (a, b) => name(a).localeCompare(name(b), 'fr');
const safeSrc = (u) => (/^(https?:\/\/|\/api\/|data:image\/)/i.test(u || '') ? u : '');

const FACTS = [
  ['Exposition', 'exposition'], ['Hauteur', 'hauteur_maturite'], ['Largeur', 'largeur_maturite'], ['Fleurs', 'couleur_fleur'],
  ['Feuillage', 'persistance_feuillage'], ['Rusticité', 'rusticite'], ['Sol', 'type_sol'], ['Utilisation', 'type_utilisation'],
];
const PERIODS = [
  ['Floraison', 'flo', (p) => (p.facets || {}).periode_floraison],
  ['Taille', 'tai', (p) => (p.facets || {}).periode_taille],
  ['Récolte', 'rec', (p) => (p.facts || {}).periode_recolte],
  ['Plantation', 'pla', (p) => (p.facets || {}).meilleure_periode_plantation],
];

function applyQuery(q) {
  const key = q.toString();
  if (key === lastQuery) return;
  lastQuery = key;
  if (q.get('zone')) {
    const z = zoneById(q.get('zone'));
    title = z ? `Zone ${z.nom}` : 'Ma sélection';
    sel = new Set(state.plants.filter((p) => p.zones.includes(Number(q.get('zone')))).map((p) => p.id));
  } else if (q.get('ids') !== null) {
    sel = new Set(q.get('ids').split(',').map(Number).filter((id) => state.plants.some((p) => p.id === id)));
    title = q.get('t') || 'Ma sélection';
  }
}

const chosen = () => state.plants.filter((p) => sel.has(p.id)).sort(byName);

function strip(p) {
  const rows = PERIODS.map(([label, cls, get]) => ({ label, cls, set: monthsOf(get(p)) })).filter((r) => r.set.size);
  if (!rows.length) return '';
  return html`<table class="pc-cal" aria-label="Calendrier"><thead><tr><th></th>${MONTHS.map((m) => html`<th>${m.replace('.', '').slice(0, 1).toUpperCase()}</th>`)}</tr></thead>
    <tbody>${rows.map((r) => html`<tr><th scope="row">${r.label}</th>${MONTHS.map((_, m) => html`<td class="${r.set.has(m) ? 'on ' + r.cls : ''}"></td>`)}</tr>`)}</tbody></table>`;
}

function card(p) {
  const src = safeSrc(p.image);
  const facts = FACTS.map(([l, k]) => [l, (p.facets || {})[k]]).filter(([, v]) => v);
  return html`<article class="pcard">
    ${opts.photos ? html`<div class="pc-photo">${src ? html`<img src="${src}" alt="" decoding="async">` : html`<span aria-hidden="true">🌿</span>`}</div>` : ''}
    <div class="pc-main">
      <h3>${name(p)}${p.quantity ? html` <span class="pc-qty">×${p.quantity}</span>` : ''}</h3>
      ${p.nom_francais && p.nom_latin ? html`<p class="pc-latin">${p.nom_latin}</p>` : ''}
      ${opts.facts && facts.length ? html`<dl class="pc-facts">${facts.map(([l, v]) => html`<div><dt>${l}</dt><dd>${glue(v)}</dd></div>`)}</dl>` : ''}
      ${opts.calendar ? strip(p) : ''}
    </div>
  </article>`;
}

function drawDoc() {
  const list = chosen();
  const box = $('#pr-doc', root);
  if (!box) return;
  mount(box, list.length
    ? html`<header class="pd-head"><h1>${title}</h1><p>${list.length} plante${list.length > 1 ? 's' : ''} · ${fmtDate(new Date().toISOString(), { day: 'numeric', month: 'long', year: 'numeric' })}</p></header>
        <div class="pd-grid">${list.map(card)}</div>`
    : html`<div class="empty noprint"><h3>Aucune plante sélectionnée</h3><p>Cochez des plantes ci-dessus, ou choisissez une zone.</p></div>`);
  const n = $('#pr-count', root); if (n) n.textContent = `${list.length} plante${list.length > 1 ? 's' : ''}`;
  const b = $('[data-action=pr-print]', root); if (b) b.disabled = !list.length;
}

function drawPicker() {
  const q = norm(pickFilter);
  const list = [...state.plants].sort(byName).filter((p) => !q || norm(name(p) + ' ' + p.nom_latin).includes(q));
  mount($('#pr-list', root), list.length ? html`${list.map((p) => html`<label><input type="checkbox" data-change="pr-plant" value="${p.id}" ${raw(sel.has(p.id) ? 'checked' : '')}> <span>${name(p)}</span></label>`)}`
    : html`<p class="muted small">Aucune plante ne correspond.</p>`);
}

function draw() {
  mount(root, html`<div class="page-scroll"><div class="page print-page">
    <div class="noprint pr-tools">
      <div class="page-head"><div><h1>Imprimer</h1><p class="muted">Fiches courtes avec photo, pour emporter au jardin.</p></div>
        <div class="chips"><a class="btn quiet" href="#/plants">Retour</a><button class="btn" data-action="pr-print">${icon('print')} Imprimer · <span id="pr-count"></span></button></div></div>
      <div class="pr-opts">
        <label class="field"><span>Titre</span><input class="input" data-input="pr-title" value="${esc(title)}"></label>
        <label class="field"><span>Ajouter les plantes d'une zone</span><select class="select" data-change="pr-zone"><option value="">Choisir une zone…</option>${state.zones.map((z) => html`<option value="${z.id}">${z.icon || ''} ${z.nom}</option>`)}</select></label>
        <fieldset class="pr-checks"><legend class="visually-hidden">Contenu</legend>
          <label><input type="checkbox" data-change="pr-opt" data-k="photos" ${raw(opts.photos ? 'checked' : '')}> Photos</label>
          <label><input type="checkbox" data-change="pr-opt" data-k="facts" ${raw(opts.facts ? 'checked' : '')}> Caractéristiques</label>
          <label><input type="checkbox" data-change="pr-opt" data-k="calendar" ${raw(opts.calendar ? 'checked' : '')}> Calendrier</label></fieldset>
      </div>
      <details class="pr-picker"><summary>Choisir les plantes <span class="muted small" id="pr-count2"></span></summary>
        <div class="pr-picker-body">
          <div class="pr-picker-bar"><input class="input" type="search" data-input="pr-filter" placeholder="Filtrer les plantes" aria-label="Filtrer les plantes">
            <button type="button" class="btn quiet small" data-action="pr-all">Tout cocher</button><button type="button" class="btn quiet small" data-action="pr-none">Tout décocher</button></div>
          <div id="pr-list" class="pr-list"></div></div></details>
    </div>
    <div id="pr-doc" class="pr-doc"></div>
  </div></div>`);
  drawPicker(); drawDoc();
}

const refreshCounts = () => { const n = $('#pr-count2', root); if (n) n.textContent = `(${sel.size} cochée${sel.size > 1 ? 's' : ''})`; };

changes['pr-plant'] = (el) => { const id = Number(el.value); el.checked ? sel.add(id) : sel.delete(id); drawDoc(); refreshCounts(); };
changes['pr-opt'] = (el) => { opts[el.dataset.k] = el.checked; drawDoc(); };
changes['pr-zone'] = (el) => {
  if (!el.value) return;
  const z = zoneById(el.value);
  state.plants.filter((p) => p.zones.includes(Number(el.value))).forEach((p) => sel.add(p.id));
  if (z && (title === 'Ma sélection' || !sel.size)) title = `Zone ${z.nom}`;
  el.value = '';
  draw(); refreshCounts();
};
inputs['pr-title'] = (el) => { title = el.value; const h = $('.pd-head h1', root); if (h) h.textContent = title; };
inputs['pr-filter'] = debounce((el) => { pickFilter = el.value; drawPicker(); }, 120);
actions['pr-all'] = () => { const q = norm(pickFilter); state.plants.filter((p) => !q || norm(name(p) + ' ' + p.nom_latin).includes(q)).forEach((p) => sel.add(p.id)); drawPicker(); drawDoc(); refreshCounts(); };
actions['pr-none'] = () => { const q = norm(pickFilter); state.plants.filter((p) => !q || norm(name(p) + ' ' + p.nom_latin).includes(q)).forEach((p) => sel.delete(p.id)); drawPicker(); drawDoc(); refreshCounts(); };
actions['pr-print'] = () => {
  // attend les images (sinon l'aperçu d'impression s'ouvre avec des cadres vides)
  const imgs = [...document.querySelectorAll('#pr-doc img')];
  Promise.all(imgs.map((i) => (i.complete ? null : i.decode().catch(() => null)))).then(() => window.print());
};

export const printView = {
  title: 'Imprimer',
  render(r, params) { root = r; lastQuery = null; applyQuery(params.query); draw(); refreshCounts(); },
  route(params) { const before = lastQuery; applyQuery(params.query); if (lastQuery !== before) { draw(); refreshCounts(); } },
  update() { if (root && $('#pr-doc', root)) { drawPicker(); drawDoc(); } },
};
