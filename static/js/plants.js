// Bibliothèque de plantes (fiche « herbier ») et recherche Promesse de Fleurs.
import {
  $, html, raw, mount, icon, api, state, notify, load, plantById, zoneById, actions, inputs, changes, toast,
  formDialog, confirmDialog, field, textInput, monthsOf, ribbonRows, monthKey, norm, debounce, resizeImage,
  emptyState, backButton, thumb, MONTHS, nowMonth, cleanName, esc,
} from './core.js';
import { newTaskForPlant, taskDone } from './work.js';

const safeUrl = (u) => (/^https?:\/\//i.test(u || '') ? u : '');

/* =========================================================
   Fiche de plante (bibliothèque ET aperçu de recherche)
   ========================================================= */
const GROUPS = [
  ['Allure', [['Hauteur adulte', 'hauteur_maturite'], ['Largeur adulte', 'largeur_maturite'], ['Port', 'port'], ['Croissance', 'croissance'],
    ['Couleur des fleurs', 'couleur_fleur'], ['Floraison', 'periode_floraison'], ['Inflorescence', 'inflorescence'], ['Taille des fleurs', 'taille_fleur'],
    ['Feuillage', 'persistance_feuillage'], ['Couleur du feuillage', 'couleur_feuillage']]],
  ['Culture', [['Exposition', 'exposition'], ['Rusticité', 'rusticite'], ['Zone USDA', 'zone_usda'], ['Type de sol', 'type_sol'], ['Humidité du sol', 'humidite_sol'],
    ['pH du sol', 'ph_sol'], ['Difficulté', 'difficulte_culture'], ['Convient pour', 'convient_pour'], ['Utilisation', 'type_utilisation'], ['Climat', 'climat_preference']]],
  ['Entretien', [['Taille', 'taille'], ['Période de taille', 'periode_taille'], ['Fréquence de taille', 'frequence_taille'], ['Densité de plantation', 'densite_plantation'],
    ['Plantation idéale', 'meilleure_periode_plantation'], ['Plantation possible', 'periode_raisonnable_plantation'], ['Arrosage', 'arrosage_conseils'],
    ['Maladies', 'resistance_maladies'], ['Hivernage', 'hivernage']]],
  ['Identité', [['Famille', 'famille'], ['Genre', 'genre'], ['Espèce', 'espece'], ['Cultivar', 'cultivar'], ['Origine', 'origine'], ['Autres noms', 'autres_noms']]],
];

/* ---- Repères : valeurs partagées par plusieurs plantes, cliquables pour filtrer la bibliothèque ---- */
export const glue = (v) => String(v ?? '').replace(/([a-zà-ÿ])([A-ZÀ-Ý])/g, '$1, $2'); // « SoleilMi-ombre » → « Soleil, Mi-ombre »
function facetTokens(v) {
  const out = []; let cur = '', depth = 0;
  for (const ch of glue(v)) {
    if (ch === '(') depth++; else if (ch === ')') depth = Math.max(0, depth - 1);
    if ((ch === ',' || ch === ';') && !depth) { out.push(cur); cur = ''; } else cur += ch;
  }
  out.push(cur);
  return out.map((t) => t.trim()).filter(Boolean);
}
const FACET_LABEL_SET = new Set(['hauteur_maturite','largeur_maturite','port','croissance','couleur_fleur','periode_floraison','inflorescence','taille_fleur','persistance_feuillage','couleur_feuillage','exposition','rusticite','zone_usda','type_sol','humidite_sol','ph_sol','difficulte_culture','convient_pour','type_utilisation','climat_preference','periode_taille','frequence_taille','meilleure_periode_plantation','periode_raisonnable_plantation','famille','genre','espece','cultivar','origine','autres_noms']);
const FACET_LABEL = Object.fromEntries(GROUPS.flatMap(([, rows]) => rows.map(([l, k]) => [k, l])));
let facetCounts = null, facetCountsFor = null;
function counts() {
  if (facetCountsFor !== state.plants) {
    facetCounts = {};
    for (const p of state.plants) for (const [k, v] of Object.entries(p.facets || {})) for (const t of new Set(facetTokens(v).map(norm))) (facetCounts[k + '|' + t] ||= new Set()).add(p.id);
    facetCountsFor = state.plants;
  }
  return facetCounts;
}
function facetValue(key, value, link) {
  const toks = facetTokens(value);
  if (!link) return toks.join(', ');
  const c = counts();
  return html`<span class="facets">${toks.map((t) => {
    const n = (c[key + '|' + norm(t)] || new Set()).size;
    return n >= 2 ? html`<button type="button" class="facet" data-action="facet-go" data-k="${key}" data-v="${t}" title="${n} plantes : ${t}" aria-label="${t} — voir les ${n} plantes">${t}<span class="n">${n}</span></button>` : html`<span class="facet solo">${t}</span>`;
  })}</span>`;
}

/* ---- Navigation par ancres : raccourcis vers les sections + repère de la section visible en faisant défiler ---- */
const NAV_LABEL = { 'Dans mon jardin': 'Mon jardin', 'Plantation et soins': 'Soins', 'Conseils de taille': 'Taille' };
let navAbort = null;
const scrollParent = (el) => {
  for (let n = el.parentElement; n; n = n.parentElement) {
    const o = getComputedStyle(n).overflowY;
    if ((o === 'auto' || o === 'scroll') && n.scrollHeight > n.clientHeight) return n;
  }
  return window;
};
function enhanceSheet(container) {
  if (navAbort) navAbort.abort();
  const article = container.querySelector('article[aria-labelledby="sheet-title"]');
  const nav = article && article.querySelector('.sheet-nav');
  if (!nav) return;
  const secs = [...article.querySelectorAll(':scope > section.section')].map((el, i) => {
    const t = (el.querySelector('h2')?.firstChild?.textContent || el.querySelector('h2')?.textContent || '').trim();
    el.id = el.id || `sec-${i}`;
    return t ? { el, label: NAV_LABEL[t] || t } : null;
  }).filter(Boolean);
  if (secs.length < 3) return;
  nav.hidden = false;
  nav.innerHTML = secs.map((s2, i) => `<button type="button" data-action="sheet-jump" data-i="${i}">${esc(s2.label)}</button>`).join('');
  const btns = [...nav.querySelectorAll('button')];
  navAbort = new AbortController();
  const sc = scrollParent(nav);
  let current = -1;
  const spy = () => {
    const top = sc === window ? 0 : sc.getBoundingClientRect().top;
    const line = top + nav.offsetHeight + 24;
    let idx = 0;
    secs.forEach((s2, i) => { if (s2.el.getBoundingClientRect().top <= line) idx = i; });
    const atEnd = sc === window ? innerHeight + scrollY >= document.documentElement.scrollHeight - 4 : sc.scrollTop + sc.clientHeight >= sc.scrollHeight - 4;
    if (atEnd) idx = secs.length - 1;
    if (idx === current) return;
    current = idx;
    btns.forEach((b, i) => { if (i === idx) b.setAttribute('aria-current', 'true'); else b.removeAttribute('aria-current'); });
    const b = btns[idx]; nav.scrollTo({ left: b.offsetLeft - (nav.clientWidth - b.offsetWidth) / 2, behavior: 'auto' });
  };
  sc.addEventListener('scroll', spy, { passive: true, signal: navAbort.signal });
  nav._secs = secs; spy();
}
actions['sheet-jump'] = (el) => {
  const nav = el.closest('.sheet-nav'); const t = nav._secs[Number(el.dataset.i)];
  if (t) t.el.scrollIntoView({ behavior: matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth', block: 'start' });
};

function plantSheet(m, mine = '', actionsBar = '') {
  const d = m.details || {};
  const cal = ribbonRows([
    { label: 'Floraison', cls: 'flo', months: monthsOf(d.periode_floraison) },
    { label: 'Taille', cls: 'tai', months: monthsOf(d.periode_taille) },
    { label: 'Récolte', cls: 'rec', months: monthsOf(d.periode_recolte) },
    { label: 'Plantation', cls: 'pla', months: monthsOf(d.meilleure_periode_plantation) },
  ]);
  // description_courte = présentation de la plante ; description_detaillee = conseils « Plantations et soins »
  const care = d.description_detaillee || '';
  const same = (a, b) => { if (!a || !b) return false; const n = Math.min(a.trim().length, b.trim().length, 60); return n >= 20 && a.trim().slice(0, n) === b.trim().slice(0, n); };
  let intro = d.description_courte || m.description || '';
  if (same(intro, care)) intro = ''; // l'ancienne version avait enregistré le texte d'entretien comme présentation
  const gallery = (d.images_galerie || []).filter(safeUrl).slice(0, 6);
  const link = safeUrl(m.url);
  return html`
    <article aria-labelledby="sheet-title">
      ${backButton('Retour')}
      <header class="sheet-head">
        <div class="sheet-names">
          <h1 id="sheet-title">${m.nom_francais || m.nom_latin}</h1>
          ${m.nom_francais && m.nom_latin ? html`<p class="latin">${m.nom_latin}</p>` : ''}
          <div class="chips">
            ${m.type ? html`<span class="chip">${m.type}</span>` : ''}
            ${m.exposition ? html`<span class="chip">${glue(m.exposition).replace(/, /g, ', ')}</span>` : ''}
            ${d.rusticite ? html`<span class="chip">${d.rusticite}</span>` : ''}
            ${m.prix ? html`<span class="chip">${m.prix}</span>` : ''}
            ${(m.zones || []).map((z) => html`<span class="chip ok">${z.icon || ''} ${z.nom}</span>`)}
          </div>
          ${actionsBar}
        </div>
        <div class="sheet-photo">${m.image ? html`<button type="button" data-action="photo-zoom" data-src="${m.image}" aria-label="Agrandir la photo"><img src="${m.image}" alt="${m.nom_francais || m.nom_latin}" fetchpriority="high" decoding="async"></button>` : '🌿'}</div>
      </header>

      <nav class="sheet-nav" aria-label="Sections de la fiche" hidden></nav>
      ${cal ? html`<section class="section" aria-labelledby="h-cal"><h2 id="h-cal">Calendrier</h2>${cal}</section>` : ''}
      ${mine}
      ${intro ? html`<section class="section" aria-labelledby="h-desc"><h2 id="h-desc">Description</h2><p class="prose">${intro}</p></section>` : ''}
      ${!intro && m.refreshable ? html`<section class="section"><h2>Description</h2><p class="muted">La présentation de cette plante n'a pas été enregistrée correctement.</p>
        <div><button class="btn quiet small" data-action="plant-refresh">Récupérer la description depuis Promesse de Fleurs</button></div></section>` : ''}
      ${care ? html`<section class="section" aria-labelledby="h-care"><h2 id="h-care">Plantation et soins</h2><p class="prose">${care}</p></section>` : ''}
      ${GROUPS.map(([title, rows]) => {
        const present = rows.filter(([, k]) => d[k] && String(d[k]).trim());
        if (!present.length) return '';
        return html`<section class="section"><h2>${title}</h2><dl class="facts">${present.map(([l, k]) => html`<div><dt>${l}</dt><dd>${FACET_LABEL_SET.has(k) ? facetValue(k, d[k], m.linkFacets) : d[k]}</dd></div>`)}</dl></section>`;
      })}
      ${d.descriptif_taille_detaille ? html`<section class="section"><h2>Conseils de taille</h2><p class="prose">${d.descriptif_taille_detaille}</p></section>` : ''}
      ${gallery.length ? html`<section class="section"><h2>Photos</h2><div class="gallery">${gallery.map((g) => html`<button type="button" data-action="photo-zoom" data-src="${g}" aria-label="Agrandir la photo"><img src="${g}" alt="" loading="lazy" decoding="async" width="160" height="160"></button>`)}</div></section>` : ''}
      ${link ? html`<p class="small muted" style="margin-top:28px">Source : <a href="${link}" target="_blank" rel="noopener">Promesse de Fleurs</a></p>` : ''}
    </article>`;
}

/* =========================================================
   Bibliothèque
   ========================================================= */
let pRoot, pFilters = { q: '', zone: '', type: '', sort: 'recent', facet: null }, pSel = null, pCur = null;

const addedAt = (p) => Date.parse(p.added_at) || 0;
function plantList() {
  const q = norm(pFilters.q);
  return state.plants.filter((p) => (!q || norm(p.nom_francais + ' ' + p.nom_latin).includes(q))
    && (!pFilters.zone || p.zones.includes(Number(pFilters.zone)))
    && (!pFilters.type || p.type_plante === pFilters.type)
    && (!pFilters.facet || facetTokens((p.facets || {})[pFilters.facet.k]).some((t) => norm(t) === norm(pFilters.facet.v))))
    .sort((a, b) => (pFilters.sort === 'recent' ? addedAt(b) - addedAt(a) || b.id - a.id : pFilters.sort === 'oldest' ? addedAt(a) - addedAt(b) || a.id - b.id
      : (a.nom_francais || a.nom_latin).localeCompare(b.nom_francais || b.nom_latin, 'fr')));
}

function renderFacetBar() {
  const box = $('#p-facet', pRoot); if (!box) return;
  const f = pFilters.facet;
  mount(box, f ? html`<div class="chips"><span class="chip ok">${FACET_LABEL[f.k] || f.k} : ${f.v}</span><button type="button" class="chip" data-action="facet-clear" aria-label="Retirer le filtre">${icon('x')} Retirer le filtre</button></div>` : '');
}
function renderPlantList() {
  renderFacetBar();
  const list = plantList();
  $('#p-count', pRoot).textContent = `${list.length} ${list.length > 1 ? 'plantes' : 'plante'}`;
  mount($('#p-list', pRoot), list.length ? html`<ul class="list">${list.map((p) => html`
    <li><a class="item" href="#/plants/${p.id}" ${raw(Number(pSel) === p.id ? 'aria-current="true"' : '')}>
      ${thumb(p.image)}
      <span class="item-main"><span class="item-title">${p.nom_francais || p.nom_latin}</span>
        <span class="item-sub latin">${p.nom_latin}</span></span>
      ${p.quantity ? html`<span class="qty" title="Exemplaires">×${p.quantity}</span>` : ''}
    </a></li>`)}</ul>`
    : state.plants.length ? emptyState('Aucun résultat', 'Essayez un autre nom ou retirez un filtre.')
      : emptyState('Votre bibliothèque est vide', 'Cherchez une plante pour commencer votre collection.', html`<a class="btn" href="#/search">${icon('search')} Rechercher une plante</a>`));
}

async function loadPlant(id) {
  pCur = null;
  const detail = $('#p-detail', pRoot);
  if (id == null) { mount(detail, emptyState('Choisissez une plante', 'Sa fiche complète s\'affiche ici : calendrier, culture, entretien, notes.')); return; }
  const summary = plantById(id);
  mount(detail, html`<div class="skeleton" style="height:34px;width:50%"></div><div class="skeleton" style="height:240px;margin-top:20px"></div>`);
  try {
    const r = await api(`/library/plant/${id}`);
    if (Number(pSel) !== Number(id)) return;
    pCur = { id: Number(id), r, summary };
    renderPlantDetail();
  } catch (e) {
    mount(detail, emptyState('Plante introuvable', e.message, html`<a class="btn quiet" href="#/plants">Retour à la liste</a>`));
  }
}

function remindersBlock(c) {
  const d = (c.r.plant && c.r.plant.details) || {};
  const m = nowMonth(), key = monthKey();
  const due = [['Taille', d.periode_taille, 'tai'], ['Récolte', d.periode_recolte, 'rec']].filter(([, p]) => monthsOf(p).has(m));
  if (!due.length) return '';
  return html`<div style="display:grid;gap:8px"><h3>Ce mois-ci</h3>${due.map(([type, period]) => {
    const done = state.reminders[`${c.id}_${type}_${key}`];
    return html`<label class="item" style="padding:6px 0;min-height:44px"><input class="check" type="checkbox" data-change="reminder" data-type="${type}" ${raw(done ? 'checked' : '')}>
      <span class="item-main"><span class="item-title">${type === 'Taille' ? 'Tailler' : 'Récolter'}</span><span class="item-sub">${period}</span></span></label>`;
  })}</div>`;
}

function tasksBlock(c) {
  const list = state.tasks.filter((t) => (t.plants || []).map(Number).includes(c.id)).sort((a, b) => Number(taskDone(a)) - Number(taskDone(b)) || b.id - a.id);
  return html`<div style="display:grid;gap:8px"><h3>Tâches</h3>
    ${list.length ? html`<ul class="list">${list.map((t) => html`<li class="${taskDone(t) ? 'done' : ''}"><div class="item">
      <input class="check" type="checkbox" data-change="plant-task-toggle" data-id="${t.id}" ${raw(taskDone(t) ? 'checked' : '')} aria-label="Terminer « ${t.title} »">
      <a class="item-main" href="#/tasks/${t.id}"><span class="item-title">${t.title}</span><span class="item-sub">${t.category || ''}</span></a></div></li>`)}</ul>`
      : html`<p class="muted small">Aucune tâche liée à cette plante.</p>`}
    <div><button class="btn quiet small" data-action="plant-task-add">${icon('plus')} Nouvelle tâche pour cette plante</button></div></div>`;
}

function renderPlantDetail() {
  const c = pCur; if (!c) return;
  const { r, summary } = c;
  const p = r.plant || {};
  const zones = (summary ? summary.zones : []).map(zoneById).filter(Boolean);
  const photo = summary && summary.image;
  const d = p.details || {};
  const model = {
    nom_francais: cleanName(p.nom_francais), nom_latin: p.nom_latin, image: photo || d.image_principale || '',
    type: p.type_plante || d.type_plante, exposition: p.exposition || d.exposition, prix: p.prix, url: p.url,
    description: d.description_courte || p.description, details: d, zones, refreshable: !!safeUrl(p.url), linkFacets: true,
  };
  const myTags = new Set((r.tags || []).map((t) => t.id));
  const mine = html`<section class="section" aria-labelledby="h-mine"><h2 id="h-mine">Dans mon jardin</h2>
    <div style="display:flex;align-items:center;gap:20px;flex-wrap:wrap">
      <div class="stepper" role="group" aria-label="Nombre d'exemplaires">
        <button class="icon-btn" data-action="plant-qty" data-delta="-1" aria-label="Un exemplaire de moins">${icon('minus')}</button>
        <output aria-live="polite">${r.quantity || 0}</output>
        <button class="icon-btn" data-action="plant-qty" data-delta="1" aria-label="Un exemplaire de plus">${icon('plus')}</button>
      </div>
      <button class="btn quiet small" data-action="plant-zones">${icon('map')} ${zones.length ? 'Changer les zones' : 'Choisir les zones'}</button>
      <button class="btn quiet small" data-action="plant-photo">${icon('camera')} ${photo && photo.includes('/photo') ? 'Changer ma photo' : 'Ajouter ma photo'}</button>
      ${photo && photo.includes('/photo') ? html`<button class="btn quiet small" data-action="plant-photo-del">Retirer ma photo</button>` : ''}
      <input type="file" id="p-file" accept="image/*" hidden>
    </div>
    ${remindersBlock(c)}
    ${tasksBlock(c)}
    <div class="chips" role="group" aria-label="Repères">${state.tags.map((t) => html`
      <button class="chip" aria-pressed="${myTags.has(t.id)}" data-action="plant-tag" data-id="${t.id}"><span aria-hidden="true" style="width:10px;height:10px;border-radius:50%;background:${t.color}"></span>${t.name}</button>`)}
      <button class="chip" data-action="tag-new">${icon('plus')} Nouveau repère</button></div>
    <label class="field"><span>Notes</span><textarea class="textarea" id="p-notes" placeholder="Date de plantation, soins, observations…">${r.notes || ''}</textarea></label>
    <div><button class="btn small" data-action="plant-notes">Enregistrer les notes</button></div>
  </section>`;
  const bar = html`<div class="chips"><button class="btn danger small" data-action="plant-delete">${icon('trash')} Retirer de ma bibliothèque</button></div>`;
  mount($('#p-detail', pRoot), plantSheet(model, mine, bar));
  enhanceSheet($('#p-detail', pRoot));
}

const savePlantNotes = async (notes, quantity) => {
  await api(`/library/${pCur.id}/notes`, { method: 'PUT', body: { notes, quantity } });
  const s = plantById(pCur.id);
  if (s) { s.quantity = quantity; s.has_notes = !!notes.trim(); }
  pCur.r.notes = notes; pCur.r.quantity = quantity;
};

actions['facet-go'] = (el) => {
  pFilters.facet = { k: el.dataset.k, v: el.dataset.v }; pFilters.q = ''; pFilters.zone = ''; pFilters.type = '';
  if (matchMedia('(min-width: 720px)').matches) { const q = $('#p-q', pRoot); if (q) q.value = ''; renderPlantList(); }
  else location.hash = '#/plants';
};
actions['plants-print'] = () => { location.hash = `#/print?ids=${plantList().map((p) => p.id).join(',')}&t=${encodeURIComponent(pFilters.facet ? `${FACET_LABEL[pFilters.facet.k] || ''} : ${pFilters.facet.v}` : 'Ma sélection')}`; };
actions['facet-clear'] = () => { pFilters.facet = null; renderPlantList(); };
actions['plant-task-add'] = () => newTaskForPlant(pCur.id, () => renderPlantDetail());
changes['plant-task-toggle'] = async (el) => {
  await api(`/tasks/${el.dataset.id}`, { method: 'PATCH', body: { status: el.checked ? 'done' : 'todo' } });
  await load(); renderPlantDetail();
};
actions['plant-qty'] = async (el) => {
  const next = Math.max(0, (pCur.r.quantity || 0) + Number(el.dataset.delta));
  await savePlantNotes(pCur.r.notes || '', next);
  renderPlantDetail(); renderPlantList();
};
actions['plant-notes'] = async () => { await savePlantNotes($('#p-notes').value, pCur.r.quantity || 0); toast('Notes enregistrées'); };
actions['plant-zones'] = () => {
  const cur = (pCur.summary ? pCur.summary.zones : []);
  formDialog({
    title: 'Zones de la plante',
    body: state.zones.length ? html`<div class="chips">${state.zones.map((z) => html`<label class="chip" style="cursor:pointer;min-height:36px"><input type="checkbox" name="z${z.id}" ${raw(cur.includes(Number(z.id)) ? 'checked' : '')}> ${z.icon || ''} ${z.nom}</label>`)}</div>`
      : html`<p>Aucune zone créée. <a href="#/zones" data-action="close-dialog">Créer une zone</a></p>`,
    onSubmit: async (v) => {
      const ids = state.zones.filter((z) => v['z' + z.id] !== undefined).map((z) => Number(z.id));
      await api(`/library/${pCur.id}/zone`, { method: 'PUT', body: { zone_ids: ids } });
      if (pCur.summary) pCur.summary.zones = ids;
      renderPlantDetail(); renderPlantList();
    },
  });
};
actions['plant-tag'] = async (el) => {
  const id = Number(el.dataset.id), on = el.getAttribute('aria-pressed') === 'true';
  if (on) await api(`/library/${pCur.id}/tags/${id}`, { method: 'DELETE' });
  else await api(`/library/${pCur.id}/tags`, { method: 'POST', body: { tag_id: id } });
  const t = state.tags.find((x) => x.id === id);
  pCur.r.tags = on ? pCur.r.tags.filter((x) => x.id !== id) : [...pCur.r.tags, t];
  if (pCur.summary) pCur.summary.tags = pCur.r.tags.map((x) => x.id);
  renderPlantDetail();
};
actions['tag-new'] = () => formDialog({
  title: 'Nouveau repère',
  body: html`${field('Nom', textInput('name', '', 'required maxlength="40"'))}${field('Couleur', raw('<input class="input" type="color" name="color" value="#5a4a9b" style="padding:4px">'))}`,
  onSubmit: async (v) => {
    await api('/tags', { method: 'POST', body: { name: v.name, color: v.color } });
    await load(); if (pCur) renderPlantDetail();
  },
});
actions['plant-refresh'] = async (el) => {
  const p = pCur.r.plant;
  el.disabled = true; el.textContent = 'Récupération…';
  try {
    const res = await api(`/plant/detail?url=${encodeURIComponent(p.url)}`);
    const fresh = Object.fromEntries(Object.entries(res.data || {}).filter(([, v]) => v && (typeof v !== 'object' || Object.keys(v).length)));
    if (!fresh.description_courte) throw new Error('Aucune description trouvée sur la page');
    const details = { ...(p.details || {}), ...fresh };
    await api('/library/get-or-create-id', { method: 'POST', body: { nom_francais: p.nom_francais, nom_latin: p.nom_latin, details, description: fresh.description_courte } });
    toast('Description récupérée');
    await loadPlant(pCur.id);
  } catch (e) { el.disabled = false; el.textContent = 'Récupérer la description depuis Promesse de Fleurs'; throw e; }
};
actions['photo-zoom'] = (el) => {
  const d = $('#zoom'); $('img', d).src = el.dataset.src; d.showModal();
};
actions['zoom-close'] = () => $('#zoom').close();
document.addEventListener('click', (e) => { const d = $('#zoom'); if (d.open && e.target.closest('#zoom')) d.close(); });
actions['plant-photo'] = () => $('#p-file').click();
changes['reminder'] = async (el) => {
  const key = monthKey(), type = el.dataset.type;
  await api('/reminders/toggle', { method: 'POST', body: { plant_id: pCur.id, reminder_type: type, month: key, is_checked: el.checked } });
  state.reminders[`${pCur.id}_${type}_${key}`] = el.checked;
  notify();
};
document.addEventListener('change', async (e) => {
  if (e.target.id !== 'p-file' || !e.target.files[0] || !pCur) return;
  try {
    const photo = await resizeImage(e.target.files[0]);
    await api(`/library/plant/${pCur.id}/photo`, { method: 'POST', body: { photo } });
    await load(); pCur.summary = plantById(pCur.id); renderPlantDetail(); toast('Photo enregistrée');
  } catch (err) { toast(err.message, 'error'); }
});
actions['plant-photo-del'] = async () => {
  await api(`/library/plant/${pCur.id}/photo`, { method: 'DELETE' });
  await load(); pCur.summary = plantById(pCur.id); renderPlantDetail();
};
actions['plant-delete'] = async () => {
  const name = cleanName(pCur.r.plant.nom_francais) || pCur.r.plant.nom_latin;
  if (!await confirmDialog(`Retirer « ${name} » de votre bibliothèque ?`, 'Retirer')) return;
  await api(`/library/${pCur.id}`, { method: 'DELETE' });
  await load(); toast('Plante retirée'); location.hash = '#/plants';
};

export const plants = {
  title: 'Plantes',
  render(root, params) {
    pRoot = root;
    const types = [...new Set(state.plants.map((p) => p.type_plante).filter(Boolean))].sort();
    mount(root, html`
      <div class="view" id="p-view">
        <section class="pane-list" aria-label="Liste des plantes">
          <div class="pane-head">
            <div class="pane-title"><h1>Plantes</h1><span class="muted small" id="p-count" aria-live="polite"></span></div>
            <div class="search">${icon('search')}<input class="input" type="search" id="p-q" data-input="plant-q" placeholder="Filtrer ma collection" aria-label="Filtrer ma collection" value="${pFilters.q}"></div>
            <div class="filters">
              <select class="select" data-change="plant-zone" aria-label="Zone"><option value="">Toutes les zones</option>${state.zones.map((z) => html`<option value="${z.id}" ${raw(String(z.id) === String(pFilters.zone) ? 'selected' : '')}>${z.icon || ''} ${z.nom}</option>`)}</select>
              <select class="select" data-change="plant-type" aria-label="Type"><option value="">Tous les types</option>${types.map((t) => html`<option ${raw(t === pFilters.type ? 'selected' : '')}>${t}</option>`)}</select>
              <select class="select" data-change="plant-sort" aria-label="Trier par">${[['recent', 'Derniers ajoutés'], ['oldest', 'Premiers ajoutés'], ['name', 'Nom A → Z']].map(([v, l]) => html`<option value="${v}" ${raw(pFilters.sort === v ? 'selected' : '')}>${l}</option>`)}</select>
              <a class="btn small" href="#/search" style="margin-left:auto">${icon('plus')} Ajouter</a>
              <button type="button" class="btn quiet small" data-action="plants-print" title="Imprimer les plantes de cette liste">${icon('print')} Imprimer</button>
            </div>
          </div>
          <div id="p-facet" style="padding:0 16px"></div>
          <div id="p-list"></div>
        </section>
        <section class="pane-detail" id="p-detail" aria-live="polite"></section>
      </div>`);
    renderPlantList();
    this.route(params);
  },
  route(params) {
    pSel = params.id ?? null;
    $('#p-view', pRoot).dataset.open = pSel == null ? 'list' : 'detail';
    renderPlantList();
    if (pSel == null) { if (matchMedia('(min-width: 720px)').matches && state.plants.length) { location.replace('#/plants/' + plantList()[0].id); return; } loadPlant(null); }
    else loadPlant(pSel);
  },
  update() { if (pRoot) renderPlantList(); },
};
inputs['plant-q'] = debounce((el) => { pFilters.q = el.value; renderPlantList(); }, 120);
changes['plant-zone'] = (el) => { pFilters.zone = el.value; renderPlantList(); };
changes['plant-sort'] = (el) => { pFilters.sort = el.value; renderPlantList(); };
changes['plant-type'] = (el) => { pFilters.type = el.value; renderPlantList(); };

/* =========================================================
   Recherche Promesse de Fleurs
   ========================================================= */
let sRoot, sQuery = '', sResults = null, sSel = null, sDetail = null, sRecent = [], sBusy = false;
const inLibrary = (r) => state.plants.find((p) => p.nom_francais === (r.nom_francais || '').trim() && p.nom_latin === (r.nom_latin || '').trim());

function renderResults() {
  const box = $('#s-list', sRoot);
  if (sBusy) { mount(box, html`<div class="results">${[1, 2, 3, 4, 5, 6].map(() => html`<div><div class="skeleton" style="aspect-ratio:1"></div><div class="skeleton" style="height:14px;margin-top:8px"></div></div>`)}</div>`); return; }
  if (sResults === null) {
    mount(box, html`<div class="empty"><h3>Quelle plante cherchez-vous ?</h3><p>Les fiches viennent de Promesse de Fleurs : variétés, calendrier, culture et entretien.</p>
      ${sRecent.length ? html`<div class="chips" style="justify-content:center">${sRecent.map((q) => html`<button class="chip" data-action="search-go" data-q="${q}">${q}</button>`)}</div>` : ''}</div>`);
    return;
  }
  mount(box, sResults.length ? html`<div class="results" role="list">${sResults.map((r, i) => {
    const mine = inLibrary(r);
    return html`<button class="result" role="listitem" data-action="search-pick" data-i="${i}" ${raw(sSel === i ? 'aria-current="true"' : '')}>
      <span class="pic" aria-hidden="true">${r.icon || '🌿'}</span>
      <span><b>${cleanName(r.nom_francais) || r.nom_latin}</b><br><span class="latin small muted">${r.nom_latin}</span>
      ${mine ? html`<br><span class="chip ok small">Dans ma bibliothèque</span>` : r.prix ? html`<br><span class="small muted">${r.prix}</span>` : ''}</span></button>`;
  })}</div>` : emptyState('Aucun résultat', `Rien pour « ${sQuery} ». Essayez le nom courant ou latin.`));
}

async function runSearch(q) {
  q = q.trim(); if (q.length < 2) return;
  sQuery = q; sBusy = true; sSel = null; sDetail = null; renderResults(); renderPreview();
  $('#s-q', sRoot).value = q;
  try { sResults = (await api(`/search?q=${encodeURIComponent(q)}&max=24`)).results || []; }
  catch (e) { sResults = []; toast(e.message, 'error'); }
  sBusy = false; renderResults();
}

function renderPreview() {
  const view = $('#s-view', sRoot), box = $('#s-detail', sRoot);
  view.dataset.open = sSel == null ? 'list' : 'detail';
  if (sSel == null) { mount(box, emptyState('Aperçu de la fiche', 'Choisissez un résultat pour voir tous ses détails avant de l\'ajouter.')); return; }
  const r = sResults[sSel];
  if (!sDetail) { mount(box, html`${backButton('Résultats')}<div class="skeleton" style="height:34px;width:55%"></div><div class="skeleton" style="height:260px;margin-top:20px"></div>`); return; }
  const d = sDetail;
  const mine = inLibrary(r);
  const bar = mine ? html`<div class="chips"><a class="btn quiet small" href="#/plants/${mine.id}">Voir dans ma bibliothèque</a></div>`
    : html`<div class="chips"><button class="btn" data-action="search-add">${icon('plus')} Ajouter à ma bibliothèque</button></div>`;
  mount(box, plantSheet({
    nom_francais: cleanName(d.nom_francais || r.nom_francais), nom_latin: d.nom_latin || r.nom_latin, image: d.image_principale,
    type: d.type_plante || r.type_plante, exposition: d.exposition || r.exposition, prix: r.prix, url: r.url,
    description: d.description_courte || r.description, details: d, zones: [],
  }, '', bar));
  enhanceSheet(box);
}

actions['search-go'] = (el) => runSearch(el.dataset.q);
actions['search-pick'] = async (el) => {
  sSel = Number(el.dataset.i); sDetail = null; renderResults(); renderPreview();
  const r = sResults[sSel], mySel = sSel;
  try {
    const res = await api(`/plant/detail?url=${encodeURIComponent(r.url)}`);
    if (sSel !== mySel) return;
    sDetail = res.data; renderPreview();
  } catch (e) { toast(e.message, 'error'); sSel = null; renderPreview(); renderResults(); }
};
actions['search-add'] = async (el) => {
  const r = sResults[sSel], d = sDetail;
  el.disabled = true;
  const res = await api('/library/get-or-create-id', { method: 'POST', body: {
    nom_francais: d.nom_francais || r.nom_francais, nom_latin: d.nom_latin || r.nom_latin,
    exposition: d.exposition || r.exposition, type_plante: d.type_plante || r.type_plante, prix: r.prix,
    description: d.description_courte || r.description, icon: r.icon, url: r.url, details: d, image_principale: d.image_principale || '',
  } });
  await load(); toast('Plante ajoutée'); location.hash = '#/plants/' + res.plant_id;
};

export const search = {
  title: 'Recherche',
  async render(root) {
    sRoot = root;
    mount(root, html`
      <div class="view" id="s-view" data-open="list">
        <section class="pane-list" aria-label="Recherche">
          <div class="pane-head">
            <div class="pane-title"><h1>Recherche</h1></div>
            <form class="search" id="s-form" role="search">${icon('search')}<input class="input" id="s-q" type="search" placeholder="Lavande, rosier, olivier…" aria-label="Rechercher une plante" value="${sQuery}" enterkeyhint="search" autocomplete="off"></form>
          </div>
          <div id="s-list"></div>
        </section>
        <section class="pane-detail" id="s-detail" aria-live="polite"></section>
      </div>`);
    $('#s-form', root).addEventListener('submit', (e) => { e.preventDefault(); runSearch($('#s-q', root).value); });
    renderResults(); renderPreview();
    if (!sRecent.length) api('/suggestions').then((s) => { sRecent = s.recent_searches || []; if (sResults === null && sRoot === root) renderResults(); }).catch(() => {});
  },
  route() {},
  back() { sSel = null; sDetail = null; renderPreview(); renderResults(); },
  update() { if (sRoot && sResults) renderResults(); },
};
