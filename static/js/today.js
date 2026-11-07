// Accueil : ce qu'il y a à faire aujourd'hui au jardin.
import { $, html, raw, mount, icon, api, state, actions, changes, notify, fmtDate, monthsOf, nowMonth, monthKey, plantById, zoneById, emptyState, esc } from './core.js';
import { lowStock, toBuy, taskDone } from './work.js';

let root, weather = undefined;

function greeting() {
  const h = new Date().getHours();
  return h < 5 ? 'Bonne nuit' : h < 18 ? 'Bonjour' : 'Bonsoir';
}

function weatherBlock() {
  if (weather === undefined) return html`<div class="weather"><div class="skeleton" style="height:48px;width:220px"></div></div>`;
  if (!weather || !weather.current) return '';
  const c = weather.current;
  return html`<section class="weather" aria-label="Météo à ${state.settings.meteo_ville || ''}">
    <div class="weather-now"><span style="font-size:2.4rem" aria-hidden="true">${c.icon}</span>
      <div><div class="big">${c.temp}°</div><div class="muted small">${c.description} · ${state.settings.meteo_ville || ''}</div></div></div>
    <div class="weather-days">${(weather.forecast || []).map((d) => html`<div><span>${d.day}</span><span style="font-size:1.4rem" aria-hidden="true">${d.icon}</span><b style="color:var(--ink)">${d.temp_max}°</b><span>${d.temp_min}°</span></div>`)}</div>
    ${(weather.alerts || []).map((a) => html`<p class="chip ${a.severity === 'high' ? 'bad' : 'warn'}" style="width:100%"><b>${a.icon} ${a.title}</b> ${a.message}${a.action ? ' · ' + a.action : ''}</p>`)}
    ${weather.demo ? html`<p class="small muted" style="width:100%">Données de démonstration : ajoutez OPENWEATHER_API_KEY sur Railway pour la météo réelle.</p>` : ''}
  </section>`;
}

function monthWork() {
  const m = nowMonth(), key = monthKey();
  const out = [];
  for (const p of state.plants) {
    const f = p.facts || {};
    for (const [type, label, field] of [['Taille', 'Tailler', 'periode_taille'], ['Récolte', 'Récolter', 'periode_recolte']]) {
      if (monthsOf(f[field]).has(m)) out.push({ p, type, label, period: f[field], done: !!state.reminders[`${p.id}_${type}_${key}`] });
    }
  }
  return out;
}

function draw() {
  if (!root) return;
  const open = state.tasks.filter((t) => !taskDone(t)).sort((a, b) => b.id - a.id);
  const stock = state.inventory.filter((i) => toBuy(i) || lowStock(i));
  const work = monthWork();
  const flowering = state.plants.filter((p) => monthsOf((p.facts || {}).periode_floraison).has(nowMonth()));
  const month = new Date().toLocaleDateString('fr-FR', { month: 'long' });
  mount(root, html`<div class="page-scroll"><div class="page">
    <header class="hello"><h1>${greeting()} Denis</h1><p class="date">${fmtDate(new Date().toISOString(), { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' })}</p></header>
    ${weatherBlock()}
    <nav class="stats" aria-label="Chiffres clés">
      <a href="#/plants"><b>${state.plants.length}</b><span>plantes</span></a>
      <a href="#/tasks"><b>${open.length}</b><span>tâches à faire</span></a>
      <a href="#/inventory"><b>${stock.length}</b><span>stock à surveiller</span></a>
      <a href="#/journal"><b>${state.journal.length}</b><span>notes au journal</span></a>
    </nav>
    <div class="cols">
      <section class="block"><h2>À faire <a class="small" href="#/tasks">Tout voir</a></h2>
        ${open.length ? html`<ul class="list">${open.slice(0, 6).map((t) => html`<li><div class="item">
          <input class="check" type="checkbox" data-change="task-toggle" data-id="${t.id}" aria-label="Terminer « ${esc(t.title)} »">
          <a class="item-main" href="#/tasks/${t.id}"><span class="item-title">${t.title}</span><span class="item-sub">${[t.category, (t.zones || []).map(zoneById).filter(Boolean).map((z) => z.nom).join(', ')].filter(Boolean).join(' · ')}</span></a></div></li>`)}</ul>`
          : emptyState('Tout est fait', 'Aucune tâche en attente.', html`<button class="btn small" data-action="v-add-task">${icon('plus')} Nouvelle tâche</button>`)}
      </section>
      <section class="block"><h2>Au jardin en ${month}</h2>
        ${work.length || flowering.length ? html`<ul class="list">
          ${work.map((w) => html`<li><label class="item" style="min-height:56px"><input class="check" type="checkbox" data-change="home-reminder" data-id="${w.p.id}" data-type="${w.type}" ${raw(w.done ? 'checked' : '')}>
            <span class="item-main"><span class="item-title">${w.label} · ${w.p.nom_francais || w.p.nom_latin}</span><span class="item-sub">${w.period}</span></span></label></li>`)}
          ${flowering.slice(0, 6).map((p) => html`<li><a class="item" href="#/plants/${p.id}"><span class="item-main"><span class="item-title">${p.nom_francais || p.nom_latin}</span><span class="item-sub">En fleurs ce mois-ci</span></span></a></li>`)}</ul>`
          : emptyState('Rien de prévu ce mois-ci', 'Les périodes de taille, récolte et floraison de vos plantes apparaîtront ici.')}
      </section>
      <section class="block"><h2>Stock à surveiller <a class="small" href="#/inventory">Inventaire</a></h2>
        ${stock.length ? html`<ul class="list">${stock.slice(0, 6).map((i) => html`<li><a class="item" href="#/inventory/${i.id}"><span class="item-main"><span class="item-title">${i.nom}</span><span class="item-sub">${toBuy(i) ? 'À acheter' : 'Stock bas'}</span></span><span class="qty">${i.quantite}</span></a></li>`)}</ul>`
          : emptyState('Stock au complet', 'Rien à racheter pour le moment.')}
      </section>
      <section class="block"><h2>Dernières notes <a class="small" href="#/journal">Journal</a></h2>
        ${state.journal.length ? html`<ul class="list">${state.journal.slice(0, 4).map((e) => html`<li><a class="item" href="#/journal/${e.id}"><span class="item-main"><span class="item-title">${e.titre || e.categorie}</span><span class="item-sub">${fmtDate(e.date)} · ${e.categorie}</span></span></a></li>`)}</ul>`
          : emptyState('Journal vide', 'Notez votre première journée au jardin.')}
      </section>
    </div>
  </div></div>`);
}

changes['home-reminder'] = async (el) => {
  const key = monthKey(), type = el.dataset.type, id = el.dataset.id;
  await api('/reminders/toggle', { method: 'POST', body: { plant_id: Number(id), reminder_type: type, month: key, is_checked: el.checked } });
  state.reminders[`${id}_${type}_${key}`] = el.checked;
};

actions['v-add-task'] = () => { location.hash = '#/tasks'; setTimeout(() => import('./work.js').then((m) => m.tasks.add()), 50); };

export const today = {
  title: "Aujourd'hui",
  render(r) {
    root = r; draw();
    if (weather === undefined) api('/weather').then((w) => { weather = w; }).catch(() => { weather = null; }).finally(() => { if (root === r) draw(); });
  },
  route() {},
  update: draw,
};
