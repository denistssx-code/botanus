// Zones, réglages (météo, heures de récupération, apparence) et menu « Plus » du mobile.
import {
  $, html, raw, mount, icon, api, state, load, actions, toast, formDialog, confirmDialog, field, textInput, selectInput,
  fmtDate, todayISO, emptyState, debounce, inputs,
} from './core.js';

/* ---------- Zones ---------- */
const ZONE_ICONS = ['🌳', '🥕', '🌹', '🍇', '🫒', '🌿', '🪴', '🏊', '🏡', '🌸', '🍅', '🧱'];

export const zones = {
  title: 'Zones',
  render(root) {
    this.root = root; this.update();
  },
  route() {},
  update() {
    if (!this.root) return;
    mount(this.root, html`<div class="page-scroll"><div class="page">
      <div class="page-head"><div><h1>Zones</h1><p class="muted">Les espaces de votre propriété.</p></div>
        <button class="btn" data-action="zone-add">${icon('plus')} Nouvelle zone</button></div>
      ${state.zones.length ? html`<div class="cols" style="grid-template-columns:repeat(auto-fill,minmax(280px,1fr))">${state.zones.map((z) => {
        const ps = state.plants.filter((p) => p.zones.includes(Number(z.id)));
        const ts = state.tasks.filter((t) => t.status !== 'done' && (t.zones || []).map(Number).includes(Number(z.id)));
        return html`<section class="block" style="border:1px solid var(--line);border-radius:14px;padding:16px;background:var(--panel)">
          <h2 style="border:0;padding:0"><span>${z.icon || '🗺️'} ${z.nom}</span>
            <button class="icon-btn" data-action="zone-edit" data-id="${z.id}" aria-label="Modifier ${z.nom}">${icon('edit')}</button></h2>
          ${z.description ? html`<p class="muted small">${z.description}</p>` : ''}
          <p class="small">${ps.length} plante${ps.length > 1 ? 's' : ''} · ${ts.length} tâche${ts.length > 1 ? 's' : ''} à faire</p>
          <div class="chips">${ps.slice(0, 8).map((p) => html`<a class="chip" href="#/plants/${p.id}" style="text-decoration:none">${p.nom_francais || p.nom_latin}</a>`)}${ps.length > 8 ? html`<span class="chip">+${ps.length - 8}</span>` : ''}</div>
        </section>`;
      })}</div>` : emptyState('Aucune zone', 'Créez des zones (potager, haie, terrasse…) pour y ranger plantes et tâches.')}
    </div></div>`);
  },
};
const zoneForm = (z) => html`${field('Nom', textInput('nom', z?.nom || '', 'required'))}
  <fieldset style="border:0;padding:0;margin:0"><legend class="field"><span>Icône</span></legend><div class="chips">${ZONE_ICONS.map((i) => html`<label class="chip" style="cursor:pointer;min-height:40px;font-size:1.3rem"><input type="radio" name="icon" value="${i}" class="visually-hidden" ${raw((z?.icon || '🌳') === i ? 'checked' : '')}>${i}</label>`)}</div></fieldset>
  ${field('Description', textInput('description', z?.description || ''))}`;
actions['zone-add'] = () => formDialog({ title: 'Nouvelle zone', body: zoneForm(null), submit: 'Créer', onSubmit: async (v) => { await api('/zones', { method: 'POST', body: v }); await load(); } });
actions['zone-edit'] = (el) => {
  const z = state.zones.find((x) => Number(x.id) === Number(el.dataset.id));
  formDialog({ title: 'Modifier la zone', body: zoneForm(z), danger: 'Supprimer',
    onSubmit: async (v) => { await api(`/zones/${z.id}`, { method: 'PATCH', body: v }); await load(); },
    onDanger: async () => {
      if (!await confirmDialog(`Supprimer la zone « ${z.nom} » ?`)) return false;
      await api(`/zones/${z.id}`, { method: 'DELETE' }); await load(); return true;
    } });
};
/* le style des icônes sélectionnées dans le formulaire de zone */
document.head.insertAdjacentHTML('beforeend', '<style>.chip:has(input[type=radio]:checked){background:var(--accent-soft);outline:2px solid var(--accent)}.chip:has(input:focus-visible){outline:3px solid var(--accent)}</style>');

/* ---------- Réglages ---------- */
const THEMES = [['auto', 'Automatique'], ['light', 'Clair'], ['dark', 'Sombre']];
export function applyTheme() {
  let t = 'auto'; try { t = localStorage.getItem('botanus-theme') || 'auto'; } catch { /* stockage indisponible */ }
  if (t === 'auto') delete document.documentElement.dataset.theme; else document.documentElement.dataset.theme = t;
  return t;
}
const balance = () => state.heures.reduce((s, h) => s + (h.type === 'Supp' ? 1 : -1) * Number(h.duree || 0), 0);
const hh = (n) => `${Math.abs(n).toLocaleString('fr-FR', { maximumFractionDigits: 2 })} h`;
let geoResults = [];

