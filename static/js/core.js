// Noyau : gabarits HTML sûrs, API, état partagé, dialogues, notifications, utilitaires.

/* ---------- gabarit html : tout est échappé sauf ce qui vient d'un autre html`` ---------- */
class Safe { constructor(s) { this.s = s; } toString() { return this.s; } }
const ESC = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' };
export const esc = (v) => String(v ?? '').replace(/[&<>"']/g, (c) => ESC[c]);
const part = (v) => (v instanceof Safe ? v.s : Array.isArray(v) ? v.map(part).join('') : v === false || v == null ? '' : esc(v));
export const html = (strings, ...vals) => new Safe(strings.reduce((out, s, i) => out + part(vals[i - 1]) + s));
export const raw = (s) => new Safe(String(s));
export const mount = (el, tpl) => { el.innerHTML = part(tpl); };

export const $ = (sel, root = document) => root.querySelector(sel);
export const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];

export const icon = (name) => raw(`<svg aria-hidden="true" focusable="false"><use href="#i-${name}"/></svg>`);

/* ---------- API ---------- */
export async function api(path, { method = 'GET', body } = {}) {
  const init = { method, headers: {} };
  if (body !== undefined) { init.body = JSON.stringify(body); init.headers['Content-Type'] = 'application/json'; }
  const res = await fetch('/api' + path, init);
  let data = null;
  try { data = await res.json(); } catch { /* corps vide */ }
  if (!res.ok) throw new Error((data && data.error) || `Erreur ${res.status}`);
  return data;
}

/* ---------- état partagé ---------- */
export const state = {
  loaded: false, plants: [], zones: [], tags: [], tasks: [], inventory: [], journal: [],
  heures: [], settings: {}, reminders: {},
};
const subs = new Set();
export const subscribe = (fn) => { subs.add(fn); return () => subs.delete(fn); };
export const notify = () => subs.forEach((fn) => fn());

export async function load() {
  const d = await api('/bootstrap');
  Object.assign(state, {
    plants: (d.plants || []).map((p) => ({ ...p, nom_francais: cleanName(p.nom_francais) })), zones: d.zones || [], tags: d.tags || [], tasks: d.tasks || [],
    inventory: d.inventory || [], journal: d.journal || [], heures: d.heures || [],
    settings: d.settings || {}, reminders: d.reminder_states || {}, loaded: true,
  });
  notify();
}
export async function reloadSilently() { try { await load(); } catch (e) { console.warn(e); } }

// Certaines fiches importées répètent le nom deux fois (« Agave montana Agave montana »)
export function cleanName(s) {
  const t = String(s || '').trim().replace(/\s+/g, ' ');
  const w = t.split(' ');
  if (w.length >= 2 && w.length % 2 === 0) {
    const a = w.slice(0, w.length / 2).join(' '), b = w.slice(w.length / 2).join(' ');
    if (a.toLowerCase() === b.toLowerCase()) return a;
  }
  return t;
}
export const zoneById = (id) => state.zones.find((z) => Number(z.id) === Number(id));
export const plantById = (id) => state.plants.find((p) => Number(p.id) === Number(id));

/* ---------- actions déléguées (un seul écouteur par type d'événement) ---------- */
export const actions = {};
export const inputs = {};
export const changes = {};
document.addEventListener('click', (e) => {
  const el = e.target.closest('[data-action]');
  if (!el || el.disabled) return;
  const fn = actions[el.dataset.action];
  if (fn) { if (el.tagName === 'A' && !el.getAttribute('href')) e.preventDefault(); Promise.resolve(fn(el, e)).catch(fail); }
});
document.addEventListener('input', (e) => { const el = e.target.closest('[data-input]'); if (el && inputs[el.dataset.input]) inputs[el.dataset.input](el, e); });
document.addEventListener('change', (e) => {
  const el = e.target.closest('[data-change]');
  if (el && changes[el.dataset.change]) Promise.resolve(changes[el.dataset.change](el, e)).catch(fail);
});

/* ---------- notifications ---------- */
export function toast(message, kind = '') {
  const host = $('#toasts');
  if (!host) return;
  const t = document.createElement('div');
  t.className = 'toast ' + kind;
  t.textContent = message;
  host.append(t);
  setTimeout(() => t.remove(), kind === 'error' ? 6000 : 2800);
}
export function fail(err) { console.error(err); toast(err.message || 'Une erreur est survenue', 'error'); }

/* ---------- dialogues natifs ---------- */
function dialogEl() { return $('#sheet'); }
export function closeDialog() { const d = dialogEl(); if (d.open) d.close(); }

export function formDialog({ title, body, submit = 'Enregistrer', danger = '', onSubmit, onDanger }) {
  const d = dialogEl();
  mount(d, html`
    <form method="dialog" id="dlg-form" autocomplete="off">
      <div class="dlg-head"><h2>${title}</h2>
        <button type="button" class="icon-btn" data-action="close-dialog" aria-label="Fermer">${icon('x')}</button></div>
      <div class="dlg-body">${body}</div>
      <div class="dlg-foot">
        ${danger ? html`<button type="button" class="btn danger" id="dlg-danger" style="margin-right:auto">${danger}</button>` : ''}
        <button type="button" class="btn quiet" data-action="close-dialog">Annuler</button>
        <button type="submit" class="btn">${submit}</button>
      </div>
    </form>`);
  const form = $('#dlg-form', d);
  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    const btn = form.querySelector('[type=submit]');
    btn.disabled = true;
    try {
      await onSubmit(Object.fromEntries(new FormData(form)), form);
      closeDialog();
    } catch (err) { fail(err); btn.disabled = false; }
  });
  if (danger) $('#dlg-danger', d).addEventListener('click', async () => {
    try { if (await onDanger()) closeDialog(); } catch (err) { fail(err); }
  });
  d.showModal();
  const first = form.querySelector('input:not([type=hidden]), textarea, select');
  if (first && !matchMedia('(pointer: coarse)').matches) first.focus();
}
actions['close-dialog'] = () => closeDialog();

