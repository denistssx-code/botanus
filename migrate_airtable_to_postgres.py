"""
Migration Airtable -> PostgreSQL.

- Ne modifie JAMAIS Airtable (lecture seule).
- Pagine toutes les tables (l'ancien client ne lisait que les 100 premiers
  enregistrements des tables Tâches, Tags, Inventaire, Journal, Zones, Rappels).
- Garde une copie brute de chaque table dans la table `airtable_backup`.
- Idempotente : les lignes déjà présentes ne sont jamais écrasées.
- Conserve les identifiants utilisés par l'app (les plantes gardent leur numéro
  d'ordre actuel, donc zones, rappels et favoris pointent toujours au bon endroit).

Usage :
    python migrate_airtable_to_postgres.py            # une fois, si pas déjà fait
    python migrate_airtable_to_postgres.py --force    # relance (sans rien écraser)

main.py l'appelle automatiquement au premier démarrage si DATABASE_URL et les
variables Airtable sont toutes présentes.
"""

import json
import os
import sys
import time
from typing import Dict, List

import requests

FLAG = 'airtable_imported_at'
SUMMARY = 'airtable_import_summary'


def _table_names() -> Dict[str, str]:
    env = os.environ.get
    return {
        'plants': env('AIRTABLE_TABLE_PLANTES', 'Plantes'),
        'tags': env('AIRTABLE_TABLE_TAGS', 'Tags'),
        'tasks': env('AIRTABLE_TABLE_TACHES', 'Taches'),
        'inventory': env('AIRTABLE_TABLE_INVENTAIRE', 'Inventaire'),
        'journal': env('AIRTABLE_TABLE_JOURNAL', 'Journal'),
        'reminders': env('AIRTABLE_TABLE_RAPPELS', 'Rappels'),
        'zones': env('AIRTABLE_TABLE_ZONES', 'Zones'),
        'settings': env('AIRTABLE_TABLE_SETTINGS', 'Settings'),
        'heures_recup': 'HeuresRecup',
    }


def fetch_all(table: str) -> List[Dict]:
    """Lit TOUS les enregistrements d'une table Airtable (pagination + 429)."""
    api_key = os.environ['AIRTABLE_API_KEY']
    base_id = os.environ['AIRTABLE_BASE_ID']
    url = f"https://api.airtable.com/v0/{base_id}/{table}"
    headers = {'Authorization': f'Bearer {api_key}'}

    records, offset = [], None
    while True:
        params = {'pageSize': 100}
        if offset:
            params['offset'] = offset
        for attempt in range(5):
            resp = requests.get(url, headers=headers, params=params, timeout=30)
            if resp.status_code == 429:
                time.sleep(30)  # limite Airtable : 5 req/s, pénalité de 30 s
                continue
            break
        resp.raise_for_status()  # on préfère échouer que migrer à moitié
        payload = resp.json()
        records.extend(payload.get('records', []))
        offset = payload.get('offset')
        if not offset:
            return records


def _int(value):
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _zone_ids_text(fields: Dict, rec_to_zone: Dict[str, int]) -> str:
    """Normalise le champ formule `zone_ids` ("10,7", 10, [10, 7]) en "10,7"."""
    raw = fields.get('zone_ids')
    ids: List[int] = []
    if isinstance(raw, list):
        ids = [i for i in (_int(x) for x in raw) if i is not None]
    elif isinstance(raw, (int, float)):
        ids = [int(raw)]
    elif isinstance(raw, str) and raw.strip():
        ids = [i for i in (_int(x) for x in raw.split(',')) if i is not None]
    if not ids:  # repli : champ de liaison -> ids numériques
        ids = [rec_to_zone[r] for r in fields.get('zones', []) if r in rec_to_zone]
    return ",".join(str(i) for i in ids)


