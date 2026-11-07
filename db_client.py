"""
Couche de persistance PostgreSQL pour Botanus.

Expose la MÊME interface que airtable_client.py (get_all_*, create_*, upsert_*,
update_*, delete_*) afin que main.py et tous les endpoints /api/... restent
inchangés. Les identifiants "airtable_id" échangés avec main.py sont simplement
l'id numérique de la ligne, converti en texte.

Activation : variable d'environnement DATABASE_URL (fournie par Railway via
${{Postgres.DATABASE_URL}}). Si elle est absente ou si la base est injoignable,
`enabled` vaut False et main.py retombe sur Airtable.
"""

import contextlib
import functools
import io
import json
import os
from datetime import datetime
from typing import Dict, List, Optional

import psycopg2
import psycopg2.extras
from psycopg2.pool import ThreadedConnectionPool

SCHEMA = """
CREATE TABLE IF NOT EXISTS meta (
    key        text PRIMARY KEY,
    value      text NOT NULL,
    updated_at timestamptz NOT NULL DEFAULT now()
);

-- Copie brute des tables Airtable au moment de la migration (filet de sécurité)
CREATE TABLE IF NOT EXISTS airtable_backup (
    table_name text PRIMARY KEY,
    data       jsonb NOT NULL,
    saved_at   timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS zones (
    id          integer PRIMARY KEY,
    nom         text NOT NULL,
    icon        text NOT NULL DEFAULT '🗺️',
    description text NOT NULL DEFAULT '',
    created_at  text NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS tags (
    id         integer PRIMARY KEY,
    name       text NOT NULL,
    color      text NOT NULL DEFAULT '#4CAF50',
    created_at text NOT NULL DEFAULT ''
);

-- 'fields' contient les ~50 champs botaniques à plat (même format que Airtable)
CREATE TABLE IF NOT EXISTS plants (
    id           serial PRIMARY KEY,
    nom_latin    text NOT NULL DEFAULT '',
    nom_francais text NOT NULL DEFAULT '',
    fields       jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at   timestamptz NOT NULL DEFAULT now(),
    updated_at   timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS plants_nom_latin_idx ON plants (lower(nom_latin));

CREATE TABLE IF NOT EXISTS tasks (
    id           integer PRIMARY KEY,
    title        text NOT NULL,
    description  text NOT NULL DEFAULT '',
    category     text NOT NULL DEFAULT 'Autre',
    status       text NOT NULL DEFAULT 'todo',
    created_at   text NOT NULL DEFAULT '',
    completed_at text,
    zone_id      integer,
    zones        jsonb NOT NULL DEFAULT '[]'::jsonb,
    subtasks     jsonb NOT NULL DEFAULT '[]'::jsonb
);
CREATE INDEX IF NOT EXISTS tasks_status_idx ON tasks (status);

CREATE TABLE IF NOT EXISTS inventory (
    id                integer PRIMARY KEY,
    nom               text NOT NULL DEFAULT '',
    categorie         text NOT NULL DEFAULT 'Outil',
    statut            text NOT NULL DEFAULT 'Possédé',
    etat              text NOT NULL DEFAULT 'Bon',
    quantite          double precision NOT NULL DEFAULT 1,
    unite             text NOT NULL DEFAULT '',
    seuil_alerte      double precision NOT NULL DEFAULT 1,
    prix_estime       double precision NOT NULL DEFAULT 0,
    date_expiration   text NOT NULL DEFAULT '',
    dernier_entretien text NOT NULL DEFAULT '',
    notes             text NOT NULL DEFAULT '',
    created_at        text NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS journal (
    id          integer PRIMARY KEY,
    date        text NOT NULL DEFAULT '',
    heure       text NOT NULL DEFAULT '',
    categorie   text NOT NULL DEFAULT 'Autre',
    emplacement text NOT NULL DEFAULT '',
    zone_id     integer,
    titre       text NOT NULL DEFAULT '',
    notes       text NOT NULL DEFAULT '',
    meteo       text NOT NULL DEFAULT '',
    created_at  text NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS journal_date_idx ON journal (date DESC);

CREATE TABLE IF NOT EXISTS reminders (
    plant_id      integer NOT NULL,
    reminder_type text NOT NULL,
    month         text NOT NULL,
    is_checked    boolean NOT NULL DEFAULT false,
    checked_date  text NOT NULL DEFAULT '',
    PRIMARY KEY (plant_id, reminder_type, month)
);

CREATE TABLE IF NOT EXISTS settings (
    user_id text PRIMARY KEY,
    data    jsonb NOT NULL DEFAULT '{}'::jsonb
);

CREATE TABLE IF NOT EXISTS heures_recup (
    id     serial PRIMARY KEY,
    date   text NOT NULL DEFAULT '',
    type   text NOT NULL DEFAULT 'Supp',
    duree  double precision NOT NULL DEFAULT 0,
    note   text NOT NULL DEFAULT '',
    statut text NOT NULL DEFAULT 'À récupérer'
);
"""

