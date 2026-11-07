// Tâches, inventaire, journal : trois vues liste + détail construites par la même fabrique.
import {
  $, html, raw, mount, icon, api, state, load, zoneById, actions, changes, inputs, toast, formDialog, confirmDialog,
  field, textInput, selectInput, zoneChecks, zonesFromForm, fmtDate, todayISO, norm, debounce, emptyState, backButton, esc,
} from './core.js';

let current = null; // section affichée (pour les filtres génériques)

function makeSection(cfg) {
  let root, sel = null;
  const f = { q: '', ...cfg.filters };
  const items = () => cfg.items(f);
  const section = {
    title: cfg.title, f,
    render(r, params) {
      root = r; current = section;
      mount(root, html`
        <div class="view" id="v-view">
          <section class="pane-list" aria-label="${cfg.title}">
            <div class="pane-head">
              <div class="pane-title"><h1>${cfg.title}</h1><span class="muted small" id="v-count" aria-live="polite"></span></div>
              <div class="search">${icon('search')}<input class="input" type="search" data-input="v-q" placeholder="Rechercher" aria-label="Rechercher" value="${f.q}"></div>
              ${cfg.head ? cfg.head(f) : ''}
              <div><button class="btn small" data-action="v-add">${icon('plus')} ${cfg.addLabel}</button></div>
            </div>
            <div id="v-list"></div>
          </section>
          <section class="pane-detail" id="v-detail" aria-live="polite"></section>
        </div>`);
      this.route(params);
    },
    route(params) {
      current = section;
      sel = params.id ?? null;
      const list = items();
      if (sel == null && list.length && matchMedia('(min-width: 720px)').matches) { location.replace(`#/${cfg.key}/${list[0].id}`); return; }
      draw();
    },
    update() { if (root) draw(); },
    refilter() { if (root) { drawList(); } },
    selected: () => cfg.find(sel),
    get sel() { return sel; },
  };
  function drawList() {
    const list = items();
    $('#v-count', root).textContent = cfg.count ? cfg.count(list) : `${list.length}`;
    mount($('#v-list', root), list.length ? cfg.list(list, sel, f) : cfg.empty());
  }
  function draw() {
    drawList();
    const item = sel == null ? null : cfg.find(sel);
    $('#v-view', root).dataset.open = item ? 'detail' : 'list';
    mount($('#v-detail', root), item ? html`${backButton('Retour')}${cfg.detail(item)}` : emptyState(cfg.pick[0], cfg.pick[1]));
  }
  return section;
}
inputs['v-q'] = debounce((el) => { current.f.q = el.value; current.refilter(); }, 120);
changes['v-filter'] = (el) => { current.f[el.dataset.k] = el.value; current.refilter(); };
actions['v-seg'] = (el) => {
  current.f[el.dataset.k] = el.dataset.v;
  el.parentElement.querySelectorAll('button').forEach((b) => b.setAttribute('aria-pressed', String(b === el)));
  current.refilter();
};
actions['v-add'] = () => current.add();

const seg = (key, value, options) => html`<div class="seg" role="group">${options.map(([v, l]) => html`<button data-action="v-seg" data-k="${key}" data-v="${v}" aria-pressed="${value === v}">${l}</button>`)}</div>`;
const matches = (q, ...texts) => !q || norm(texts.join(' ')).includes(norm(q));
const zoneChips = (ids) => (ids || []).map(zoneById).filter(Boolean).map((z) => html`<span class="chip ok">${z.icon || ''} ${z.nom}</span>`);
const actionBar = (editAct, delAct) => html`<div class="chips" style="margin-top:6px"><button class="btn quiet small" data-action="${editAct}">${icon('edit')} Modifier</button><button class="btn danger small" data-action="${delAct}">${icon('trash')} Supprimer</button></div>`;
const goList = (key) => { location.hash = `#/${key}`; };

/* =========================================================
   Tâches
   ========================================================= */
const TASK_CATS = ['Jardin', 'Piscine', 'Maison', 'Maçonnerie', 'Électrique', 'Autre'];
export const taskDone = (t) => t.status === 'done';
const subProgress = (t) => { const s = t.subtasks || []; return s.length ? `${s.filter((x) => x.completed).length}/${s.length}` : ''; };