def _build_rows(raw: Dict[str, List[Dict]]) -> Dict[str, List[Dict]]:
    rows: Dict[str, List[Dict]] = {}

    # --- zones (en premier : les autres tables s'y réfèrent)
    rec_to_zone: Dict[str, int] = {}
    rows['zones'] = []
    for rec in raw['zones']:
        f = rec.get('fields', {})
        zone_id = _int(f.get('zone_id'))
        if zone_id is None:
            continue
        rec_to_zone[rec['id']] = zone_id
        rows['zones'].append({
            'id': zone_id, 'nom': f.get('nom', ''), 'icon': f.get('icon', '🗺️'),
            'description': f.get('description', ''), 'created_at': f.get('created_at', ''),
        })

    # --- tags
    rows['tags'] = []
    for rec in raw['tags']:
        f = rec.get('fields', {})
        tag_id = _int(f.get('tag_id'))
        if tag_id is None:
            continue
        rows['tags'].append({
            'id': tag_id, 'name': f.get('name', ''), 'color': f.get('color', '#4CAF50'),
            'created_at': f.get('created_at', ''),
        })

    # --- tâches
    rows['tasks'] = []
    for rec in raw['tasks']:
        f = rec.get('fields', {})
        task_id = _int(f.get('task_id'))
        if task_id is None:
            continue
        subtasks = []
        if f.get('subtasks'):
            try:
                subtasks = json.loads(f['subtasks'])
            except (TypeError, ValueError):
                subtasks = []
        zones = [rec_to_zone[r] for r in f.get('zones', []) if r in rec_to_zone]
        zone_id = _int(f.get('zone_id')) or (zones[0] if zones else None)
        if zone_id and zone_id not in zones:
            zones.insert(0, zone_id)
        rows['tasks'].append({
            'id': task_id, 'title': f.get('title', ''), 'description': f.get('description', ''),
            'category': f.get('category', 'Autre'), 'status': f.get('status', 'todo'),
            'created_at': f.get('created_at', ''), 'completed_at': f.get('completed_at') or None,
            'zone_id': zone_id, 'zones': zones, 'subtasks': subtasks,
        })

    # --- inventaire
    rows['inventory'] = []
    for rec in raw['inventory']:
        f = rec.get('fields', {})
        item_id = _int(f.get('inventory_id'))
        if item_id is None:
            continue
        rows['inventory'].append({
            'id': item_id, 'nom': f.get('nom', ''), 'categorie': f.get('categorie', 'Outil'),
            'statut': f.get('statut', 'Possédé'), 'etat': f.get('etat', 'Bon'),
            'quantite': f.get('quantite', 1), 'unite': f.get('unite', ''),
            'seuil_alerte': f.get('seuil_alerte', 1), 'prix_estime': f.get('prix_estime', 0),
            'date_expiration': f.get('date_expiration', ''),
            'dernier_entretien': f.get('dernier_entretien', ''),
            'notes': f.get('notes', ''), 'created_at': f.get('created_at', ''),
        })

    # --- journal
    rows['journal'] = []
    for rec in raw['journal']:
        f = rec.get('fields', {})
        entry_id = _int(f.get('journal_id'))
        if entry_id is None:
            continue
        rows['journal'].append({
            'id': entry_id, 'date': f.get('date', ''), 'heure': f.get('heure', ''),
            'categorie': f.get('categorie', 'Autre'), 'emplacement': f.get('emplacement', ''),
            'zone_id': _int(f.get('zone_id')), 'titre': f.get('titre', ''),
            'notes': f.get('notes', ''), 'meteo': f.get('meteo', ''),
            'created_at': f.get('created_at', ''),
        })

    # --- rappels
    rows['reminders'] = []
    for rec in raw['reminders']:
        f = rec.get('fields', {})
        plant_id = _int(f.get('plant_id'))
        if plant_id is None or 'reminder_type' not in f:
            continue
        rows['reminders'].append({
            'plant_id': plant_id, 'reminder_type': f['reminder_type'],
            'month': f.get('month', ''), 'is_checked': bool(f.get('is_checked', False)),
            'checked_date': f.get('checked_date', ''),
        })

    # --- plantes : id = rang dans la liste Airtable, exactement comme le faisait
    # main.py au démarrage (les plantes sans nom gardent leur rang mais sont ignorées)
    rows['plants'] = []
    for idx, rec in enumerate(raw['plants'], start=1):
        f = dict(rec.get('fields', {}))
        nom_francais = (f.get('nom_francais') or '').strip()
        nom_latin = (f.get('nom_latin') or '').strip()
        if not nom_francais and not nom_latin:
            continue
        f['zone_ids'] = _zone_ids_text(f, rec_to_zone)
        f.pop('zones', None)  # ids d'enregistrements Airtable, remplacés par zone_ids
        rows['plants'].append({
            'id': idx, 'nom_latin': nom_latin, 'nom_francais': nom_francais, 'fields': f,
        })

    # --- heures récup
    rows['heures_recup'] = []
    for idx, rec in enumerate(raw['heures_recup'], start=1):
        f = rec.get('fields', {})
        rows['heures_recup'].append({
            'id': idx, 'date': f.get('Date', ''), 'type': f.get('Type', 'Supp'),
            'duree': f.get('Duree', 0), 'note': f.get('Note', ''),
            'statut': f.get('Statut', 'À récupérer'),
        })

    return rows