DEFAULT_SETTINGS = {
    'meteo_ville': 'Malaucène',
    'meteo_latitude': 44.1736,
    'meteo_longitude': 5.1314,
    'meteo_mode': 'ville',
}

# Tables pouvant recevoir un import en masse (nom -> colonnes autorisées)
IMPORT_COLUMNS = {
    'zones': ['id', 'nom', 'icon', 'description', 'created_at'],
    'tags': ['id', 'name', 'color', 'created_at'],
    'plants': ['id', 'nom_latin', 'nom_francais', 'fields'],
    'tasks': ['id', 'title', 'description', 'category', 'status', 'created_at',
              'completed_at', 'zone_id', 'zones', 'subtasks'],
    'inventory': ['id', 'nom', 'categorie', 'statut', 'etat', 'quantite', 'unite',
                  'seuil_alerte', 'prix_estime', 'date_expiration',
                  'dernier_entretien', 'notes', 'created_at'],
    'journal': ['id', 'date', 'heure', 'categorie', 'emplacement', 'zone_id',
                'titre', 'notes', 'meteo', 'created_at'],
    'reminders': ['plant_id', 'reminder_type', 'month', 'is_checked', 'checked_date'],
    'heures_recup': ['id', 'date', 'type', 'duree', 'note', 'statut'],
}
JSON_COLUMNS = {'fields', 'zones', 'subtasks'}


def _safe(default):
    """Décorateur pour les écritures : log l'erreur et renvoie une valeur neutre
    (même comportement que airtable_client, qui renvoie None/False en cas d'échec)."""
    def deco(fn):
        @functools.wraps(fn)
        def wrapper(self, *args, **kwargs):
            if not self.enabled:
                return default
            try:
                return fn(self, *args, **kwargs)
            except Exception as e:
                print(f"❌ Erreur PostgreSQL ({fn.__name__}): {e}")
                return default
        return wrapper
    return deco


def _num(value):
    """5.0 -> 5 pour que le JSON reste identique à celui d'Airtable."""
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return value


def _to_int(value) -> Optional[int]:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _int_list(values) -> List[int]:
    out = []
    for v in values or []:
        i = _to_int(v)
        if i is not None:
            out.append(i)
    return out


def _today() -> str:
    return datetime.now().strftime('%Y-%m-%d')


