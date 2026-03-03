"""
Module pour gérer l'intégration avec Airtable
Permet de stocker et récupérer les données des plantes
"""

import os
import requests
from typing import Dict, List, Optional
from dataclasses import asdict
import json

class AirtableClient:
    """Client pour interagir avec l'API Airtable"""
    
    def __init__(self):
        # Récupérer les credentials depuis variables d'environnement
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
    
    def _request(self, method: str, endpoint: str, data: Optional[Dict] = None) -> Optional[Dict]:
        """Effectue une requête à l'API Airtable"""
        if not self.enabled:
            return None
        
        url = f"{self.base_url}/{endpoint}"
        
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
    
    def transform_plant_data(self, plant_data: Dict) -> Dict:
        """
        Transforme les données d'une plante pour Airtable
        Adapte les noms de champs et les formats
        """
        fields = {}
        
        # DEBUG: Afficher ce qui est reçu
        print(f"📥 transform_plant_data - Données reçues:")
        print(f"   - Champs racine: {list(plant_data.keys())}")
        if plant_data.get('details'):
            print(f"   - Champs dans details: {len(plant_data['details'].keys())} champs")
            print(f"   - Liste: {list(plant_data['details'].keys())}")
        
        # Champs basiques
        if plant_data.get('nom_francais'):
            fields['nom_francais'] = plant_data['nom_francais']
        
        if plant_data.get('nom_latin'):
            fields['nom_latin'] = plant_data['nom_latin']
        
        if plant_data.get('famille'):
            fields['famille'] = plant_data['famille']
        
        if plant_data.get('url'):
            fields['url_source'] = plant_data['url']
        
        # Dimensions
        if plant_data.get('hauteur_maturite'):
            fields['hauteur_maturite'] = plant_data['hauteur_maturite']
        
        if plant_data.get('largeur_maturite'):
            fields['largeur_maturite'] = plant_data['largeur_maturite']
        
        if plant_data.get('type_plante'):
            fields['type_plante'] = plant_data['type_plante']
        
        # Exposition
        if plant_data.get('exposition'):
            # Convertir en liste si c'est une string
            expo = plant_data['exposition']
            if isinstance(expo, str):
                # Essayer de parser les multiples expositions
                fields['exposition'] = [e.strip() for e in expo.split(',')]
            else:
                fields['exposition'] = [expo]
        
        # Floraison
        if plant_data.get('periode_floraison'):
            fields['periode_floraison'] = plant_data['periode_floraison']
        
        # Description
        if plant_data.get('description'):
            fields['description_courte'] = plant_data['description']
        
        # Prix
        if plant_data.get('prix'):
            fields['prix'] = plant_data['prix']
        
        # Image
        if plant_data.get('image_principale'):
            fields['image_principale'] = plant_data['image_principale']
        
        # Détails si disponibles
        details = plant_data.get('details', {})
        if details:
            # Dimensions
            if details.get('hauteur_maturite'):
                fields['hauteur_maturite'] = details['hauteur_maturite']
            
            if details.get('largeur_maturite'):
                fields['largeur_maturite'] = details['largeur_maturite']
            
            # Exposition (peut être écrasée par details)
            if details.get('exposition'):
                expo = details['exposition']
                if isinstance(expo, str):
                    fields['exposition'] = [e.strip() for e in expo.split(',')]
                else:
                    fields['exposition'] = [expo]
            
            # Floraison
            if details.get('periode_floraison'):
                fields['periode_floraison'] = details['periode_floraison']
            
            if details.get('couleur_fleurs'):
                fields['couleur_fleurs'] = details['couleur_fleurs']
            
            if details.get('duree_floraison'):
                fields['duree_floraison'] = details['duree_floraison']
            
            # Feuillage et port
            if details.get('feuillage'):
                fields['feuillage'] = details['feuillage']
            
            if details.get('port'):
                fields['port'] = details['port']
            
            # Sol
            if details.get('sol_type'):
                fields['sol_type'] = details['sol_type']
            
            if details.get('sol_ph'):
                fields['sol_ph'] = details['sol_ph']
            
            if details.get('sol_humidite'):
                fields['sol_humidite'] = details['sol_humidite']
            
            if details.get('sol_drainage'):
                fields['sol_drainage'] = details['sol_drainage']
            
            # Type de plante (peut être écrasé par details)
            if details.get('type_plante'):
                fields['type_plante'] = details['type_plante']
            
            # Descriptions
            if details.get('description_complete'):
                fields['description_complete'] = details['description_complete']
            
            if details.get('description_courte'):
                fields['description_courte'] = details['description_courte']
            
            # Utilisations
            if details.get('utilisations'):
                fields['utilisations'] = details['utilisations']
            
            # Plantation
            if details.get('meilleure_periode_plantation'):
                fields['meilleure_periode_plantation'] = details['meilleure_periode_plantation']
            
            if details.get('periode_raisonnable_plantation'):
                fields['periode_raisonnable_plantation'] = details['periode_raisonnable_plantation']
            
            if details.get('densite_plantation'):
                fields['densite_plantation'] = details['densite_plantation']
            
            # Taille
            if details.get('periode_taille'):
                fields['taille_periode'] = details['periode_taille']
            
            if details.get('descriptif_taille_detaille'):
                fields['taille_technique'] = details['descriptif_taille_detaille']
            
            if details.get('periode_raisonnable_taille'):
                fields['periode_raisonnable_taille'] = details['periode_raisonnable_taille']
            
            # Rusticité
            if details.get('rusticite'):
                fields['rusticite_zone'] = details['rusticite']
            
            if details.get('rusticite_min_celsius'):
                fields['rusticite_min_celsius'] = details['rusticite_min_celsius']
            
            # Botanique
            if details.get('famille'):
                fields['famille'] = details['famille']
            
            if details.get('autres_noms'):
                fields['autres_noms'] = details['autres_noms']
            
            # Image (peut être écrasée par details)
            if details.get('image_principale'):
                fields['image_principale'] = details['image_principale']
        
        # Données enrichies AuJardin.info
        if plant_data.get('arrosage_detail'):
            fields['arrosage_detail'] = plant_data['arrosage_detail']
        
        if plant_data.get('arrosage'):
            fields['arrosage_frequence'] = plant_data['arrosage']
        
        if plant_data.get('fertilisation_detail'):
            fields['fertilisation'] = plant_data['fertilisation_detail']
        
        if plant_data.get('taille_periode') and not fields.get('taille_periode'):
            fields['taille_periode'] = plant_data['taille_periode']
        
        if plant_data.get('taille_technique') and not fields.get('taille_technique'):
            fields['taille_technique'] = plant_data['taille_technique']
        
        if plant_data.get('multiplication'):
            fields['multiplication'] = plant_data['multiplication']
        
        if plant_data.get('multiplication_detail'):
            if 'multiplication' in fields:
                fields['multiplication'] += f" - {plant_data['multiplication_detail']}"
            else:
                fields['multiplication'] = plant_data['multiplication_detail']
        
        if plant_data.get('rusticite') and not fields.get('rusticite_zone'):
            fields['rusticite_zone'] = plant_data['rusticite']
        
        if plant_data.get('sol_type'):
            fields['sol_type'] = plant_data['sol_type']
        
        if plant_data.get('sol_ph'):
            fields['sol_ph'] = plant_data['sol_ph']
        
        # Source
        fields['source'] = plant_data.get('source', 'Promesse de Fleurs')
        fields['statut'] = 'Complet' if (details or plant_data.get('arrosage_detail')) else 'Partiel'
        
        # SÉCURITÉ: Liste blanche des champs Airtable autorisés
        # Ceci empêche d'envoyer des champs qui n'existent pas dans Airtable
        ALLOWED_FIELDS = {
            'nom_francais', 'nom_latin', 'autres_noms', 'famille', 'url_source',
            'hauteur_maturite', 'largeur_maturite', 'type_plante', 'feuillage', 'port',
            'periode_floraison', 'couleur_fleurs', 'duree_floraison', 
            'exposition', 'rusticite_zone', 'rusticite_min_celsius',
            'sol_type', 'sol_ph', 'sol_humidite', 'sol_drainage',
            'meilleure_periode_plantation', 'periode_raisonnable_plantation', 'densite_plantation',
            'arrosage_frequence', 'arrosage_detail', 'fertilisation',
            'taille_periode', 'taille_technique', 'multiplication',
            'periode_taille', 'periode_raisonnable_taille', 'paillage', 'tuteurage', 'rabattage_periode',
            'description_courte', 'description_complete', 'utilisations',
            'image_principale', 'prix', 'disponibilite', 'source', 'statut', 'notes_internes'
        }
        
        # Filtrer pour ne garder que les champs autorisés
        cleaned_fields = {k: v for k, v in fields.items() if k in ALLOWED_FIELDS}
        
        # Debug: afficher les champs rejetés si on en a
        rejected = set(fields.keys()) - set(cleaned_fields.keys())
        if rejected:
            print(f"⚠️ Champs rejetés (n'existent pas dans Airtable): {rejected}")
        
        return cleaned_fields
    
    def find_plant_by_latin_name(self, nom_latin: str) -> Optional[str]:
        """
        Cherche une plante par son nom latin
        Retourne le record ID si trouvée
        """
        if not self.enabled:
            return None
        
        # Utiliser filterByFormula pour chercher
        formula = f"{{nom_latin}}='{nom_latin}'"
        params = {'filterByFormula': formula}
        
        response = self._request('GET', f"{self.table_plantes}?{requests.compat.urlencode(params)}")
        
        if response and response.get('records'):
            return response['records'][0]['id']
        
        return None
    
    def create_plant(self, plant_data: Dict) -> Optional[str]:
        """
        Crée une nouvelle plante dans Airtable
        Retourne le record ID si succès
        """
        if not self.enabled:
            return None
        
        # Transformer les données
        fields = self.transform_plant_data(plant_data)
        
        # DEBUG: Afficher les noms de champs envoyés
        print(f"🔍 DEBUG Airtable - Champs envoyés: {list(fields.keys())}")
        
        # Créer le record
        data = {
            'fields': fields
        }
        
        # DEBUG: Afficher le JSON complet
        import json
        print(f"📤 JSON complet envoyé:")
        print(json.dumps(data, indent=2, ensure_ascii=False))
        
        response = self._request('POST', self.table_plantes, data)
        
        if response and response.get('id'):
            print(f"✅ Plante créée dans Airtable: {fields.get('nom_francais')} (ID: {response['id']})")
            return response['id']
        
        return None
    
    def update_plant(self, record_id: str, plant_data: Dict) -> bool:
        """
        Met à jour une plante existante dans Airtable
        """
        if not self.enabled:
            return False
        
        # Transformer les données
        fields = self.transform_plant_data(plant_data)
        
        # Mettre à jour le record
        data = {
            'fields': fields
        }
        
        response = self._request('PATCH', f"{self.table_plantes}/{record_id}", data)
        
        if response and response.get('id'):
            print(f"✅ Plante mise à jour dans Airtable: {fields.get('nom_francais')}")
            return True
        
        return False
    
    def upsert_plant(self, plant_data: Dict) -> Optional[str]:
        """
        Crée ou met à jour une plante
        (Upsert = Update or Insert)
        """
        if not self.enabled:
            return None
        
        nom_latin = plant_data.get('nom_latin')
        
        if not nom_latin:
            print("⚠️ Pas de nom latin, impossible de faire un upsert")
            return self.create_plant(plant_data)
        
        # Chercher si la plante existe déjà
        record_id = self.find_plant_by_latin_name(nom_latin)
        
        if record_id:
            # Mise à jour
            self.update_plant(record_id, plant_data)
            return record_id
        else:
            # Création
            return self.create_plant(plant_data)
    
    def get_plant(self, record_id: str) -> Optional[Dict]:
        """Récupère une plante par son ID"""
        if not self.enabled:
            return None
        
        response = self._request('GET', f"{self.table_plantes}/{record_id}")
        
        if response:
            return response.get('fields', {})
        
        return None
    
    def get_all_plants(self, view: Optional[str] = None) -> List[Dict]:
        """
        Récupère toutes les plantes
        Peut filtrer par vue Airtable
        """
        if not self.enabled:
            return []
        
        endpoint = self.table_plantes
        if view:
            endpoint += f"?view={view}"
        
        all_records = []
        offset = None
        
        while True:
            url = endpoint
            if offset:
                url += f"{'&' if '?' in url else '?'}offset={offset}"
            
            response = self._request('GET', url)
            
            if not response:
                break
            
            records = response.get('records', [])
            all_records.extend([r['fields'] for r in records])
            
            # Pagination
            offset = response.get('offset')
            if not offset:
                break
        
        print(f"✅ {len(all_records)} plantes récupérées depuis Airtable")
        return all_records
    
    def sync_formats(self, nom_latin: str, formats: List[Dict]) -> bool:
        """
        Synchronise les formats de vente pour une plante
        """
        if not self.enabled or not formats:
            return False
        
        # Trouver la plante
        plant_record_id = self.find_plant_by_latin_name(nom_latin)
        
        if not plant_record_id:
            print(f"⚠️ Plante {nom_latin} non trouvée pour sync formats")
            return False
        
        # Créer les formats
        for format_data in formats:
            fields = {
                'nom_format': format_data.get('format', 'Inconnu'),
                'prix': format_data.get('prix', ''),
                'disponibilite': format_data.get('disponibilite', 'Inconnu'),
                'plante': [plant_record_id]  # Link to plant
            }
            
            if format_data.get('url'):
                fields['url_achat'] = format_data['url']
            
            data = {'fields': fields}
            self._request('POST', self.table_formats, data)
        
        print(f"✅ {len(formats)} formats synchronisés pour {nom_latin}")
        return True
    
    def test_connection(self) -> bool:
        """Test la connexion à Airtable"""
        if not self.enabled:
            print("❌ Airtable désactivé")
            return False
        
        response = self._request('GET', self.table_plantes + '?maxRecords=1')
        
        if response is not None:
            print("✅ Connexion Airtable OK")
            return True
        else:
            print("❌ Connexion Airtable échouée")
            return False


# Instance globale
airtable_client = AirtableClient()


if __name__ == "__main__":
    # Tests
    print("=== Test Airtable Client ===\n")
    
    # Test connexion
    if airtable_client.enabled:
        airtable_client.test_connection()
        
        # Test création plante
        test_plant = {
            'nom_francais': 'Lavande vraie (TEST)',
            'nom_latin': 'Lavandula angustifolia TEST',
            'famille': 'Lamiacées',
            'type_plante': 'Vivace',
            'exposition': 'Plein soleil',
            'description': 'Test depuis Python',
            'prix': '8,90 €',
            'url': 'https://example.com'
        }
        
        record_id = airtable_client.create_plant(test_plant)
        
        if record_id:
            print(f"\n✅ Test réussi ! Record ID: {record_id}")
            print("⚠️ N'oubliez pas de supprimer ce record de test dans Airtable")
    else:
        print("⚠️ Configurez vos credentials Airtable pour tester")
