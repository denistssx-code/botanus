from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Optional, List
import os
import httpx

app = FastAPI(title="Clos & Co API")

# ── Airtable config ──────────────────────────────────────
AIRTABLE_TOKEN = os.environ.get("AIRTABLE_TOKEN")
AIRTABLE_BASE  = os.environ.get("AIRTABLE_BASE_ID")

TABLES = {
    "evenements":   "Evenements",
    "prestataires": "Prestataires",
    "idees":        "Idees",
    "rappels":      "Rappels",
    "achats":       "Achats",
}

def airtable_headers():
    return {
        "Authorization": f"Bearer {AIRTABLE_TOKEN}",
        "Content-Type": "application/json",
    }

def airtable_url(table: str, record_id: str = "") -> str:
    base = f"https://api.airtable.com/v0/{AIRTABLE_BASE}/{TABLES[table]}"
    return f"{base}/{record_id}" if record_id else base


# ── Modèles Pydantic ─────────────────────────────────────

class Evenement(BaseModel):
    nom: str
    type: str                    # famille, oeno, musique, gastronomie, etc.
    date: str                    # YYYY-MM-DD
    creneau: str                 # Week-end, Semaine, Jour férié, Soirée…
    prix_personne: float
    nb_participants: int
    lieu: str
    description: Optional[str] = ""
    statut: Optional[str] = "à venir"   # à venir, en cours, passé
    meteo: Optional[str] = ""
    couleur: Optional[str] = "#6E9B88"

class Prestataire(BaseModel):
    evenement_id: str            # ID Airtable de l'événement lié
    type_icon: str               # 🧑‍🌾 🎵 🚚 🌸 🍽️ etc.
    nom: str
    cout: float = 0
    note: Optional[str] = ""
    statut: Optional[str] = "à confirmer"

class Idee(BaseModel):
    titre:     Optional[str]  = None
    categorie: Optional[str]  = None
    statut:    Optional[str]  = "à faire"
    possible:  Optional[bool] = True
    notes:     Optional[str]  = ""

class Rappel(BaseModel):
    titre: str
    categorie: str               # événement, achat, client, partenaire, décoration
    echeance: str                # YYYY-MM-DD
    priorite: str = "moyenne"    # haute, moyenne, basse
    fait: bool = False
    evenement_ref: Optional[str] = ""

class Achat(BaseModel):
    libelle: str
    categorie: str               # Décoration, Restauration, Technique, Mobilier…
    montant: float
    evenement_ref: Optional[str] = ""
    statut: str = "à venir"      # passé, en cours, à venir
    date: Optional[str] = ""


# ── Helpers Airtable ─────────────────────────────────────

async def airtable_list(table: str, params: dict = {}):
    async with httpx.AsyncClient() as client:
        r = await client.get(
            airtable_url(table),
            headers=airtable_headers(),
            params=params,
            timeout=10
        )
        r.raise_for_status()
        data = r.json()
        return [{"id": rec["id"], **rec["fields"]} for rec in data.get("records", [])]

async def airtable_create(table: str, fields: dict):
    async with httpx.AsyncClient() as client:
        r = await client.post(
            airtable_url(table),
            headers=airtable_headers(),
            json={"fields": fields},
            timeout=10
        )
        if not r.ok:
            detail = r.text
            try:
                detail = r.json()
            except Exception:
                pass
            raise HTTPException(status_code=r.status_code, detail=detail)
        try:
            rec = r.json()
            return {"id": rec["id"], **rec.get("fields", {})}
        except Exception as e:
            # L'enregistrement est créé dans Airtable, on retourne juste l'id
            print(f"[Airtable] Response parse error (record was created): {e}")
            return {"id": "created", "success": True}

async def airtable_update(table: str, record_id: str, fields: dict):
    async with httpx.AsyncClient() as client:
        r = await client.patch(
            airtable_url(table, record_id),
            headers=airtable_headers(),
            json={"fields": fields},
            timeout=10
        )
        if not r.ok:
            detail = r.text
            try: detail = r.json()
            except Exception: pass
            raise HTTPException(status_code=r.status_code, detail=detail)
        try:
            rec = r.json()
            return {"id": rec["id"], **rec.get("fields", {})}
        except Exception as e:
            print(f"[Airtable] Update response parse error: {e}")
            return {"id": record_id, "success": True}