class PostgresClient:
    """Client PostgreSQL avec l'interface d'AirtableClient."""

    def __init__(self):
        self.dsn = os.environ.get('DATABASE_URL', '')
        self.enabled = False
        self.pool = None
        self._transformer = None

        if not self.dsn:
            print("ℹ️ PostgreSQL désactivé (DATABASE_URL absente)")
            return
        try:
            self.pool = ThreadedConnectionPool(
                1, int(os.environ.get('DB_POOL_MAX', '8')), self.dsn, connect_timeout=8
            )
            self._query(SCHEMA)
            self.enabled = True
            print("✅ PostgreSQL activé")
        except Exception as e:
            print(f"❌ PostgreSQL injoignable, retour sur Airtable: {e}")
            self.pool = None

    # ------------------------------------------------------------------
    # Accès bas niveau
    # ------------------------------------------------------------------

    def _query(self, sql, params=None, fetch=None):
        """Exécute une requête. fetch: 'all' | 'one' | None (renvoie rowcount).
        Une connexion morte (base redémarrée, inactivité) est remplacée et la
        requête rejouée une fois."""
        last_error = None
        for _attempt in (1, 2):
            conn = self.pool.getconn()
            broken = False
            try:
                with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                    cur.execute(sql, params)
                    if fetch == 'all':
                        result = cur.fetchall()
                    elif fetch == 'one':
                        result = cur.fetchone()
                    else:
                        result = cur.rowcount
                conn.commit()
                return result
            except (psycopg2.OperationalError, psycopg2.InterfaceError) as e:
                broken = True
                last_error = e
                with contextlib.suppress(Exception):
                    conn.rollback()
            except Exception:
                with contextlib.suppress(Exception):
                    conn.rollback()
                raise
            finally:
                self.pool.putconn(conn, close=broken)
        raise last_error

    def test_connection(self) -> bool:
        if not self.enabled:
            print("❌ PostgreSQL désactivé")
            return False
        try:
            self._query("SELECT 1", fetch='one')
            print("✅ Connexion PostgreSQL OK")
            return True
        except Exception as e:
            print(f"❌ Connexion PostgreSQL échouée: {e}")
            return False

    # ------------------------------------------------------------------
    # Meta / import en masse (utilisés par la migration)
    # ------------------------------------------------------------------

    def get_meta(self, key: str) -> Optional[str]:
        row = self._query("SELECT value FROM meta WHERE key = %s", (key,), fetch='one')
        return row['value'] if row else None

    def set_meta(self, key: str, value: str) -> None:
        self._query(
            "INSERT INTO meta (key, value) VALUES (%s, %s) "
            "ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value, updated_at = now()",
            (key, value),
        )

    def is_empty(self) -> bool:
        """True si aucune donnée utilisateur n'existe encore."""
        for table in ('plants', 'tasks', 'zones', 'tags', 'inventory', 'journal', 'heures_recup'):
            row = self._query(f"SELECT 1 AS x FROM {table} LIMIT 1", fetch='one')
            if row:
                return False
        return True

    def save_backup(self, table_name: str, records: list) -> None:
        self._query(
            "INSERT INTO airtable_backup (table_name, data) VALUES (%s, %s) "
            "ON CONFLICT (table_name) DO UPDATE SET data = EXCLUDED.data, saved_at = now()",
            (table_name, psycopg2.extras.Json(records)),
        )

    def import_rows(self, table: str, rows: List[Dict]) -> int:
        """Insère des lignes telles quelles (ids explicites). Les doublons sont ignorés."""
        if table not in IMPORT_COLUMNS:
            raise ValueError(f"Table inconnue: {table}")
        if not rows:
            return 0
        columns = IMPORT_COLUMNS[table]
        placeholders = ", ".join(["%s"] * len(columns))
        sql = (f"INSERT INTO {table} ({', '.join(columns)}) VALUES ({placeholders}) "
               f"ON CONFLICT DO NOTHING")
        inserted = 0
        for row in rows:
            values = []
            for col in columns:
                v = row.get(col)
                if col in JSON_COLUMNS:
                    v = psycopg2.extras.Json(v if v is not None else ([] if col != 'fields' else {}))
                values.append(v)
            inserted += self._query(sql, values) or 0
        # Remettre les séquences après les ids importés
        for seq_table in ('plants', 'heures_recup'):
            if table == seq_table:
                self._query(
                    f"SELECT setval(pg_get_serial_sequence('{seq_table}', 'id'), "
                    f"GREATEST((SELECT COALESCE(MAX(id), 0) FROM {seq_table}), 1))",
                    fetch='one',
                )
        return inserted

    def import_settings(self, data: Dict) -> None:
        self._query(
            "INSERT INTO settings (user_id, data) VALUES ('default', %s) "
            "ON CONFLICT (user_id) DO NOTHING",
            (psycopg2.extras.Json(data),),
        )

    # ------------------------------------------------------------------
    # PLANTES
    # ------------------------------------------------------------------

    def _plant_fields(self, plant_data: Dict) -> Dict:
        """Convertit le dict de main.py (avec 'details') en champs plats, en
        réutilisant le mapping éprouvé d'AirtableClient.transform_plant_data."""
        fields: Dict = {}
        try:
            if self._transformer is None:
                from airtable_client import AirtableClient
                with contextlib.redirect_stdout(io.StringIO()):
                    self._transformer = AirtableClient()
            with contextlib.redirect_stdout(io.StringIO()):
                fields = self._transformer.transform_plant_data(plant_data)
        except Exception as e:
            print(f"⚠️ transform_plant_data indisponible ({e}), mapping minimal")
            for key in ('nom_francais', 'nom_latin', 'type_plante', 'exposition', 'prix'):
                if plant_data.get(key):
                    fields[key] = plant_data[key]
            if plant_data.get('url'):
                fields['url_source'] = plant_data['url']

        # Les zones sont stockées sous forme de texte "10,7" (comme la formule
        # zone_ids d'Airtable). Une liste vide efface bien les zones.
        fields.pop('zones', None)
        if 'zones' in plant_data:
            fields['zone_ids'] = ",".join(str(z) for z in _int_list(plant_data['zones']))
        return fields

    @_safe(None)
    def find_plant_by_latin_name(self, nom_latin: str) -> Optional[str]:
        row = self._query(
            "SELECT id FROM plants WHERE lower(nom_latin) = lower(%s) ORDER BY id LIMIT 1",
            (nom_latin,), fetch='one',
        )
        return str(row['id']) if row else None

    @_safe(None)
    def create_plant(self, plant_data: Dict, plant_id: Optional[int] = None) -> Optional[str]:
        """Crée une plante. Si plant_id est fourni (numéro utilisé par l'app en mémoire),
        il devient l'id de la ligne : ainsi les ids restent identiques après un redémarrage."""
        fields = self._plant_fields(plant_data)
        values = (plant_data.get('nom_latin', '') or '', plant_data.get('nom_francais', '') or '',
                  psycopg2.extras.Json(fields))
        row = None
        if plant_id is not None:
            row = self._query(
                "INSERT INTO plants (id, nom_latin, nom_francais, fields) VALUES (%s, %s, %s, %s) "
                "ON CONFLICT (id) DO NOTHING RETURNING id",
                (int(plant_id),) + values, fetch='one',
            )
            if row:
                self._query(
                    "SELECT setval(pg_get_serial_sequence('plants', 'id'), "
                    "GREATEST((SELECT MAX(id) FROM plants), 1))", fetch='one',
                )
        if not row:  # pas d'id imposé, ou id déjà pris : laisser la séquence choisir
            row = self._query(
                "INSERT INTO plants (nom_latin, nom_francais, fields) VALUES (%s, %s, %s) RETURNING id",
                values, fetch='one',
            )
        print(f"✅ Plante créée: {plant_data.get('nom_francais')} (id {row['id']})")
        return str(row['id'])

    @_safe(False)
    def update_plant(self, record_id: str, plant_data: Dict) -> bool:
        fields = self._plant_fields(plant_data)
        count = self._query(
            "UPDATE plants SET fields = fields || %s::jsonb, "
            "nom_latin = COALESCE(NULLIF(%s, ''), nom_latin), "
            "nom_francais = COALESCE(NULLIF(%s, ''), nom_francais), "
            "updated_at = now() WHERE id = %s",
            (json.dumps(fields), plant_data.get('nom_latin', '') or '',
             plant_data.get('nom_francais', '') or '', _to_int(record_id)),
        )
        return count > 0

    @_safe(None)
    def upsert_plant(self, plant_data: Dict, plant_id: Optional[int] = None) -> Optional[str]:
        nom_latin = (plant_data.get('nom_latin') or '').strip()
        if not nom_latin:
            return self.create_plant(plant_data, plant_id)
        record_id = self.find_plant_by_latin_name(nom_latin)
        if record_id:
            self.update_plant(record_id, plant_data)
            return record_id
        return self.create_plant(plant_data, plant_id)

    @_safe(None)
    def get_plant(self, record_id: str) -> Optional[Dict]:
        row = self._query("SELECT fields FROM plants WHERE id = %s", (_to_int(record_id),), fetch='one')
        return row['fields'] if row else None

    @_safe(False)
    def delete_plant(self, record_id: str) -> bool:
        return self._query("DELETE FROM plants WHERE id = %s", (_to_int(record_id),)) > 0

    @_safe(False)
    def delete_plant_by_latin_name(self, nom_latin: str) -> bool:
        return self._query(
            "DELETE FROM plants WHERE lower(nom_latin) = lower(%s)", (nom_latin,)
        ) > 0

    def get_all_plants(self, view: Optional[str] = None) -> List[Dict]:
        if not self.enabled:
            return []
        rows = self._query(
            "SELECT id, nom_latin, nom_francais, fields FROM plants ORDER BY id", fetch='all'
        )
        plants = []
        for row in rows:
            fields = dict(row['fields'] or {})
            fields['nom_latin'] = row['nom_latin']
            fields['nom_francais'] = row['nom_francais']
            fields['airtable_record_id'] = str(row['id'])
            fields['db_id'] = row['id']  # main.py s'en sert comme plant_id stable
            plants.append(fields)
        print(f"✅ {len(plants)} plantes chargées depuis PostgreSQL")
        return plants

    def sync_formats(self, nom_latin: str, formats: List[Dict]) -> bool:
        # Les formats de vente ne sont plus stockés (non utilisés par l'API actuelle)
        return False

    @_safe(False)
    def update_plant_tags(self, record_id: str, tags: List[int]) -> bool:
        return self._query(
            "UPDATE plants SET fields = fields || jsonb_build_object('tags', %s::text), "
            "updated_at = now() WHERE id = %s",
            (json.dumps(tags), _to_int(record_id)),
        ) > 0

    @_safe(False)
    def update_plant_notes_quantity(self, record_id: str, notes: str, quantity: int) -> bool:
        return self._query(
            "UPDATE plants SET fields = fields || jsonb_build_object('notes', %s::text, 'quantity', %s::int), "
            "updated_at = now() WHERE id = %s",
            (notes or '', int(quantity or 0), _to_int(record_id)),
        ) > 0

    # ------------------------------------------------------------------
    # TAGS
    # ------------------------------------------------------------------

    def get_all_tags(self) -> List[Dict]:
        if not self.enabled:
            return []
        rows = self._query("SELECT * FROM tags ORDER BY id", fetch='all')
        return [{'id': r['id'], 'name': r['name'], 'color': r['color'],
                 'created_at': r['created_at'], 'airtable_id': str(r['id'])} for r in rows]

    @_safe(None)
    def create_tag(self, tag_data: Dict) -> Optional[str]:
        tag_id = int(tag_data['tag_id'])
        self._query(
            "INSERT INTO tags (id, name, color, created_at) VALUES (%s, %s, %s, %s) "
            "ON CONFLICT (id) DO UPDATE SET name = EXCLUDED.name, color = EXCLUDED.color",
            (tag_id, tag_data['name'], tag_data.get('color', '#4CAF50'),
             tag_data.get('created_at', _today())),
        )
        return str(tag_id)

    @_safe(False)
    def delete_tag(self, tag_id: int) -> bool:
        return self._query("DELETE FROM tags WHERE id = %s", (int(tag_id),)) > 0

    # ------------------------------------------------------------------
    # TÂCHES
    # ------------------------------------------------------------------

    def get_all_tasks(self) -> List[Dict]:
        if not self.enabled:
            return []
        rows = self._query("SELECT * FROM tasks ORDER BY id", fetch='all')
        return [{
            'id': r['id'], 'title': r['title'], 'description': r['description'],
            'category': r['category'], 'status': r['status'],
            'created_at': r['created_at'], 'completed_at': r['completed_at'] or '',
            'subtasks': json.dumps(r['subtasks'] or []),
            'zone_id': r['zone_id'], 'zones': r['zones'] or [], 'airtable_id': str(r['id']),
        } for r in rows]

    @_safe(None)
    def create_task(self, task_data: Dict) -> Optional[str]:
        task_id = int(task_data['task_id'])
        zones = _int_list(task_data.get('zones'))
        zone_id = _to_int(task_data.get('zone_id')) or (zones[0] if zones else None)
        row = self._query(
            "INSERT INTO tasks (id, title, description, category, status, created_at, "
            "completed_at, zone_id, zones, subtasks) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s) "
            "ON CONFLICT (id) DO NOTHING RETURNING id",
            (task_id, task_data['title'], task_data.get('description', ''),
             task_data.get('category', 'Autre'), task_data.get('status', 'todo'),
             task_data.get('created_at', _today()), task_data.get('completed_at') or None,
             zone_id, psycopg2.extras.Json(zones),
             psycopg2.extras.Json(task_data.get('subtasks') or [])),
            fetch='one',
        )
        if not row:
            print(f"❌ Tâche {task_id} existe déjà en base, création ignorée")
            return None
        return str(task_id)

    @_safe(False)
    def update_task(self, record_id: str, task_data: Dict) -> bool:
        sets, params = [], []
        for key in ('title', 'description', 'category', 'status'):
            if key in task_data:
                sets.append(f"{key} = %s")
                params.append(task_data[key])
        if 'completed_at' in task_data:
            sets.append("completed_at = %s")
            params.append(task_data['completed_at'] or None)
        if 'subtasks' in task_data:
            sets.append("subtasks = %s")
            params.append(psycopg2.extras.Json(task_data['subtasks'] or []))
        if 'zones' in task_data:
            zones = _int_list(task_data['zones'])
            sets.append("zones = %s")
            params.append(psycopg2.extras.Json(zones))
            if 'zone_id' not in task_data:
                sets.append("zone_id = %s")
                params.append(zones[0] if zones else None)
        if 'zone_id' in task_data:
            sets.append("zone_id = %s")
            params.append(_to_int(task_data['zone_id']))
        if not sets:
            return True
        params.append(_to_int(record_id))
        return self._query(f"UPDATE tasks SET {', '.join(sets)} WHERE id = %s", params) > 0

    @_safe(False)
    def delete_task(self, task_id: int) -> bool:
        return self._query("DELETE FROM tasks WHERE id = %s", (int(task_id),)) > 0

    # ------------------------------------------------------------------
    # INVENTAIRE
    # ------------------------------------------------------------------

    def get_all_inventory_items(self) -> List[Dict]:
        if not self.enabled:
            return []
        rows = self._query("SELECT * FROM inventory ORDER BY id", fetch='all')
        items = []
        for r in rows:
            items.append({
                'id': r['id'], 'nom': r['nom'], 'categorie': r['categorie'],
                'statut': r['statut'], 'etat': r['etat'],
                'quantite': _num(r['quantite']), 'unite': r['unite'],
                'seuil_alerte': _num(r['seuil_alerte']), 'prix_estime': _num(r['prix_estime']),
                'date_expiration': r['date_expiration'],
                'dernier_entretien': r['dernier_entretien'], 'notes': r['notes'],
                'airtable_id': str(r['id']), 'created_at': r['created_at'],
            })
        return items

    @_safe(None)
    def upsert_inventory_item(self, item_id: int, item_data: Dict) -> Optional[str]:
        self._query(
            "INSERT INTO inventory (id, nom, categorie, statut, etat, quantite, unite, "
            "seuil_alerte, prix_estime, date_expiration, dernier_entretien, notes, created_at) "
            "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) "
            "ON CONFLICT (id) DO UPDATE SET nom=EXCLUDED.nom, categorie=EXCLUDED.categorie, "
            "statut=EXCLUDED.statut, etat=EXCLUDED.etat, quantite=EXCLUDED.quantite, "
            "unite=EXCLUDED.unite, seuil_alerte=EXCLUDED.seuil_alerte, "
            "prix_estime=EXCLUDED.prix_estime, date_expiration=EXCLUDED.date_expiration, "
            "dernier_entretien=EXCLUDED.dernier_entretien, notes=EXCLUDED.notes",
            (int(item_id), item_data.get('nom', ''), item_data.get('categorie', 'Outil'),
             item_data.get('statut', 'Possédé'), item_data.get('etat', 'Bon'),
             item_data.get('quantite', 1), item_data.get('unite', ''),
             item_data.get('seuil_alerte', 1), item_data.get('prix_estime', 0),
             item_data.get('date_expiration', '') or '',
             item_data.get('dernier_entretien', '') or '',
             item_data.get('notes', '') or '',
             item_data.get('created_at') or _today()),
        )
        return str(item_id)

    @_safe(False)
    def delete_inventory_item(self, item_id: int) -> bool:
        return self._query("DELETE FROM inventory WHERE id = %s", (int(item_id),)) > 0

    # ------------------------------------------------------------------
    # JOURNAL
    # ------------------------------------------------------------------

    def get_all_journal_entries(self) -> List[Dict]:
        if not self.enabled:
            return []
        rows = self._query("SELECT * FROM journal ORDER BY id", fetch='all')
        return [{
            'id': r['id'], 'date': r['date'], 'heure': r['heure'],
            'categorie': r['categorie'], 'emplacement': r['emplacement'],
            'zone_id': r['zone_id'], 'titre': r['titre'], 'notes': r['notes'],
            'meteo': r['meteo'], 'airtable_id': str(r['id']), 'created_at': r['created_at'],
        } for r in rows]

    @_safe(None)
    def upsert_journal_entry(self, entry_id: int, entry_data: Dict) -> Optional[str]:
        self._query(
            "INSERT INTO journal (id, date, heure, categorie, emplacement, zone_id, titre, "
            "notes, meteo, created_at) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) "
            "ON CONFLICT (id) DO UPDATE SET date=EXCLUDED.date, heure=EXCLUDED.heure, "
            "categorie=EXCLUDED.categorie, emplacement=EXCLUDED.emplacement, "
            "zone_id=EXCLUDED.zone_id, titre=EXCLUDED.titre, notes=EXCLUDED.notes, "
            "meteo=EXCLUDED.meteo",
            (int(entry_id), entry_data.get('date', '') or '', entry_data.get('heure', '') or '',
             entry_data.get('categorie', 'Autre'), entry_data.get('emplacement', '') or '',
             _to_int(entry_data.get('zone_id')), entry_data.get('titre', '') or '',
             entry_data.get('notes', '') or '', entry_data.get('meteo', '') or '',
             entry_data.get('created_at') or _today()),
        )
        return str(entry_id)

    @_safe(False)
    def delete_journal_entry(self, entry_id: int) -> bool:
        return self._query("DELETE FROM journal WHERE id = %s", (int(entry_id),)) > 0

    # ------------------------------------------------------------------
    # RAPPELS
    # ------------------------------------------------------------------

    def get_all_reminders(self) -> List[Dict]:
        if not self.enabled:
            return []
        rows = self._query("SELECT * FROM reminders", fetch='all')
        return [{
            'plant_id': r['plant_id'], 'reminder_type': r['reminder_type'],
            'month': r['month'], 'is_checked': r['is_checked'],
            'checked_date': r['checked_date'],
            'airtable_id': f"{r['plant_id']}|{r['reminder_type']}|{r['month']}",
        } for r in rows]

    @_safe(False)
    def toggle_reminder(self, plant_id: int, reminder_type: str, month: str, is_checked: bool) -> bool:
        self._query(
            "INSERT INTO reminders (plant_id, reminder_type, month, is_checked, checked_date) "
            "VALUES (%s, %s, %s, %s, %s) "
            "ON CONFLICT (plant_id, reminder_type, month) DO UPDATE SET "
            "is_checked = EXCLUDED.is_checked, "
            "checked_date = CASE WHEN EXCLUDED.is_checked THEN EXCLUDED.checked_date "
            "ELSE reminders.checked_date END",
            (int(plant_id), reminder_type, month, bool(is_checked),
             _today() if is_checked else ''),
        )
        return True

    # ------------------------------------------------------------------
    # ZONES
    # ------------------------------------------------------------------

    def get_all_zones(self) -> List[Dict]:
        if not self.enabled:
            return []
        rows = self._query("SELECT * FROM zones ORDER BY id", fetch='all')
        return [{'id': r['id'], 'nom': r['nom'], 'icon': r['icon'],
                 'description': r['description'], 'created_at': r['created_at'],
                 'airtable_id': str(r['id'])} for r in rows]

    @_safe(None)
    def create_zone(self, zone_data: Dict) -> Optional[str]:
        zone_id = int(zone_data['zone_id'])
        row = self._query(
            "INSERT INTO zones (id, nom, icon, description, created_at) VALUES (%s,%s,%s,%s,%s) "
            "ON CONFLICT (id) DO NOTHING RETURNING id",
            (zone_id, zone_data['nom'], zone_data.get('icon', '🗺️'),
             zone_data.get('description', ''), zone_data.get('created_at', _today())),
            fetch='one',
        )
        if not row:
            print(f"❌ Zone {zone_id} existe déjà en base, création ignorée")
            return None
        return str(zone_id)

    @_safe(False)
    def update_zone(self, zone_id: int, zone_data: Dict) -> bool:
        sets, params = [], []
        for key in ('nom', 'icon', 'description'):
            if key in zone_data:
                sets.append(f"{key} = %s")
                params.append(zone_data[key])
        if not sets:
            return True
        params.append(int(zone_id))
        return self._query(f"UPDATE zones SET {', '.join(sets)} WHERE id = %s", params) > 0

    @_safe(False)
    def delete_zone(self, zone_id: int) -> bool:
        return self._query("DELETE FROM zones WHERE id = %s", (int(zone_id),)) > 0

    # ------------------------------------------------------------------
    # SETTINGS
    # ------------------------------------------------------------------

    def get_settings(self) -> Dict:
        if not self.enabled:
            return dict(DEFAULT_SETTINGS)
        row = self._query("SELECT data FROM settings WHERE user_id = 'default'", fetch='one')
        if not row:
            self.import_settings(DEFAULT_SETTINGS)
            return {**DEFAULT_SETTINGS, 'airtable_id': 'default'}
        return {**DEFAULT_SETTINGS, **(row['data'] or {}), 'airtable_id': 'default'}

    @_safe(False)
    def update_settings(self, settings_data: Dict) -> bool:
        allowed = {k: v for k, v in settings_data.items() if k in DEFAULT_SETTINGS}
        self._query(
            "INSERT INTO settings (user_id, data) VALUES ('default', %s) "
            "ON CONFLICT (user_id) DO UPDATE SET data = settings.data || EXCLUDED.data",
            (psycopg2.extras.Json(allowed),),
        )
        return True

    # ------------------------------------------------------------------
    # HEURES RÉCUP
    # ------------------------------------------------------------------

    def get_all_heures_recup(self) -> List[Dict]:
        if not self.enabled:
            return []
        rows = self._query("SELECT * FROM heures_recup ORDER BY id", fetch='all')
        return [{'id': str(r['id']), 'airtable_id': str(r['id']), 'date': r['date'],
                 'type': r['type'], 'duree': _num(r['duree']), 'note': r['note'],
                 'statut': r['statut']} for r in rows]

    @_safe(None)
    def create_heure_recup(self, heure_data: Dict) -> Optional[Dict]:
        date_str = heure_data.get('Date', '') or ''
        if 'T' in date_str:
            date_str = date_str.split('T')[0]
        row = self._query(
            "INSERT INTO heures_recup (date, type, duree, note, statut) "
            "VALUES (%s,%s,%s,%s,%s) RETURNING id",
            (date_str, heure_data.get('Type', 'Supp'), heure_data.get('Duree', 0),
             heure_data.get('Note', ''), heure_data.get('Statut', 'À récupérer')),
            fetch='one',
        )
        return {'id': str(row['id'])}


# Instance globale (même schéma que airtable_client.py)
db_client = PostgresClient()
