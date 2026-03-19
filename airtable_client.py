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
        self.table_tags = os.environ.get('AIRTABLE_TABLE_TAGS', 'Tags')
        self.table_taches = os.environ.get('AIRTABLE_TABLE_TACHES', 'Taches')
        
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
            
        except requests.exceptions.HTTPError as e:
            print(f"❌ Erreur Airtable HTTP {e.response.status_code}: {e}")
            # Afficher le détail de l'erreur pour 422
            if e.response.status_code == 422:
                try:
                    error_detail = e.response.json()
                    print(f"📋 Détail erreur 422:")
                    import json
                    print(json.dumps(error_detail, indent=2, ensure_ascii=False))
                except:
                    print(f"📋 Réponse brute: {e.response.text}")
            return None
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
        
        # Type de plante (IMPORTANT: doit être "Texte long" dans Airtable, pas "Sélection unique")
        if plant_data.get('type_plante'):
            try:
                fields['type_plante'] = plant_data['type_plante']
            except Exception as e:
                print(f"⚠️ Erreur type_plante: {e}")
                print(f"   💡 Dans Airtable, change le type du champ 'type_plante' en 'Texte long'")
        
        # Exposition
        if plant_data.get('exposition'):
            # Convertir en liste si c'est une string
            expo = plant_data['exposition']
            if isinstance(expo, list):
                # Déjà une liste, utiliser telle quelle
                fields['exposition'] = expo
            elif isinstance(expo, str):
                # Essayer de parser les multiples expositions
                fields['exposition'] = [e.strip() for e in expo.split(',')]
            else:
                fields['exposition'] = [str(expo)]
        
        # Floraison
        if plant_data.get('periode_floraison'):
            fields['periode_floraison'] = plant_data['periode_floraison']
        
        # Description
        if plant_data.get('description'):
            fields['description_courte'] = plant_data['description']
        
        # Prix
        if plant_data.get('prix'):
            fields['prix'] = plant_data['prix']
        
        # Disponibilité
        if plant_data.get('disponibilite'):
            fields['disponibilite'] = plant_data['disponibilite']
        
        # Image
        if plant_data.get('image_principale'):
            fields['image_principale'] = plant_data['image_principale']
        
        # Détails si disponibles
        details = plant_data.get('details', {})
        if details:
            # Dimensions (priorité aux details)
            if details.get('hauteur_maturite') and not fields.get('hauteur_maturite'):
                fields['hauteur_maturite'] = details['hauteur_maturite']
            
            if details.get('largeur_maturite') and not fields.get('largeur_maturite'):
                fields['largeur_maturite'] = details['largeur_maturite']
            
            # Exposition (peut être écrasée par details)
            if details.get('exposition'):
                expo = details['exposition']
                if isinstance(expo, str):
                    fields['exposition'] = [e.strip() for e in expo.split(',')]
                elif isinstance(expo, list):
                    fields['exposition'] = expo
                else:
                    fields['exposition'] = [expo]
            
            # Floraison
            if details.get('periode_floraison'):
                fields['periode_floraison'] = details['periode_floraison']
            
            # Couleur fleurs (IMPORTANT: doit être "Texte long" dans Airtable)
            if details.get('couleur_fleur'):
                try:
                    fields['couleur_fleurs'] = details['couleur_fleur']
                except Exception as e:
                    print(f"⚠️ Erreur couleur_fleurs: {e}")
                    print(f"   💡 Dans Airtable, change le type du champ 'couleur_fleurs' en 'Texte long'")
            elif details.get('couleur_fleurs'):
                try:
                    fields['couleur_fleurs'] = details['couleur_fleurs']
                except Exception as e:
                    print(f"⚠️ Erreur couleur_fleurs: {e}")
            
            if details.get('duree_floraison'):
                fields['duree_floraison'] = details['duree_floraison']
            
            # Feuillage et port
            # persistance_feuillage (pas feuillage !)
            if details.get('persistance_feuillage'):
                fields['feuillage'] = details['persistance_feuillage']
            
            if details.get('couleur_feuillage'):
                if fields.get('feuillage'):
                    fields['feuillage'] += f" - {details['couleur_feuillage']}"
                else:
                    fields['feuillage'] = details['couleur_feuillage']
            
            if details.get('port'):
                fields['port'] = details['port']
            
            # Sol (ATTENTION : noms inversés !)
            # details a type_sol, ph_sol, humidite_sol
            # Airtable veut sol_type, sol_ph, sol_humidite
            if details.get('type_sol'):
                fields['sol_type'] = details['type_sol']
            
            if details.get('ph_sol'):
                fields['sol_ph'] = details['ph_sol']
            
            if details.get('humidite_sol'):
                fields['sol_humidite'] = details['humidite_sol']
            
            if details.get('sol_drainage'):
                fields['sol_drainage'] = details['sol_drainage']
            
            # Type de plante (peut être écrasé par details)
            if details.get('type_plante'):
                try:
                    fields['type_plante'] = details['type_plante']
                except Exception as e:
                    print(f"⚠️ Erreur type_plante (details): {e}")
            
            # Descriptions
            if details.get('description_detaillee'):
                fields['description_complete'] = details['description_detaillee']
            
            if details.get('description_courte') and not fields.get('description_courte'):
                fields['description_courte'] = details['description_courte']
            
            # Utilisations
            if details.get('type_utilisation'):
                fields['utilisations'] = details['type_utilisation']
            elif details.get('convient_pour'):
                fields['utilisations'] = details['convient_pour']
            
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
                # Dupliquer dans periode_taille (autre champ) pour compatibilité
                fields['periode_taille'] = details['periode_taille']
            
            if details.get('descriptif_taille_detaille'):
                fields['taille_technique'] = details['descriptif_taille_detaille']
            elif details.get('taille'):
                fields['taille_technique'] = details['taille']
            
            if details.get('periode_raisonnable_taille'):
                fields['periode_raisonnable_taille'] = details['periode_raisonnable_taille']
            
            if details.get('frequence_taille'):
                # Ajouter à taille_technique si existe déjà
                if fields.get('taille_technique'):
                    fields['taille_technique'] = f"{details['frequence_taille']}. {fields['taille_technique']}"
                else:
                    fields['taille_technique'] = details['frequence_taille']
            
            # Entretien supplémentaire
            if details.get('paillage'):
                fields['paillage'] = details['paillage']
            
            if details.get('tuteurage'):
                fields['tuteurage'] = details['tuteurage']
            
            if details.get('rabattage_periode'):
                fields['rabattage_periode'] = details['rabattage_periode']
            
            # Rusticité
            if details.get('rusticite'):
                fields['rusticite_zone'] = details['rusticite']
            
            if details.get('zone_usda'):
                if fields.get('rusticite_zone'):
                    fields['rusticite_zone'] += f" (Zone USDA: {details['zone_usda']})"
                else:
                    fields['rusticite_zone'] = f"Zone USDA: {details['zone_usda']}"
            
            if details.get('rusticite_min_celsius'):
                fields['rusticite_min_celsius'] = details['rusticite_min_celsius']
            
            # Botanique
            if details.get('famille'):
                fields['famille'] = details['famille']
            
            # Champs botaniques séparés (v12.14)
            if details.get('genre'):
                fields['genre'] = details['genre']
            
            if details.get('espece'):
                fields['espece'] = details['espece']
            
            if details.get('cultivar'):
                fields['cultivar'] = details['cultivar']
            
            if details.get('origine'):
                fields['origine'] = details['origine']
            
            # Autres noms (noms communs uniquement)
            if details.get('autres_noms'):
                fields['autres_noms'] = details['autres_noms']
            
            # Sous-catégorie
            if details.get('sous_categorie'):
                fields['sous_categorie'] = details['sous_categorie']
            
            # Image (peut être écrasée par details)
            if details.get('image_principale') and not fields.get('image_principale'):
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
            'nom_francais', 'nom_latin', 'autres_noms', 'famille', 'genre', 'espece', 'cultivar', 'origine', 'type_plante', 'url_source',
            'hauteur_maturite', 'largeur_maturite', 'feuillage', 'port',
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
        
        
        # IMPORTANT : type_plante et couleur_fleurs
        # Si tu obtiens des erreurs 422 avec ces champs, c'est qu'ils sont définis
        # comme "Sélection unique/multiple" dans Airtable.
        # 
        # SOLUTION : Dans Airtable, change le type de ces champs en "Texte long"
        # 
        # Les erreurs s'afficheront dans les logs mais ne bloqueront pas l'insertion
        
        # Filtrer pour ne garder que les champs autorisés
        cleaned_fields = {k: v for k, v in fields.items() if k in ALLOWED_FIELDS}
        
        # Debug: afficher les champs rejetés si on en a
        rejected = set(fields.keys()) - set(cleaned_fields.keys())
        if rejected:
            print(f"⚠️ Champs rejetés (n'existent pas dans Airtable): {rejected}")
        
        return cleaned_fields
    
    def _escape_formula_value(self, value: str) -> str:
        """
        Échappe les caractères spéciaux pour les formules Airtable
        Les apostrophes doivent être doublées dans les formules Airtable
        """
        if not value:
            return ''
        # Doubler les apostrophes pour Airtable
        return value.replace("'", "''")
    
    def find_plant_by_latin_name(self, nom_latin: str) -> Optional[str]:
        """
        Cherche une plante par son nom latin
        Retourne le record ID si trouvée
        """
        if not self.enabled:
            return None
        
        # Échapper les apostrophes dans nom_latin pour la formule
        escaped_nom_latin = self._escape_formula_value(nom_latin)
        
        # Utiliser filterByFormula pour chercher
        formula = f"{{nom_latin}}='{escaped_nom_latin}'"
        
        # Encoder proprement la formule pour l'URL
        from urllib.parse import quote
        encoded_formula = quote(formula)
        
        response = self._request('GET', f"{self.table_plantes}?filterByFormula={encoded_formula}")
        
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
    
    def delete_plant(self, record_id: str) -> bool:
        """Supprime une plante par son record ID Airtable"""
        if not self.enabled:
            return False
        
        response = self._request('DELETE', f"{self.table_plantes}/{record_id}")
        
        if response and response.get('deleted'):
            print(f"✅ Plante supprimée dans Airtable: {record_id}")
            return True
        
        return False
    
    def delete_plant_by_latin_name(self, nom_latin: str) -> bool:
        """Supprime une plante par son nom latin"""
        if not self.enabled:
            return False
        
        # Trouver le record ID
        record_id = self.find_plant_by_latin_name(nom_latin)
        
        if record_id:
            return self.delete_plant(record_id)
        else:
            print(f"⚠️ Plante non trouvée dans Airtable pour suppression: {nom_latin}")
            return False
    
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
            # Retourner les fields ET l'ID du record
            for r in records:
                fields = r['fields'].copy()
                fields['airtable_record_id'] = r['id']  # Ajouter l'ID Airtable
                all_records.append(fields)
            
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
    
    # ====== MÉTHODES TAGS ======
    
    def get_all_tags(self) -> List[Dict]:
        """Récupère tous les tags depuis Airtable"""
        if not self.enabled:
            return []
        
        try:
            result = self._request('GET', self.table_tags)
            if result and 'records' in result:
                tags = []
                for record in result['records']:
                    fields = record.get('fields', {})
                    if 'tag_id' in fields:
                        tags.append({
                            'id': fields['tag_id'],
                            'name': fields.get('name', ''),
                            'color': fields.get('color', '#4CAF50'),
                            'created_at': fields.get('created_at', ''),
                            'airtable_id': record['id']  # Pour les mises à jour
                        })
                print(f"✅ {len(tags)} tags chargés depuis Airtable")
                return tags
        except Exception as e:
            print(f"❌ Erreur chargement tags: {e}")
        
        return []
    
    def create_tag(self, tag_data: Dict) -> Optional[str]:
        """Crée un tag dans Airtable
        
        Args:
            tag_data: Dict avec 'tag_id', 'name', 'color', 'created_at'
        
        Returns:
            Record ID si succès, None sinon
        """
        if not self.enabled:
            return None
        
        try:
            fields = {
                'tag_id': tag_data['tag_id'],
                'name': tag_data['name'],
                'color': tag_data.get('color', '#4CAF50'),
                'created_at': tag_data.get('created_at', '')
            }
            
            data = {'fields': fields}
            result = self._request('POST', self.table_tags, data)
            
            if result and 'id' in result:
                print(f"✅ Tag '{tag_data['name']}' créé dans Airtable")
                return result['id']
        except Exception as e:
            print(f"❌ Erreur création tag: {e}")
        
        return None
    
    def delete_tag(self, tag_id: int) -> bool:
        """Supprime un tag d'Airtable
        
        Args:
            tag_id: ID du tag à supprimer
        
        Returns:
            True si succès, False sinon
        """
        if not self.enabled:
            return False
        
        try:
            # Trouver le record Airtable avec ce tag_id
            from urllib.parse import quote
            formula = f"{{tag_id}}={tag_id}"
            
            result = self._request('GET', f"{self.table_tags}?filterByFormula={quote(formula)}")
            
            if result and 'records' in result and len(result['records']) > 0:
                record_id = result['records'][0]['id']
                delete_result = self._request('DELETE', f"{self.table_tags}/{record_id}")
                
                if delete_result:
                    print(f"✅ Tag {tag_id} supprimé d'Airtable")
                    return True
        except Exception as e:
            print(f"❌ Erreur suppression tag: {e}")
        
        return False
    
    def update_plant_tags(self, record_id: str, tags: List[int]) -> bool:
        """Met à jour les tags d'une plante dans Airtable
        
        Args:
            record_id: ID du record Airtable de la plante
            tags: Liste des IDs de tags [1, 3, 5]
        
        Returns:
            True si succès, False sinon
        """
        if not self.enabled:
            return False
        
        try:
            # Convertir la liste en JSON
            tags_json = json.dumps(tags)
            
            data = {
                'fields': {
                    'tags': tags_json
                }
            }
            
            result = self._request('PATCH', f"{self.table_plantes}/{record_id}", data)
            
            if result:
                print(f"✅ Tags mis à jour pour plante {record_id}")
                return True
        except Exception as e:
            print(f"❌ Erreur mise à jour tags plante: {e}")
        
        return False
    
    def update_plant_notes_quantity(self, record_id: str, notes: str, quantity: int) -> bool:
        """Met à jour les notes et quantité d'une plante dans Airtable
        
        Args:
            record_id: ID du record Airtable de la plante
            notes: Texte des notes
            quantity: Quantité (nombre entier)
        
        Returns:
            True si succès, False sinon
        """
        if not self.enabled:
            return False
        
        try:
            data = {
                'fields': {
                    'notes': notes,
                    'quantity': quantity
                }
            }
            
            result = self._request('PATCH', f"{self.table_plantes}/{record_id}", data)
            
            if result:
                print(f"✅ Notes/quantité mis à jour pour plante {record_id}")
                return True
        except Exception as e:
            print(f"❌ Erreur mise à jour notes/quantité plante: {e}")
        
        return False
    
    # ====== MÉTHODES TÂCHES ======
    
    def get_all_tasks(self) -> List[Dict]:
        """Récupère toutes les tâches depuis Airtable"""
        if not self.enabled:
            return []
        
        try:
            result = self._request('GET', self.table_taches)
            if result and 'records' in result:
                tasks = []
                for record in result['records']:
                    fields = record.get('fields', {})
                    if 'task_id' in fields:
                        tasks.append({
                            'id': fields['task_id'],
                            'title': fields.get('title', ''),
                            'description': fields.get('description', ''),
                            'category': fields.get('category', 'Autre'),
                            'status': fields.get('status', 'todo'),
                            'created_at': fields.get('created_at', ''),
                            'completed_at': fields.get('completed_at', ''),
                            'airtable_id': record['id']
                        })
                print(f"✅ {len(tasks)} tâches chargées depuis Airtable")
                return tasks
        except Exception as e:
            print(f"❌ Erreur chargement tâches: {e}")
        
        return []
    
    def create_task(self, task_data: Dict) -> Optional[str]:
        """Crée une tâche dans Airtable"""
        if not self.enabled:
            return None
        
        try:
            fields = {
                'task_id': task_data['task_id'],
                'title': task_data['title'],
                'description': task_data.get('description', ''),
                'category': task_data.get('category', 'Autre'),
                'status': task_data.get('status', 'todo'),
                'created_at': task_data.get('created_at', '')
            }
            
            if task_data.get('completed_at'):
                fields['completed_at'] = task_data['completed_at']
            
            data = {'fields': fields}
            result = self._request('POST', self.table_taches, data)
            
            if result and 'id' in result:
                print(f"✅ Tâche '{task_data['title']}' créée dans Airtable")
                return result['id']
        except Exception as e:
            print(f"❌ Erreur création tâche: {e}")
        
        return None
    
    def update_task(self, record_id: str, task_data: Dict) -> bool:
        """Met à jour une tâche dans Airtable"""
        if not self.enabled:
            return False
        
        try:
            fields = {}
            
            if 'title' in task_data:
                fields['title'] = task_data['title']
            if 'description' in task_data:
                fields['description'] = task_data['description']
            if 'category' in task_data:
                fields['category'] = task_data['category']
            if 'status' in task_data:
                fields['status'] = task_data['status']
            if 'completed_at' in task_data:
                fields['completed_at'] = task_data['completed_at']
            
            data = {'fields': fields}
            result = self._request('PATCH', f"{self.table_taches}/{record_id}", data)
            
            if result:
                print(f"✅ Tâche {record_id} mise à jour")
                return True
        except Exception as e:
            print(f"❌ Erreur mise à jour tâche: {e}")
        
        return False
    
    def delete_task(self, task_id: int) -> bool:
        """Supprime une tâche d'Airtable"""
        if not self.enabled:
            return False
        
        try:
            from urllib.parse import quote
            formula = f"{{task_id}}={task_id}"
            
            result = self._request('GET', f"{self.table_taches}?filterByFormula={quote(formula)}")
            
            if result and 'records' in result and len(result['records']) > 0:
                record_id = result['records'][0]['id']
                delete_result = self._request('DELETE', f"{self.table_taches}/{record_id}")
                
                if delete_result:
                    print(f"✅ Tâche {task_id} supprimée d'Airtable")
                    return True
        except Exception as e:
            print(f"❌ Erreur suppression tâche: {e}")
        
        return False
    
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
