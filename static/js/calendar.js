// Calendrier du jardin : ce qui fleurit, se taille, se récolte ou se plante, mois par mois.
import { $, html, raw, mount, icon, state, actions, monthsOf, MONTHS, nowMonth, thumb, emptyState } from './core.js';

const KINDS = [
  ['periode_floraison', 'Floraison', 'flo'],
  ['periode_taille', 'Taille', 'tai'],
  ['periode_recolte', 'Récolte', 'rec'],
  ['meilleure_periode_plantation', 'Plantation', 'pla'],
];
const FULL = ['janvier', 'février', 'mars', 'avril', 'mai', 'juin', 'juillet', 'août', 'septembre', 'octobre', 'novembre', 'décembre'];

let root, month = nowMonth(), mode = 'month', kind = 'periode_floraison';

const periods = (p, key) => monthsOf((p.facts || {})[key]);
const name = (p) => p.nom_francais || p.nom_latin;

function monthView() {
  return html`<div class="cols" style="grid-template-columns:repeat(auto-fit,minmax(260px,1fr))">${KINDS.map(([key, label, cls]) => {
    const list = state.plants.filter((p) => periods(p, key).has(month)).sort((a, b) => name(a).localeCompare(name(b), 'fr'));
    return html`<section class="block"><h2><span><i class="dot ${cls}"></i> ${label}</span><span class="muted small">${list.length}</span></h2>
      ${list.length ? html`<ul class="list">${list.map((p) => html`<li><a class="item" href="#/plants/${p.id}" style="min-height:56px">${thumb(p.image)}<span class="item-main"><span class="item-title">${name(p)}</span><span class="item-sub">${p.facts[key]}</span></span></a></li>`)}</ul>`
        : html`<p class="muted small" style="padding:8px 0">Rien ce mois-ci.</p>`}</section>`;
  })}</div>`;
}

function yearView() {
  const cls = KINDS.find(([k]) => k === kind)[2];
  const rows = state.plants.map((p) => ({ p, set: periods(p, kind) })).filter((r) => r.set.size)
    .sort((a, b) => Math.min(...a.set) - Math.min(...b.set) || name(a.p).localeCompare(name(b.p), 'fr'));
  if (!rows.length) return emptyState('Aucune période renseignée', 'Les fiches de vos plantes n\'indiquent pas cette période.');
  const cur = nowMonth();
  return html`<div class="year" role="table" aria-label="Calendrier annuel">
    <div class="year-row year-head" role="row"><span role="columnheader"></span>${MONTHS.map((n, m) => html`<b role="columnheader" class="${m === cur ? 'now' : ''}">${n.replace('.', '')}</b>`)}</div>
    ${rows.map(({ p, set }) => html`<a class="year-row" role="row" href="#/plants/${p.id}"><span class="year-name" role="rowheader">${name(p)}</span>${MONTHS.map((_, m) => html`<i role="cell" class="${cls} ${set.has(m) ? 'on' : ''} ${m === cur ? 'now' : ''}" ${raw(set.has(m) ? `aria-label="${MONTHS[m]}"` : 'aria-hidden="true"')}></i>`)}</a>`)}
  </div>`;
}

function draw() {
  if (!root) return;
  const withData = state.plants.filter((p) => KINDS.some(([k]) => periods(p, k).size)).length;
  mount(root, html`<div class="page-scroll"><div class="page" style="max-width:1100px">
    <div class="page-head"><div><h1>Calendrier</h1><p class="muted">${withData} plantes avec des périodes renseignées sur ${state.plants.length}.</p></div>
      <div class="seg" role="group" aria-label="Affichage"><button data-action="cal-mode" data-v="month" aria-pressed="${mode === 'month'}">Par mois</button><button data-action="cal-mode" data-v="year" aria-pressed="${mode === 'year'}">Toute l'année</button></div></div>
    ${mode === 'month'
      ? html`<div class="seg" role="group" aria-label="Mois">${MONTHS.map((n, m) => html`<button data-action="cal-month" data-m="${m}" aria-pressed="${month === m}">${n.replace('.', '')}</button>`)}</div>
        <h2><span style="text-transform:capitalize">${FULL[month]}</span>${month === nowMonth() ? html` <span class="chip ok">ce mois-ci</span>` : ''}</h2>${monthView()}`
      : html`<div class="seg" role="group" aria-label="Type de période">${KINDS.map(([k, l]) => html`<button data-action="cal-kind" data-k="${k}" aria-pressed="${kind === k}">${l}</button>`)}</div>${yearView()}`}
  </div></div>`);
  const on = $('[data-action=cal-month][aria-pressed=true]', root);
  if (on) on.scrollIntoView({ inline: 'center', block: 'nearest' });
}

actions['cal-mode'] = (el) => { mode = el.dataset.v; draw(); };
actions['cal-month'] = (el) => { month = Number(el.dataset.m); draw(); };
actions['cal-kind'] = (el) => { kind = el.dataset.k; draw(); };

export const calendar = {
  title: 'Calendrier',
  render(r) { root = r; draw(); },
  route() {},
  update: draw,
};