export const tasks = makeSection({
  key: 'tasks', title: 'Tâches', addLabel: 'Nouvelle tâche', filters: { cat: '', zone: '', show: 'open' },
  pick: ['Choisissez une tâche', 'Ses étapes et ses zones s\'affichent ici.'],
  find: (id) => state.tasks.find((t) => Number(t.id) === Number(id)),
  items: (f) => state.tasks.filter((t) => matches(f.q, t.title, t.description) && (!f.cat || t.category === f.cat)
    && (!f.zone || (t.zones || []).map(Number).includes(Number(f.zone)))
    && (f.show === 'all' || (f.show === 'done') === taskDone(t))).sort((a, b) => (b.id - a.id)),
  count: (l) => `${l.length} ${l.length > 1 ? 'tâches' : 'tâche'}`,
  head: (f) => html`${seg('show', f.show, [['open', 'À faire'], ['done', 'Terminées'], ['all', 'Toutes']])}
    <div class="filters"><select class="select" data-change="v-filter" data-k="cat" aria-label="Catégorie"><option value="">Toutes catégories</option>${TASK_CATS.map((c) => html`<option ${raw(f.cat === c ? 'selected' : '')}>${c}</option>`)}</select>
    <select class="select" data-change="v-filter" data-k="zone" aria-label="Zone"><option value="">Toutes les zones</option>${state.zones.map((z) => html`<option value="${z.id}" ${raw(String(z.id) === String(f.zone) ? 'selected' : '')}>${z.icon || ''} ${z.nom}</option>`)}</select></div>`,
  empty: () => emptyState('Rien à faire ici', 'Aucune tâche ne correspond à ce filtre.'),
  list: (list, sel) => html`<ul class="list">${list.map((t) => html`<li class="${taskDone(t) ? 'done' : ''}">
    <div class="item" ${raw(Number(sel) === Number(t.id) ? 'aria-current="true"' : '')}>
      <input class="check" type="checkbox" data-change="task-toggle" data-id="${t.id}" ${raw(taskDone(t) ? 'checked' : '')} aria-label="Terminer « ${esc(t.title)} »">
      <a class="item-main" href="#/tasks/${t.id}"><span class="item-title">${t.title}</span>
        <span class="item-sub">${[t.category, subProgress(t) && `étapes ${subProgress(t)}`, (t.zones || []).map(zoneById).filter(Boolean).map((z) => z.nom).join(', ')].filter(Boolean).join(' · ')}</span></a>
    </div></li>`)}</ul>`,
  detail: (t) => html`
    <h1>${t.title}</h1>
    <div class="chips" style="margin-top:10px">${t.category ? html`<span class="chip">${t.category}</span>` : ''}
      <span class="chip ${taskDone(t) ? 'ok' : 'warn'}">${taskDone(t) ? `Terminée ${t.completed_at ? 'le ' + fmtDate(t.completed_at) : ''}` : 'À faire'}</span>
      ${zoneChips(t.zones)}</div>
    ${t.description ? html`<p class="prose" style="margin-top:18px">${t.description}</p>` : ''}
    <section class="section"><h2>Étapes <span class="muted small">${subProgress(t)}</span></h2>
      <ul class="list">${(t.subtasks || []).map((s, i) => html`<li class="${s.completed ? 'done' : ''}"><label class="item" style="min-height:48px"><input class="check" type="checkbox" data-change="subtask-toggle" data-id="${t.id}" data-i="${i}" ${raw(s.completed ? 'checked' : '')}><span class="item-main"><span class="item-title" style="white-space:normal">${s.text}</span></span></label></li>`)}</ul>
      <form data-form="subtask-add" data-id="${t.id}" style="display:flex;gap:8px"><input class="input" name="text" placeholder="Ajouter une étape" aria-label="Nouvelle étape" required><button class="btn quiet" type="submit">Ajouter</button></form>
    </section>
    ${actionBar('task-edit', 'task-del')}`,
});
const curTask = () => tasks.selected();
const patchTask = async (id, body) => { await api(`/tasks/${id}`, { method: 'PATCH', body }); await load(); };
changes['task-toggle'] = (el) => patchTask(el.dataset.id, { status: el.checked ? 'done' : 'todo' });
changes['subtask-toggle'] = (el) => {
  const t = state.tasks.find((x) => Number(x.id) === Number(el.dataset.id));
  const subtasks = t.subtasks.map((s, i) => (i === Number(el.dataset.i) ? { ...s, completed: el.checked } : s));
  return patchTask(t.id, { subtasks });
};
document.addEventListener('submit', (e) => {
  const form = e.target.closest('[data-form="subtask-add"]');
  if (!form) return;
  e.preventDefault();
  const t = state.tasks.find((x) => Number(x.id) === Number(form.dataset.id));
  const text = new FormData(form).get('text').trim();
  if (text) patchTask(t.id, { subtasks: [...(t.subtasks || []), { text, completed: false }] }).catch((err) => toast(err.message, 'error'));
});
const taskForm = (t) => html`${field('Titre', textInput('title', t?.title || '', 'required'))}
  <div class="row2">${field('Catégorie', selectInput('category', [...new Set([...TASK_CATS, t?.category].filter(Boolean))], t?.category || 'Jardin'))}</div>
  ${field('Description', html`<textarea class="textarea" name="description">${t?.description || ''}</textarea>`)}
  <div class="field"><span>Zones</span>${zoneChecks(t?.zones || [])}</div>`;