def run(db, force: bool = False) -> Dict:
    """Exécute la migration vers `db` (un PostgresClient actif)."""
    if not force and db.get_meta(FLAG):
        print(f"ℹ️ Migration Airtable déjà effectuée le {db.get_meta(FLAG)}, rien à faire")
        return json.loads(db.get_meta(SUMMARY) or '{}')

    print("\n" + "=" * 60)
    print("📦 MIGRATION AIRTABLE -> POSTGRESQL")
    print("=" * 60)

    names = _table_names()
    raw: Dict[str, List[Dict]] = {}
    for key, table in names.items():
        raw[key] = fetch_all(table)
        print(f"📥 {table}: {len(raw[key])} enregistrements")
        db.save_backup(table, raw[key])

    rows = _build_rows(raw)

    summary = {}
    for table in ('zones', 'tags', 'plants', 'tasks', 'inventory', 'journal',
                  'reminders', 'heures_recup'):
        inserted = db.import_rows(table, rows[table])
        summary[table] = {'airtable': len(raw[table if table != 'heures_recup' else 'heures_recup']),
                          'prepares': len(rows[table]), 'inserted': inserted}
        flag = '' if inserted == len(rows[table]) else '  (déjà présentes ou doublons ignorés)'
        print(f"✅ {table}: {inserted}/{len(rows[table])} importées{flag}")

    # Settings
    for rec in raw['settings']:
        f = rec.get('fields', {})
        if f.get('user_id') == 'default':
            db.import_settings({
                'meteo_ville': f.get('meteo_ville', 'Malaucène'),
                'meteo_latitude': f.get('meteo_latitude', 44.1736),
                'meteo_longitude': f.get('meteo_longitude', 5.1314),
                'meteo_mode': f.get('meteo_mode', 'ville'),
            })
            break

    db.set_meta(SUMMARY, json.dumps(summary))
    db.set_meta(FLAG, time.strftime('%Y-%m-%d %H:%M:%S'))
    print("=" * 60 + "\n")
    return summary


if __name__ == '__main__':
    from db_client import db_client

    if not db_client.enabled:
        sys.exit("DATABASE_URL absente ou base injoignable")
    if not (os.environ.get('AIRTABLE_API_KEY') and os.environ.get('AIRTABLE_BASE_ID')):
        sys.exit("AIRTABLE_API_KEY / AIRTABLE_BASE_ID manquantes")
    print(json.dumps(run(db_client, force='--force' in sys.argv), indent=2, ensure_ascii=False))
