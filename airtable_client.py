import os
import requests
from typing import Dict, List, Optional
import json

class AirtableClient:
    """Client pour interagir avec l'API Airtable"""

    def __init__(self):
        self.api_key = os.environ.get('AIRTABLE_API_KEY', '')
        self.base_id = os.environ.get('AIRTABLE_BASE_ID', '')
        self.table_plantes = os.environ.get('AIRTABLE_TABLE_PLANTES', 'Plantes')
        self.table_maladies = os.environ.get('AIRTABLE_TABLE_MALADIES', 'Maladies')
        self.table_parasites = os.environ.get('AIRTABLE_TABLE_PARASITES', 'Parasites')
        self.table_formats = os.environ.get('AIRTABLE_TABLE_FORMATS', 'Formats')

        self.base_url = f"https://api.airtable.com/v0/{self.base_id}"
        self.headers = {
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json'
        }

        self.enabled = bool(self.api_key and self.base_id)

        if self.enabled:
            print("✅ Airtable activé")
        else:
            print("⚠️ Airtable désactivé (credentials manquants)")

    # ---------------------------------------------------------
    #  REQUEST WRAPPER
    # ---------------------------------------------------------
    def _request(self, method: str, endpoint: str, data: Optional[Dict] = None) -> Optional[Dict]:
        if not self.enabled:
            return None

        url = f"{self.base_url}/{endpoint}"

        print(f"➡️ Appel Airtable : {method} {url}")
        if data:
            print("➡️ Payload brut envoyé :")
            print(json.dumps(data, indent=2, ensure_ascii=False))

        try:
            if method == 'GET':
                response = requests.get(url, headers=self.headers)
            elif method == 'POST':
                response = requests.post(url, headers=self.headers, json=data)
            elif method == 'PATCH':
                response = requests.patch(url, headers=self.headers, json=data)
            elif method == 'DELETE':
                response = requests.delete(url, headers=self.headers)
            else:
                return None

            response.raise_for_status()
            return response.json()

        except requests.exceptions.RequestException as e:
            print(f"❌ Erreur Airtable API: {e}")
            return None

    # ---------------------------------------------------------
    #  TRANSFORMATION DES DONNÉES
    # ---------------------------------------------------------
    def transform_plant_data(self, plant_data: Dict) -> Dict:
        fields = {}

        # Champs simples
        for key in [
            "nom_francais", "nom_latin", "famille", "hauteur_maturite",
            "largeur_maturite", "type_plante", "periode_floraison",
            "description", "prix", "image_principale"
        ]:
            if plant_data.get(key):
                fields[key] = plant_data[key]

        # URL
        if plant_data.get("url"):
            fields["url_source"] = plant_data["url"]

        # Exposition (multi-select)
        if plant_data.get("exposition"):
            expo = plant_data["exposition"]
            if isinstance(expo, str):
                fields["exposition"] = [e.strip() for e in expo.split(",")]
            else:
                fields["exposition"] = expo

        # Détails
        details = plant_data.get("details", {})
        for key in [
            "description_complete", "meilleure_periode_plantation",
            "periode_raisonnable_plantation", "densite_plantation",
            "periode_taille", "descriptif_taille_detaille", "rusticite"
        ]:
            if details.get(key):
                fields[key] = details[key]

        # Enrichissements
        if plant_data.get("arrosage_detail"):
            fields["arrosage_detail"] = plant_data["arrosage_detail"]

        if plant_data.get("arrosage"):
            fields["arrosage_frequence"] = plant_data["arrosage"]

        if plant_data.get("fertilisation_detail"):
            fields["fertilisation"] = plant_data["fertilisation_detail"]

        if plant_data.get("multiplication"):
            fields["multiplication"] = plant_data["multiplication"]

        if plant_data.get("sol_type"):
            fields["sol_type"] = plant_data["sol_type"]

        if plant_data.get("sol_ph"):
            fields["sol_ph"] = plant_data["sol_ph"]

        # Meta
        fields["source"] = plant_data.get("source", "Promesse de Fleurs")
        fields["statut"] = "Complet" if details else "Partiel"

        return fields

    # ---------------------------------------------------------
    #  CRUD PLANTES
    # ---------------------------------------------------------
    def find_plant_by_latin_name(self, nom_latin: str) -> Optional[str]:
        if not self.enabled:
            return None

        formula = f"{{nom_latin}}='{nom_latin}'"
        params = {'filterByFormula': formula}

        response = self._request('GET', f"{self.table_plantes}?{requests.compat.urlencode(params)}")

        if response and response.get('records'):
            return response['records'][0]['id']

        return None

    def create_plant(self, plant_data: Dict) -> Optional[str]:
        if not self.enabled:
            return None

        fields = self.transform_plant_data(plant_data)
        data = {"fields": fields}

        print("📤 JSON envoyé à Airtable (CREATE) :")
        print(json.dumps(data, indent=2, ensure_ascii=False))

        response = self._request('POST', self.table_plantes, data)

        if response and response.get("id"):
            print(f"✅ Plante créée : {fields.get('nom_francais')} (ID: {response['id']})")
            return response["id"]

        return None

    def update_plant(self, record_id: str, plant_data: Dict) -> bool:
        if not self.enabled:
            return False

        fields = self.transform_plant_data(plant_data)
        data = {"fields": fields}

        print("📤 JSON envoyé à Airtable (UPDATE) :")
        print(json.dumps(data, indent=2, ensure_ascii=False))

        response = self._request('PATCH', f"{self.table_plantes}/{record_id}", data)

        if response and response.get("id"):
            print(f"✅ Plante mise à jour : {fields.get('nom_francais')}")
            return True

        return False

    def upsert_plant(self, plant_data: Dict) -> Optional[str]:
        if not self.enabled:
            return None

        nom_latin = plant_data.get("nom_latin")
        if not nom_latin:
            print("⚠️ Pas de nom latin → création directe")
            return self.create_plant(plant_data)

        record_id = self.find_plant_by_latin_name(nom_latin)

        if record_id:
            return self.update_plant(record_id, plant_data)
        else:
            return self.create_plant(plant_data)


# Instance globale
airtable_client = AirtableClient()