tasks.add = () => formDialog({ title: 'Nouvelle tâche', body: taskForm(null), submit: 'Créer', onSubmit: async (v, form) => {
  const r = await api('/tasks', { method: 'POST', body: { title: v.title, category: v.category, description: v.description, zones: zonesFromForm(form) } });
  await load(); location.hash = '#/tasks/' + r.task.id;
} });
actions['task-edit'] = () => { const t = curTask(); formDialog({ title: 'Modifier la tâche', body: taskForm(t), onSubmit: async (v, form) => {
  await patchTask(t.id, { title: v.title, category: v.category, description: v.description, zones: zonesFromForm(form) });
} }); };
actions['task-del'] = async () => {
  const t = curTask();
  if (!await confirmDialog(`Supprimer « ${t.title} » ?`)) return;
  await api(`/tasks/${t.id}`, { method: 'DELETE' }); await load(); goList('tasks');
};

/* =========================================================
   Inventaire
   ========================================================= */
const INV_GROUPS = [['Outillage', 'Outillage'], ['Matériaux', 'Matériaux'], ['Produits', 'Produits']];
const invGroup = (i) => (i.categorie === 'Matériau' ? 'Matériaux' : i.categorie === 'Produit' ? 'Produits' : 'Outillage');
export const lowStock = (i) => i.statut === 'Possédé' && Number(i.seuil_alerte) > 0 && Number(i.quantite) <= Number(i.seuil_alerte);
export const toBuy = (i) => i.statut === 'À acheter';
const needsCare = (i) => i.etat && i.etat !== 'Bon';