# ── Endpoint de diagnostic ────────────────────────────────
@app.get("/api/debug")
async def debug():
    """Vérifie la connexion Airtable et liste les champs existants."""
    results = {}
    for key, table_name in TABLES.items():
        try:
            async with httpx.AsyncClient() as client:
                # On récupère juste 1 enregistrement pour voir les champs
                r = await client.get(
                    f"https://api.airtable.com/v0/{AIRTABLE_BASE}/{table_name}",
                    headers=airtable_headers(),
                    params={"maxRecords": 1},
                    timeout=10
                )
                if r.ok:
                    data = r.json()
                    records = data.get("records", [])
                    fields = list(records[0]["fields"].keys()) if records else []
                    results[key] = {"status": "ok", "table": table_name, "sample_fields": fields}
                else:
                    results[key] = {"status": "error", "code": r.status_code, "detail": r.text}
        except Exception as e:
            results[key] = {"status": "exception", "detail": str(e)}
    return {
        "airtable_base": AIRTABLE_BASE,
        "token_set": bool(AIRTABLE_TOKEN),
        "tables": results
    }

@app.get("/api/debug/fields")
async def debug_fields():
    """Liste les vrais noms de champs de chaque table Airtable."""
    result = {}
    async with httpx.AsyncClient() as client:
        for key, table_name in TABLES.items():
            try:
                # API metadata Airtable
                r = await client.get(
                    f"https://api.airtable.com/v0/meta/bases/{AIRTABLE_BASE}/tables",
                    headers=airtable_headers(),
                    timeout=10
                )
                if r.ok:
                    tables = r.json().get("tables", [])
                    for t in tables:
                        if t["name"] == table_name:
                            result[key] = {
                                "table_name": table_name,
                                "fields": [
                                    {"name": f["name"], "type": f["type"]}
                                    for f in t.get("fields", [])
                                ]
                            }
                    if key not in result:
                        result[key] = {"error": f"Table '{table_name}' non trouvée"}
                else:
                    # Fallback : lire un enregistrement
                    r2 = await client.get(
                        f"https://api.airtable.com/v0/{AIRTABLE_BASE}/{table_name}",
                        headers=airtable_headers(),
                        params={"maxRecords": 1},
                        timeout=10
                    )
                    if r2.ok:
                        records = r2.json().get("records", [])
                        fields = list(records[0]["fields"].keys()) if records else ["(aucun enregistrement)"]
                        result[key] = {"table_name": table_name, "fields_from_record": fields}
                    else:
                        result[key] = {"error": r2.status_code, "detail": r2.text}
            except Exception as e:
                result[key] = {"exception": str(e)}
    return result
    async with httpx.AsyncClient() as client:
        r = await client.delete(
            airtable_url(table, record_id),
            headers=airtable_headers(),
            timeout=10
        )
        r.raise_for_status()
        return {"deleted": True, "id": record_id}


# ══════════════════════════════════════════════════════════
#  ROUTES — ÉVÉNEMENTS
# ══════════════════════════════════════════════════════════

@app.get("/api/evenements")
async def get_evenements(statut: Optional[str] = None, type: Optional[str] = None):
    params = {}
    filters = []
    if statut:
        filters.append(f"{{statut}}='{statut}'")
    if type:
        filters.append(f"{{type}}='{type}'")
    if filters:
        params["filterByFormula"] = f"AND({','.join(filters)})" if len(filters) > 1 else filters[0]
    params["sort[0][field]"] = "date"
    params["sort[0][direction]"] = "asc"
    return await airtable_list("evenements", params)

@app.get("/api/evenements/{record_id}")
async def get_evenement(record_id: str):
    async with httpx.AsyncClient() as client:
        r = await client.get(
            airtable_url("evenements", record_id),
            headers=airtable_headers(),
            timeout=10
        )
        r.raise_for_status()
        rec = r.json()
        return {"id": rec["id"], **rec["fields"]}

