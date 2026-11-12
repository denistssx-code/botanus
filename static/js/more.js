// Zones, réglages (météo, heures de récupération, apparence) et menu « Plus » du mobile.
import {
  $, html, raw, mount, icon, api, state, load, actions, toast, formDialog, confirmDialog, field, textInput, selectInput,
  fmtDate, todayISO, emptyState, debounce, inputs, backButton, thumb, cleanName,
} from './core.js';

/* ---------- Zones ---------- */
const ZONE_ICONS = ['🌳', '🥕', '🌹', '🍇', '🫒', '🌿', '🪴', '🏊', '🏡', '🌸', '🍅', '🧱'];

const zPlants = (z) => state.plants.filter((p) => p.zones.includes(Number(z.id)))
  .sort((a, b) => (cleanName(a.nom_francais) || a.nom_latin).localeCompare(cleanName(b.nom_francais) || b.nom_latin, 'fr'));
const zTasks = (z) => state.tasks.filter((t) => t.status !== 'done' && (t.zones || []).map(Number).includes(Number(z.id)));
const zoneAll = new Set(); // zones dont toute la liste de plantes est dépliée
const Z_MAX = 18;
const plural = (n, one, many) => `${n} ${n > 1 ? many : one}`;

// Liste des zones à gauche (compacte), détail à droite : reste lisible même avec beaucoup de zones et de plantes.
export const zones = {
  title: 'Zones',
  sel: null,
  render(root, params) { this.root = root; this.sel = params.id ?? null; this.draw(true); },
  route(params) { this.sel = params.id ?? null; this.draw(true); },
  update() { this.draw(false); },
  draw(fresh) {
    if (!this.root) return;
    if (this.sel == null && state.zones.length && matchMedia('(min-width: 720px)').matches) { location.replace(`#/zones/${state.zones[0].id}`); return; }
    const z = this.sel == null ? null : state.zones.find((x) => Number(x.id) === Number(this.sel));
    mount(this.root, html`<div class="view" id="z-view" data-open="${z ? 'detail' : 'list'}">
      <section class="pane-list" aria-label="Zones">
        <div class="pane-head">
          <div class="pane-title"><h1>Zones</h1><span class="muted small">${plural(state.zones.length, 'zone', 'zones')}</span></div>
          <div><button class="btn small" data-action="zone-add">${icon('plus')} Nouvelle zone</button></div>
        </div>
        ${state.zones.length ? html`<ul class="list">${state.zones.map((x) => html`<li><a class="item" href="#/zones/${x.id}" ${raw(z && Number(z.id) === Number(x.id) ? 'aria-current="true"' : '')}>
          <span class="thumb" aria-hidden="true">${x.icon || '🗺️'}</span>
          <span class="item-main"><span class="item-title">${x.nom}</span><span class="item-sub">${plural(zPlants(x).length, 'plante', 'plantes')} · ${plural(zTasks(x).length, 'tâche', 'tâches')}</span></span></a></li>`)}</ul>`
          : emptyState('Aucune zone', 'Créez des zones (potager, haie, terrasse…) pour y ranger plantes et tâches.')}
      </section>
      <section class="pane-detail" aria-live="polite">${z ? this.detail(z) : emptyState('Choisissez une zone', 'Ses plantes et ses tâches s\'affichent ici.')}</section>
    </div>`);
  },
  detail(z) {
    const ps = zPlants(z), ts = zTasks(z);
    return html`${backButton('Retour')}
      <header class="page-head"><div><h1>${z.icon || '🗺️'} ${z.nom}</h1>${z.description ? html`<p class="muted">${z.description}</p>` : ''}</div>
        <div class="chips"><a class="btn quiet small" href="#/print?zone=${z.id}">${icon('print')} Imprimer</a>
          <button class="btn quiet small" data-action="zone-edit" data-id="${z.id}">${icon('edit')} Modifier</button></div></header>
      <section class="section"><h2>Plantes <span class="muted small">${ps.length}</span></h2>
        ${ps.length ? html`<div class="pchips pchips-tight">${(zoneAll.has(z.id) ? ps : ps.slice(0, Z_MAX)).map((p) => html`<a class="pchip" href="#/plants/${p.id}" title="${cleanName(p.nom_francais) || p.nom_latin}">${thumb(p.image)}<span>${cleanName(p.nom_francais) || p.nom_latin}</span></a>`)}</div>
          ${ps.length > Z_MAX ? html`<div><button class="btn quiet small" data-action="zone-all" data-id="${z.id}">${zoneAll.has(z.id) ? 'Réduire la liste' : `Afficher les ${ps.length - Z_MAX} autres`}</button></div>` : ''}`
          : html`<p class="muted small">Aucune plante dans cette zone. Rattachez-en depuis leur fiche (« Choisir les zones »).</p>`}</section>
      <section class="section"><h2>Tâches à faire <span class="muted small">${ts.length}</span></h2>
        ${ts.length ? html`<ul class="list">${ts.map((t) => html`<li><a class="item" href="#/tasks/${t.id}"><span class="item-main"><span class="item-title">${t.title}</span><span class="item-sub">${t.category || ''}</span></span></a></li>`)}</ul>`
          : html`<p class="muted small">Rien à faire ici.</p>`}</section>`;
  },
};
actions['zone-all'] = (el) => { const id = Number(el.dataset.id); zoneAll.has(id) ? zoneAll.delete(id) : zoneAll.add(id); zones.draw(false); };
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
      <section class="block"><h2>Carte</h2><p class="muted small">Ouvre la carte de la propriété dans un nouvel onglet.</p>
        <div><a class="btn" href="/carte" target="_blank" rel="noopener">${icon('map')} Ouvrir la carte</a></div></section>
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
      <section class="block"><h2>Descriptions des plantes</h2><div id="repair-box"><p class="muted">Vérification…</p></div></section>
      <section class="block"><h2>Accès</h2><p class="muted small">Le site est protégé par un mot de passe. Votre appareil le retient 30 jours.</p>
        <div><button class="btn quiet" data-action="logout">Se déconnecter</button></div></section>
      <section class="block"><h2>Sauvegardes</h2><div id="backup-box"><p class="muted">Vérification…</p></div></section>
      <section class="block"><h2>Heures de récupération <span class="chip ${bal > 0 ? 'ok' : bal < 0 ? 'warn' : ''}">${bal >= 0 ? '+' : '−'}${hh(bal)}</span></h2>
        <div><button class="btn small" data-action="heure-add">${icon('plus')} Ajouter des heures</button></div>
        ${state.heures.length ? html`<ul class="list">${[...state.heures].sort((a, b) => String(b.date).localeCompare(String(a.date))).map((h) => html`<li><div class="item">
          <span class="item-main"><span class="item-title">${h.type === 'Supp' ? 'Heures supplémentaires' : 'Récupération'}</span><span class="item-sub">${fmtDate(h.date, { day: 'numeric', month: 'long', year: 'numeric' })}${h.note ? ' · ' + h.note : ''}</span></span>
          <span class="qty">${h.type === 'Supp' ? '+' : '−'}${hh(Number(h.duree))}</span></div></li>`)}</ul>` : emptyState('Aucune heure enregistrée', 'Suivez vos heures supplémentaires et vos récupérations.')}
      </section>
    </div></div>`);
    refreshRepair(); refreshBackups();
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
        ${[['cal', 'Calendrier du jardin', '#/calendar'], ['search', 'Rechercher une plante', '#/search'], ['box', 'Inventaire', '#/inventory'], ['map', 'Zones', '#/zones'], ['gear', 'Réglages et heures de récup', '#/settings']].map(([i, l, h]) => html`
          <li><a class="item" href="${h}">${icon(i)}<span class="item-main"><span class="item-title">${l}</span></span></a></li>`)}
      </ul></div></div>`);
  },
  route() {},
};