export const inventory = makeSection({
  key: 'inventory', title: 'Inventaire', addLabel: 'Nouvel article', filters: { show: 'all' },
  pick: ['Choisissez un article', 'Quantité, état et entretien s\'affichent ici.'],
  find: (id) => state.inventory.find((i) => Number(i.id) === Number(id)),
  items: (f) => state.inventory.filter((i) => matches(f.q, i.nom, i.notes)
    && (f.show === 'all' || (f.show === 'stock' ? lowStock(i) || toBuy(i) : invGroup(i) === f.show)))
    .sort((a, b) => a.nom.localeCompare(b.nom, 'fr')),
  count: (l) => `${l.length} article${l.length > 1 ? 's' : ''}`,
  head: (f) => seg('show', f.show, [['all', 'Tout'], ['Outillage', 'Outillage'], ['Matériaux', 'Matériaux'], ['Produits', 'Produits'], ['stock', 'Stock & achats']]),
  empty: () => emptyState('Aucun article', 'Ajoutez votre matériel, vos matériaux et vos produits.'),
  list: (list, sel) => html`${INV_GROUPS.map(([key, label]) => {
    const rows = list.filter((i) => invGroup(i) === key);
    return rows.length ? html`<h2 class="group-title">${label}</h2><ul class="list">${rows.map((i) => html`<li>
      <a class="item" href="#/inventory/${i.id}" ${raw(Number(sel) === Number(i.id) ? 'aria-current="true"' : '')}>
        <span class="item-main"><span class="item-title">${i.nom}</span>
          <span class="item-sub">${[toBuy(i) && 'À acheter', lowStock(i) && 'Stock bas', needsCare(i) && i.etat].filter(Boolean).join(' · ') || i.unite || ' '}</span></span>
        <span class="qty">${i.quantite}${i.unite ? ' ' + i.unite : ''}</span></a></li>`)}</ul>` : '';
  })}`,
  detail: (i) => html`
    <h1>${i.nom}</h1>
    <div class="chips" style="margin-top:10px"><span class="chip">${i.categorie}</span>
      <span class="chip ${toBuy(i) ? 'warn' : ''}">${i.statut}</span>
      ${needsCare(i) ? html`<span class="chip bad">${i.etat}</span>` : html`<span class="chip ok">Bon état</span>`}
      ${lowStock(i) ? html`<span class="chip warn">Stock bas</span>` : ''}</div>
    <div style="display:flex;align-items:center;gap:16px;margin-top:22px;flex-wrap:wrap">
      <div class="stepper" role="group" aria-label="Quantité"><button class="icon-btn" data-action="inv-qty" data-delta="-1" aria-label="Retirer un">${icon('minus')}</button>
        <output aria-live="polite">${i.quantite}</output><button class="icon-btn" data-action="inv-qty" data-delta="1" aria-label="Ajouter un">${icon('plus')}</button></div>
      <span class="muted">${i.unite || 'pièce(s)'} · alerte à ${i.seuil_alerte}</span></div>
    <dl class="facts" style="margin-top:24px">
      ${Number(i.prix_estime) ? html`<div><dt>Prix estimé</dt><dd>${i.prix_estime} €</dd></div>` : ''}
      ${i.dernier_entretien ? html`<div><dt>Dernier entretien</dt><dd>${fmtDate(i.dernier_entretien, { day: 'numeric', month: 'long', year: 'numeric' })}</dd></div>` : ''}
      ${i.date_expiration ? html`<div><dt>Expire le</dt><dd>${fmtDate(i.date_expiration, { day: 'numeric', month: 'long', year: 'numeric' })}</dd></div>` : ''}
    </dl>
    ${i.notes ? html`<section class="section"><h2>Notes</h2><p class="prose">${i.notes}</p></section>` : ''}
    ${actionBar('inv-edit', 'inv-del')}`,
});
const curItem = () => inventory.selected();
actions['inv-qty'] = async (el) => {
  const i = curItem();
  await api(`/inventory/${i.id}`, { method: 'PATCH', body: { quantite: Math.max(0, Number(i.quantite) + Number(el.dataset.delta)) } });
  await load();
};
const invForm = (i) => html`${field('Nom', textInput('nom', i?.nom || '', 'required'))}
  <div class="row2">${field('Catégorie', selectInput('categorie', [['Outil', 'Outillage'], ['Matériau', 'Matériau'], ['Produit', 'Produit'], ['Équipement', 'Équipement']], i?.categorie || 'Outil'))}
  ${field('Statut', selectInput('statut', ['Possédé', 'À acheter'], i?.statut || 'Possédé'))}</div>
  <div class="row2">${field('Quantité', textInput('quantite', i?.quantite ?? 1, 'type="number" min="0" step="any"'))}${field('Unité', textInput('unite', i?.unite || '', 'placeholder="pièce, kg, L, sacs…"'))}</div>
  <div class="row2">${field('Alerte quand il en reste', textInput('seuil_alerte', i?.seuil_alerte ?? 1, 'type="number" min="0" step="any"'))}${field('État', selectInput('etat', ['Bon', 'À réparer', 'À remplacer'], i?.etat || 'Bon'))}</div>
  <div class="row2">${field('Prix estimé (€)', textInput('prix_estime', i?.prix_estime || 0, 'type="number" min="0" step="any"'))}${field('Dernier entretien', textInput('dernier_entretien', i?.dernier_entretien || '', 'type="date"'))}</div>
  ${field('Notes', html`<textarea class="textarea" name="notes">${i?.notes || ''}</textarea>`)}`;
const invBody = (v) => ({ ...v, quantite: Number(v.quantite), seuil_alerte: Number(v.seuil_alerte), prix_estime: Number(v.prix_estime) });
inventory.add = () => formDialog({ title: 'Nouvel article', body: invForm(null), submit: 'Ajouter', onSubmit: async (v) => {
  const r = await api('/inventory', { method: 'POST', body: invBody(v) }); await load(); location.hash = '#/inventory/' + r.item.id;
} });
actions['inv-edit'] = () => { const i = curItem(); formDialog({ title: 'Modifier l\'article', body: invForm(i), onSubmit: async (v) => {
  await api(`/inventory/${i.id}`, { method: 'PATCH', body: invBody(v) }); await load();
} }); };
actions['inv-del'] = async () => {
  const i = curItem();
  if (!await confirmDialog(`Supprimer « ${i.nom} » ?`)) return;
  await api(`/inventory/${i.id}`, { method: 'DELETE' }); await load(); goList('inventory');
};