@app.post("/api/evenements")
async def create_evenement(ev: Evenement):
    # Champs obligatoires — toujours envoyés
    fields: dict = {
        "nom":             ev.nom,
        "type":            ev.type,
        "date":            ev.date,
        "prix_personne":   ev.prix_personne,
        "nb_participants": ev.nb_participants,
    }
    # Champs optionnels — uniquement si non vides
    if ev.creneau:     fields["creneau"]     = ev.creneau
    if ev.lieu:        fields["lieu"]        = ev.lieu
    if ev.description: fields["description"] = ev.description
    if ev.couleur:     fields["couleur"]     = ev.couleur
    if ev.meteo:       fields["meteo"]       = ev.meteo
    # statut = Single Select → on l'envoie seulement si la valeur est non vide
    # Assurez-vous que les options "à venir","en cours","passé" existent dans Airtable
    # OU changez le type de ce champ en "Texte" dans Airtable
    if ev.statut:      fields["statut"]      = ev.statut

    print(f"[Airtable POST] Evenements → champs: {list(fields.keys())}")
    try:
        return await airtable_create("evenements", fields)
    except HTTPException as e:
        print(f"[Airtable ERR] {e.detail}")
        raise HTTPException(
            status_code=422,
            detail={
                "message": "Erreur Airtable 422 — champ refusé",
                "champs_envoyes": list(fields.keys()),
                "detail_airtable": e.detail,
                "conseil": "Vérifiez que le champ 'statut' est en type Texte OU que les options à venir/en cours/passé existent"
            }
        )

@app.patch("/api/evenements/{record_id}")
async def update_evenement(record_id: str, data: dict):
    allowed = {"nom","type","date","creneau","prix_personne","nb_participants","lieu","description","statut","meteo","couleur"}
    fields = {k: v for k, v in data.items() if k in allowed and v is not None}
    return await airtable_update("evenements", record_id, fields)

@app.delete("/api/evenements/{record_id}")
async def delete_evenement(record_id: str):
    return await airtable_delete("evenements", record_id)


# ══════════════════════════════════════════════════════════
#  ROUTES — PRESTATAIRES
# ══════════════════════════════════════════════════════════

@app.get("/api/prestataires")
async def get_prestataires(evenement_id: Optional[str] = None):
    params = {}
    if evenement_id:
        params["filterByFormula"] = f"{{evenement_id}}='{evenement_id}'"
    return await airtable_list("prestataires", params)

@app.post("/api/prestataires")
async def create_prestataire(p: Prestataire):
    return await airtable_create("prestataires", p.dict())

@app.patch("/api/prestataires/{record_id}")
async def update_prestataire(record_id: str, data: dict):
    allowed = {"evenement_id","type_icon","nom","cout","note","statut"}
    fields = {k: v for k, v in data.items() if k in allowed and v is not None}
    return await airtable_update("prestataires", record_id, fields)

@app.delete("/api/prestataires/{record_id}")
async def delete_prestataire(record_id: str):
    return await airtable_delete("prestataires", record_id)


# ══════════════════════════════════════════════════════════
#  ROUTES — IDÉES
# ══════════════════════════════════════════════════════════

@app.get("/api/idees")
async def get_idees(statut: Optional[str] = None):
    params = {}
    if statut:
        params["filterByFormula"] = f"{{statut}}='{statut}'"
    return await airtable_list("idees", params)

@app.post("/api/idees")
async def create_idee(i: Idee):
    fields: dict = {"titre": i.titre, "categorie": i.categorie}
    if i.statut:  fields["statut"]   = i.statut
    if i.notes:   fields["notes"]    = i.notes
    # possible est un checkbox Airtable — envoyer explicitement True/False
    fields["possible"] = bool(i.possible)
    print(f"[Airtable POST] Idees → {list(fields.keys())}")
    return await airtable_create("idees", fields)

@app.patch("/api/idees/{record_id}")
async def update_idee(record_id: str, data: dict):
    """PATCH partiel — accepte n'importe quel sous-ensemble de champs."""
    allowed = {"titre", "categorie", "statut", "possible", "notes"}
    fields = {k: v for k, v in data.items() if k in allowed}
    if not fields:
        raise HTTPException(status_code=400, detail="Aucun champ valide fourni")
    # Forcer le type bool pour possible
    if "possible" in fields:
        fields["possible"] = bool(fields["possible"])
    print(f"[Airtable PATCH] Idees/{record_id} → {fields}")
    return await airtable_update("idees", record_id, fields)

@app.delete("/api/idees/{record_id}")
async def delete_idee(record_id: str):
    return await airtable_delete("idees", record_id)


# ══════════════════════════════════════════════════════════
#  ROUTES — RAPPELS
# ══════════════════════════════════════════════════════════