/* ---------- Réparation des descriptions ---------- */
let repairTimer = null, lastFinish = null;
async function refreshRepair() {
  const box = $('#repair-box');
  if (!box) { clearTimeout(repairTimer); return; }
  let r;
  try { r = await api('/library/repair-descriptions'); } catch { box.textContent = 'Indisponible pour le moment.'; return; }
  if (r.running) {
    mount(box, html`<p>Réparation en cours : <b>${r.done}</b> / ${r.total}${r.current ? html` · ${r.current}` : ''}</p>
      <progress max="${r.total}" value="${r.done}" style="width:100%"></progress>
      <p class="small muted">Vous pouvez quitter cette page, la réparation continue sur le serveur.</p>`);
    clearTimeout(repairTimer); repairTimer = setTimeout(refreshRepair, 3000);
    return;
  }
  const finished = r.finished_at ? html`<p class="chip ok">Terminé : ${r.fixed} fiche${r.fixed > 1 ? 's' : ''} réparée${r.fixed > 1 ? 's' : ''}${r.failed ? `, ${r.failed} échec${r.failed > 1 ? 's' : ''}` : ''}</p>` : '';
  if (r.finished_at && r.finished_at !== lastFinish) { lastFinish = r.finished_at; await load(); return; }
  mount(box, html`${finished}${r.pending
    ? html`<p>${r.pending} fiche${r.pending > 1 ? 's affichent' : ' affiche'} le texte d'entretien à la place de la présentation.</p>
      <div><button class="btn" data-action="repair-start">Récupérer les descriptions depuis Promesse de Fleurs</button></div>`
    : html`<p class="muted">Toutes les descriptions sont en place.</p>`}`);
}
actions['repair-start'] = async () => {
  await api('/library/repair-descriptions', { method: 'POST' });
  toast('Réparation lancée');
  refreshRepair();
};

/* ---------- Sauvegardes ---------- */
async function refreshBackups() {
  const box = $('#backup-box');
  if (!box) return;
  let r;
  try { r = await api('/backups'); } catch { box.textContent = 'Indisponible pour le moment.'; return; }
  if (!r.enabled) { mount(box, html`<p class="muted">Les sauvegardes nécessitent la base PostgreSQL.</p>`); return; }
  const last = r.backups[0];
  mount(box, html`<p>${last ? html`Dernière sauvegarde : <b>${new Date(last.created_at).toLocaleString('fr-FR', { dateStyle: 'long', timeStyle: 'short' })}</b>` : 'Aucune sauvegarde pour le moment.'}</p>
    <p class="small muted">Une copie est faite chaque jour dans la base (${r.backups.length} conservée${r.backups.length > 1 ? 's' : ''}, les 14 dernières). Gardez aussi un fichier chez vous.</p>
    <div class="chips"><button class="btn quiet" data-action="backup-now">Sauvegarder maintenant</button>
    <a class="btn" href="/api/export" download>${icon('box')} Télécharger mes données</a></div>`);
}
actions['logout'] = async () => { await api('/logout', { method: 'POST' }); location.reload(); };
actions['backup-now'] = async () => { await api('/backups', { method: 'POST' }); toast('Sauvegarde créée'); refreshBackups(); };