/* =========================================================
   Journal
   ========================================================= */
const J_CATS = ['Semis / Plantation', 'Entretien / Taille', 'Arrosage', 'Traitement', 'Travaux / Aménagement', 'Piscine', 'Observation', 'Problème détecté', 'Récolte', 'Autre'];

export const journal = makeSection({
  key: 'journal', title: 'Journal', addLabel: 'Nouvelle note', filters: { cat: '' },
  pick: ['Choisissez une note', 'Le détail de la journée s\'affiche ici.'],
  find: (id) => state.journal.find((e) => Number(e.id) === Number(id)),
  items: (f) => state.journal.filter((e) => matches(f.q, e.titre, e.notes, e.emplacement) && (!f.cat || e.categorie === f.cat)),
  count: (l) => `${l.length} note${l.length > 1 ? 's' : ''}`,
  head: (f) => html`<div class="filters"><select class="select" data-change="v-filter" data-k="cat" aria-label="Catégorie"><option value="">Toutes catégories</option>${J_CATS.map((c) => html`<option ${raw(f.cat === c ? 'selected' : '')}>${c}</option>`)}</select></div>`,
  empty: () => emptyState('Journal vide', 'Notez ce que vous faites au jardin : plantations, soins, observations.'),
  list: (list, sel) => {
    const days = [...new Set(list.map((e) => e.date))];
    return html`${days.map((day) => html`<h2 class="group-title">${fmtDate(day, { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' })}</h2>
      <ul class="list">${list.filter((e) => e.date === day).map((e) => html`<li><a class="item" href="#/journal/${e.id}" ${raw(Number(sel) === Number(e.id) ? 'aria-current="true"' : '')}>
        <span class="item-main"><span class="item-title">${e.titre || e.categorie}</span><span class="item-sub">${[e.heure, e.categorie, e.emplacement].filter(Boolean).join(' · ')}</span></span></a></li>`)}</ul>`)}`;
  },
  detail: (e) => html`
    <p class="muted">${fmtDate(e.date, { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' })}${e.heure ? ' · ' + e.heure : ''}</p>
    <h1>${e.titre || e.categorie}</h1>
    <div class="chips" style="margin-top:10px"><span class="chip">${e.categorie}</span>${e.emplacement ? html`<span class="chip">${e.emplacement}</span>` : ''}${e.zone_id ? zoneChips([e.zone_id]) : ''}${e.meteo ? html`<span class="chip">${e.meteo}</span>` : ''}</div>
    ${e.notes ? html`<p class="prose" style="margin-top:20px;white-space:pre-wrap">${e.notes}</p>` : ''}
    ${actionBar('j-edit', 'j-del')}`,
});
const curEntry = () => journal.selected();
const jForm = (e) => html`${field('Titre', textInput('titre', e?.titre || '', 'required'))}
  <div class="row2">${field('Date', textInput('date', e?.date || todayISO(), 'type="date" required'))}${field('Heure', textInput('heure', e?.heure || '', 'type="time"'))}</div>
  <div class="row2">${field('Catégorie', selectInput('categorie', J_CATS, e?.categorie || 'Observation'))}
  ${field('Zone', selectInput('zone_id', [['', 'Aucune'], ...state.zones.map((z) => [z.id, `${z.icon || ''} ${z.nom}`])], e?.zone_id ?? ''))}</div>
  ${field('Lieu précis', textInput('emplacement', e?.emplacement || ''))}
  ${field('Notes', html`<textarea class="textarea" name="notes" rows="5">${e?.notes || ''}</textarea>`)}`;
const jBody = (v) => ({ ...v, zone_id: v.zone_id === '' ? null : Number(v.zone_id) });
journal.add = () => formDialog({ title: 'Nouvelle note', body: jForm(null), submit: 'Ajouter', onSubmit: async (v) => {
  const r = await api('/journal', { method: 'POST', body: jBody(v) }); await load(); location.hash = '#/journal/' + r.entry.id;
} });
actions['j-edit'] = () => { const e = curEntry(); formDialog({ title: 'Modifier la note', body: jForm(e), onSubmit: async (v) => {
  await api(`/journal/${e.id}`, { method: 'PATCH', body: jBody(v) }); await load();
} }); };
actions['j-del'] = async () => {
  const e = curEntry();
  if (!await confirmDialog('Supprimer cette note ?')) return;
  await api(`/journal/${e.id}`, { method: 'DELETE' }); await load(); goList('journal');
};