@app.get("/api/rappels")
async def get_rappels(fait: Optional[bool] = None, categorie: Optional[str] = None):
    params = {}
    filters = []
    if fait is not None:
        filters.append(f"{{fait}}={'TRUE' if fait else 'FALSE'}")
    if categorie:
        filters.append(f"{{categorie}}='{categorie}'")
    if filters:
        params["filterByFormula"] = f"AND({','.join(filters)})" if len(filters) > 1 else filters[0]
    params["sort[0][field]"] = "echeance"
    params["sort[0][direction]"] = "asc"
    return await airtable_list("rappels", params)

@app.post("/api/rappels")
async def create_rappel(r: Rappel):
    return await airtable_create("rappels", r.dict())

@app.patch("/api/rappels/{record_id}")
async def update_rappel(record_id: str, data: dict):
    allowed = {"titre","categorie","echeance","priorite","fait","evenement_ref"}
    fields = {k: v for k, v in data.items() if k in allowed}
    if "fait" in fields:
        fields["fait"] = bool(fields["fait"])
    return await airtable_update("rappels", record_id, fields)

@app.delete("/api/rappels/{record_id}")
async def delete_rappel(record_id: str):
    return await airtable_delete("rappels", record_id)


# ══════════════════════════════════════════════════════════
#  ROUTES — ACHATS
# ══════════════════════════════════════════════════════════

@app.get("/api/achats")
async def get_achats(statut: Optional[str] = None):
    params = {}
    if statut:
        params["filterByFormula"] = f"{{statut}}='{statut}'"
    params["sort[0][field]"] = "date"
    params["sort[0][direction]"] = "desc"
    return await airtable_list("achats", params)

@app.post("/api/achats")
async def create_achat(a: Achat):
    return await airtable_create("achats", a.dict())

@app.patch("/api/achats/{record_id}")
async def update_achat(record_id: str, data: dict):
    allowed = {"libelle","categorie","montant","evenement_ref","statut","date"}
    fields = {k: v for k, v in data.items() if k in allowed and v is not None}
    return await airtable_update("achats", record_id, fields)

@app.delete("/api/achats/{record_id}")
async def delete_achat(record_id: str):
    return await airtable_delete("achats", record_id)


# ══════════════════════════════════════════════════════════
#  ROUTE — STATS ROI (pour le bloc rentabilité accueil)
# ══════════════════════════════════════════════════════════

@app.get("/api/stats/roi")
async def get_roi():
    """Calcule les chiffres de rentabilité du poste."""
    evenements = await airtable_list("evenements")
    achats = await airtable_list("achats")

    salaire_mensuel = float(os.environ.get("SALAIRE_MENSUEL", 1800))
    salaire_annuel  = salaire_mensuel * 12

    revenus_total = sum(
        float(e.get("prix_personne", 0)) * int(e.get("nb_participants", 0))
        for e in evenements
    )
    depenses_total = sum(float(a.get("montant", 0)) for a in achats)
    valeur_nette   = revenus_total - salaire_annuel
    roi_pct        = round(((revenus_total - salaire_annuel) / salaire_annuel) * 100) if salaire_annuel else 0
    multiplicateur = round(revenus_total / salaire_annuel, 1) if salaire_annuel else 0
    mois_rentabilite = round(salaire_annuel / (revenus_total / 12), 1) if revenus_total else None

    return {
        "salaire_mensuel":   salaire_mensuel,
        "salaire_annuel":    salaire_annuel,
        "revenus_total":     revenus_total,
        "depenses_total":    depenses_total,
        "valeur_nette":      valeur_nette,
        "roi_pct":           roi_pct,
        "multiplicateur":    multiplicateur,
        "mois_rentabilite":  mois_rentabilite,
        "nb_evenements":     len(evenements),
    }


# ══════════════════════════════════════════════════════════
#  SERVE FRONTEND STATIQUE
# ══════════════════════════════════════════════════════════

app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/")
async def root():
    return FileResponse("static/index.html")

@app.get("/{full_path:path}")
async def catch_all(full_path: str):
    # Ne pas intercepter les routes API
    if full_path.startswith("api/"):
        raise HTTPException(status_code=404, detail=f"Route /api/{full_path} non trouvée")
    return FileResponse("static/index.html")