export const settings = {
  title: 'Réglages',
  render(root) { this.root = root; this.update(); },
  route() {},
  update() {
    if (!this.root || this.root.querySelector('#geo-q:focus')) return;
    const s = state.settings, theme = applyTheme(), bal = balance();
    mount(this.root, html`<div class="page-scroll"><div class="page">
      <div class="page-head"><h1>Réglages</h1></div>
      <div class="cols">
        <section class="block"><h2>Météo</h2>
          <p>Ville suivie : <b>${s.meteo_ville || 'Malaucène'}</b></p>
          <form id="geo-form" class="search">${icon('search')}<input class="input" id="geo-q" type="search" placeholder="Changer de ville" aria-label="Changer de ville" autocomplete="off"></form>
          <div id="geo-res">${geoResults.length ? html`<ul class="list">${geoResults.map((g, i) => html`<li><button class="item" data-action="geo-pick" data-i="${i}"><span class="item-main"><span class="item-title">${g.name}</span></span></button></li>`)}</ul>` : ''}</div>
        </section>
        <section class="block"><h2>Apparence</h2>
          <div class="seg" role="group" aria-label="Thème">${THEMES.map(([v, l]) => html`<button data-action="theme" data-v="${v}" aria-pressed="${theme === v}">${l}</button>`)}</div>
          <p class="small muted">« Automatique » suit le réglage de votre appareil.</p>
          <p style="margin-top:12px"><a href="/classic">Ouvrir l'ancienne interface</a></p>
        </section>
      </div>
      <section class="block"><h2>Heures de récupération <span class="chip ${bal > 0 ? 'ok' : bal < 0 ? 'warn' : ''}">${bal >= 0 ? '+' : '−'}${hh(bal)}</span></h2>
        <div><button class="btn small" data-action="heure-add">${icon('plus')} Ajouter des heures</button></div>
        ${state.heures.length ? html`<ul class="list">${[...state.heures].sort((a, b) => String(b.date).localeCompare(String(a.date))).map((h) => html`<li><div class="item">
          <span class="item-main"><span class="item-title">${h.type === 'Supp' ? 'Heures supplémentaires' : 'Récupération'}</span><span class="item-sub">${fmtDate(h.date, { day: 'numeric', month: 'long', year: 'numeric' })}${h.note ? ' · ' + h.note : ''}</span></span>
          <span class="qty">${h.type === 'Supp' ? '+' : '−'}${hh(Number(h.duree))}</span></div></li>`)}</ul>` : emptyState('Aucune heure enregistrée', 'Suivez vos heures supplémentaires et vos récupérations.')}
      </section>
    </div></div>`);
    const form = $('#geo-form', this.root);
    form.addEventListener('submit', (e) => { e.preventDefault(); searchCity($('#geo-q', this.root).value); });
  },
};
async function searchCity(q) {
  q = q.trim(); if (q.length < 2) return;
  try { geoResults = (await api(`/geocode?q=${encodeURIComponent(q)}`)).results || []; } catch (e) { toast(e.message, 'error'); }
  if (!geoResults.length) toast('Aucune ville trouvée');
  settings.update();
}
actions['geo-pick'] = async (el) => {
  const g = geoResults[Number(el.dataset.i)];
  await api('/settings/meteo', { method: 'PUT', body: { meteo_ville: g.raw_name || g.name, meteo_latitude: g.lat, meteo_longitude: g.lon, meteo_mode: 'ville' } });
  geoResults = []; await load(); toast('Ville enregistrée');
};
actions['theme'] = (el) => {
  try { localStorage.setItem('botanus-theme', el.dataset.v); } catch { /* ignoré */ }
  applyTheme(); settings.update();
};
actions['heure-add'] = () => formDialog({
  title: 'Ajouter des heures',
  body: html`<div class="row2">${field('Type', selectInput('type', [['Supp', 'Heures supplémentaires'], ['Récup', 'Récupération']], 'Supp'))}${field('Durée (heures)', textInput('duree', '', 'type="number" step="0.25" min="0" required inputmode="decimal"'))}</div>
    ${field('Date', textInput('date', todayISO(), 'type="date" required'))}${field('Note', textInput('note', ''))}`,
  submit: 'Ajouter',
  onSubmit: async (v) => { await api('/heures-recup', { method: 'POST', body: { ...v, duree: Number(v.duree) } }); await load(); },
});

/* ---------- Menu « Plus » (mobile) ---------- */
export const more = {
  title: 'Plus',
  render(root) {
    mount(root, html`<div class="page-scroll"><div class="page"><div class="page-head"><h1>Plus</h1></div>
      <ul class="list" style="border:1px solid var(--line);border-radius:14px;background:var(--panel);overflow:hidden">
        ${[['search', 'Rechercher une plante', '#/search'], ['box', 'Inventaire', '#/inventory'], ['map', 'Zones', '#/zones'], ['gear', 'Réglages et heures de récup', '#/settings']].map(([i, l, h]) => html`
          <li><a class="item" href="${h}">${icon(i)}<span class="item-main"><span class="item-title">${l}</span></span></a></li>`)}
      </ul></div></div>`);
  },
  route() {},
};