export function confirmDialog(message, label = 'Supprimer') {
  return new Promise((resolve) => {
    const d = dialogEl();
    mount(d, html`
      <form method="dialog">
        <div class="dlg-body" style="padding-top:22px"><h2>${message}</h2></div>
        <div class="dlg-foot">
          <button type="button" class="btn quiet" value="no">Annuler</button>
          <button type="button" class="btn danger" value="yes">${label}</button>
        </div>
      </form>`);
    const done = (v) => { d.removeEventListener('close', onClose); d.close(); resolve(v); };
    const onClose = () => resolve(false);
    d.addEventListener('close', onClose, { once: true });
    d.querySelectorAll('button[value]').forEach((b) => b.addEventListener('click', () => done(b.value === 'yes')));
    d.showModal();
  });
}

/* ---------- champs de formulaire ---------- */
export const field = (label, control) => html`<label class="field"><span>${label}</span>${control}</label>`;
export const textInput = (name, value = '', attrs = '') => html`<input class="input" name="${name}" value="${value}" ${raw(attrs)}>`;
export const selectInput = (name, options, value = '') => html`<select class="select" name="${name}">${options.map((o) => {
  const [v, l] = Array.isArray(o) ? o : [o, o];
  return html`<option value="${v}" ${raw(String(v) === String(value) ? 'selected' : '')}>${l}</option>`;
})}</select>`;
export const zoneChecks = (selected = []) => html`<fieldset style="border:0;padding:0;margin:0"><legend class="visually-hidden">Zones</legend>
  <div class="chips">${state.zones.map((z) => html`
    <label class="chip" style="cursor:pointer"><input type="checkbox" name="zone" value="${z.id}" ${raw(selected.map(Number).includes(Number(z.id)) ? 'checked' : '')}>
    ${z.icon || ''} ${z.nom}</label>`)}</div></fieldset>`;
export const zonesFromForm = (form) => [...form.querySelectorAll('input[name=zone]:checked')].map((i) => Number(i.value));

/* ---------- dates & mois ---------- */
export const MONTHS = ['janv.', 'févr.', 'mars', 'avr.', 'mai', 'juin', 'juil.', 'août', 'sept.', 'oct.', 'nov.', 'déc.'];
const FULL = ['janvier', 'fevrier', 'mars', 'avril', 'mai', 'juin', 'juillet', 'aout', 'septembre', 'octobre', 'novembre', 'decembre'];
export function monthsOf(text) {
  const t = String(text || '').toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g, '');
  if (/toute l.?annee/.test(t)) return new Set([...Array(12).keys()]);
  const set = new Set();
  let prev = null, range = false;
  for (const tk of t.match(/[a-z]+/g) || []) {
    if (tk === 'a' || tk === 'au' || tk === 'jusqu' || tk === 'jusqua') { if (prev !== null) range = true; continue; }
    const m = tk.length >= 3 ? FULL.findIndex((n) => n.startsWith(tk)) : -1;
    if (m < 0) continue;
    if (range && prev !== null) { for (let i = prev; ; i = (i + 1) % 12) { set.add(i); if (i === m) break; } range = false; }
    else set.add(m);
    prev = m;
  }
  return set;
}
export const nowMonth = () => new Date().getMonth();
export const monthKey = (d = new Date()) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`;
export const todayISO = () => { const d = new Date(); return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`; };
export const fmtDate = (iso, opts = { day: 'numeric', month: 'long' }) => {
  if (!iso) return '';
  const d = new Date(String(iso).slice(0, 10) + 'T12:00:00');
  return isNaN(d) ? String(iso) : d.toLocaleDateString('fr-FR', opts);
};

export const norm = (s) => String(s || '').toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g, '');
export const debounce = (fn, ms = 250) => { let t; return (...a) => { clearTimeout(t); t = setTimeout(() => fn(...a), ms); }; };

export function resizeImage(file, max = 1100, quality = 0.82) {
  return new Promise((resolve, reject) => {
    const img = new Image();
    img.onload = () => {
      const k = Math.min(1, max / Math.max(img.width, img.height));
      const c = document.createElement('canvas');
      c.width = Math.round(img.width * k); c.height = Math.round(img.height * k);
      c.getContext('2d').drawImage(img, 0, 0, c.width, c.height);
      URL.revokeObjectURL(img.src);
      resolve(c.toDataURL('image/jpeg', quality));
    };
    img.onerror = () => reject(new Error("Image illisible"));
    img.src = URL.createObjectURL(file);
  });
}

/* ---------- morceaux d'interface partagés ---------- */
export const emptyState = (title, text, actionHtml = '') => html`<div class="empty"><h3>${title}</h3><p>${text}</p>${actionHtml}</div>`;
export const backButton = (label = 'Retour') => html`<button class="btn quiet small back" data-action="back">${icon('back')} ${label}</button>`;
export const thumb = (src, fallback = '🌿') => html`<span class="thumb">${src ? html`<img src="${src}" alt="" loading="lazy" decoding="async" width="52" height="52">` : fallback}</span>`;

export function ribbonRows(rows) {
  const cur = nowMonth();
  const used = rows.filter((r) => r.months.size);
  if (!used.length) return '';
  return html`<div class="ribbon" role="img" aria-label="${used.map((r) => `${r.label} : ${[...r.months].sort((a, b) => a - b).map((m) => MONTHS[m]).join(', ')}`).join(' ; ')}">
    ${used.map((r) => html`<div class="ribbon-row"><span>${r.label}</span>${MONTHS.map((_, m) => html`<i class="${r.cls} ${r.months.has(m) ? 'on' : ''} ${m === cur ? 'now' : ''}"></i>`)}</div>`)}
    <div class="ribbon-row months" aria-hidden="true"><span></span>${MONTHS.map((n, m) => html`<b class="${m === cur ? 'now' : ''}">${n[0].toUpperCase()}</b>`)}</div>
  </div>`;
}
