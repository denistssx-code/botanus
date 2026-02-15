from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
from dataclasses import dataclass, asdict
from typing import List, Dict
import json
import os
import requests
from bs4 import BeautifulSoup
import re

app = Flask(__name__, static_folder='static')
CORS(app)

@dataclass
class PlantInfo:
    nom_francais: str = ""
    nom_latin: str = ""
    exposition: str = ""
    type_plante: str = ""
    prix: str = ""
    description: str = ""
    icon: str = "🌿"
    url: str = ""

class PromesseDeFleursScraper:
    """Scraper réel pour Promesse de Fleurs"""
    
    def __init__(self):
        self.base_url = "https://www.promessedefleurs.com"
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        }
        
        # Icônes par type de plante
        self.icons = {
            'rosier': '🌹',
            'rose': '🌹',
            'lavande': '🌿',
            'hortensia': '🌺',
            'olivier': '🌳',
            'arbre': '🌳',
            'arbuste': '🌳',
            'vivace': '🌸',
            'graminée': '🌾',
            'tomate': '🍅',
            'basilic': '🌿',
            'plante': '🌿'
        }
    
    def get_icon(self, name: str, type_plante: str = "") -> str:
        """Détermine l'icône selon le nom ou type"""
        search_text = (name + " " + type_plante).lower()
        
        for key, icon in self.icons.items():
            if key in search_text:
                return icon
        
        return '🌿'
    
    def clean_text(self, text: str) -> str:
        """Nettoie le texte HTML"""
        if not text:
            return ""
        return re.sub(r'\s+', ' ', text).strip()
    
    def extract_price(self, price_text: str) -> str:
        """Extrait et formate le prix"""
        if not price_text:
            return "Prix non disponible"
        
        # Chercher le pattern de prix
        match = re.search(r'(\d+[,.]?\d*)\s*€', price_text)
        if match:
            return f"{match.group(1)} €"
        
        return price_text.strip()
    
    def search_plants(self, query: str, max_results: int = 10) -> List[PlantInfo]:
        """Recherche réelle sur Promesse de Fleurs"""
        
        print(f"🔍 Recherche sur Promesse de Fleurs: '{query}'")
        
        try:
            # Construire l'URL de recherche
            search_url = f"{self.base_url}/catalogsearch/result/?q={query.replace(' ', '+')}"
            
            # Faire la requête
            response = requests.get(search_url, headers=self.headers, timeout=15)
            response.raise_for_status()
            
            print(f"✅ Réponse reçue: {response.status_code}")
            
            # Parser le HTML
            soup = BeautifulSoup(response.text, 'html.parser')
            
            results = []
            
            # Chercher les produits (essayer plusieurs sélecteurs)
            products = (
                soup.find_all('li', class_='item product product-item') or
                soup.find_all('div', class_='product-item-info') or
                soup.find_all('div', class_='product-item')
            )
            
            print(f"📦 {len(products)} produits trouvés")
            
            for product in products[:max_results]:
                try:
                    plant = self.extract_plant_info(product)
                    if plant and plant.nom_francais:
                        results.append(plant)
                        print(f"   ✓ {plant.nom_francais} - {plant.prix}")
                except Exception as e:
                    print(f"   ⚠ Erreur extraction produit: {e}")
                    continue
            
            print(f"✅ Total extrait: {len(results)} plantes")
            return results
            
        except requests.RequestException as e:
            print(f"❌ Erreur requête: {e}")
            return []
        except Exception as e:
            print(f"❌ Erreur générale: {e}")
            import traceback
            traceback.print_exc()
            return []
    
    def extract_plant_info(self, product_element) -> PlantInfo:
        """Extrait les informations d'un produit"""
        
        # Nom du produit
        name_tag = (
            product_element.find('a', class_='product-item-link') or
            product_element.find('h2', class_='product-name') or
            product_element.find('a', class_='product name product-item-name')
        )
        
        nom_francais = self.clean_text(name_tag.get_text()) if name_tag else ""
        
        # URL du produit
        url = name_tag.get('href', '') if name_tag else ''
        
        # Prix
        price_tag = (
            product_element.find('span', class_='price') or
            product_element.find('span', class_='price-wrapper')
        )
        prix = self.extract_price(price_tag.get_text()) if price_tag else "Prix non disponible"
        
        # Description courte
        desc_tag = product_element.find('div', class_='product-item-description')
        description = self.clean_text(desc_tag.get_text()) if desc_tag else ""
        
        # Essayer d'extraire le nom latin (souvent entre parenthèses)
        nom_latin = ""
        latin_match = re.search(r'\(([\w\s]+)\)', nom_francais)
        if latin_match:
            nom_latin = latin_match.group(1)
            nom_francais = nom_francais.replace(f"({nom_latin})", "").strip()
        
        # Déterminer le type de plante depuis le nom ou la description
        type_plante = self.guess_plant_type(nom_francais, description)
        
        # Icône
        icon = self.get_icon(nom_francais, type_plante)
        
        return PlantInfo(
            nom_francais=nom_francais,
            nom_latin=nom_latin,
            exposition="",  # Nécessiterait d'aller sur la page détail
            type_plante=type_plante,
            prix=prix,
            description=description[:200] if description else "",
            icon=icon,
            url=url
        )
    
    def guess_plant_type(self, name: str, description: str = "") -> str:
        """Devine le type de plante depuis le nom"""
        text = (name + " " + description).lower()
        
        if any(word in text for word in ['rosier', 'rose ']):
            return "Rosier"
        elif any(word in text for word in ['arbre', 'érable', 'olivier', 'cerisier']):
            return "Arbre"
        elif any(word in text for word in ['arbuste', 'hortensia', 'buddleia']):
            return "Arbuste"
        elif any(word in text for word in ['vivace', 'lavande', 'hémérocalle']):
            return "Vivace"
        elif any(word in text for word in ['graminée', 'miscanthus', 'stipa']):
            return "Graminée"
        elif any(word in text for word in ['annuelle', 'tomate', 'basilic']):
            return "Annuelle"
        elif any(word in text for word in ['grimpant', 'clématite', 'glycine']):
            return "Grimpante"
        else:
            return "Plante"

class MockScraper:
    """Scraper de secours avec données simulées"""
    
    def __init__(self):
        self.mock_data = {
            "lavande": [
                {
                    "nom_francais": "Lavande vraie",
                    "nom_latin": "Lavandula angustifolia",
                    "exposition": "Plein soleil",
                    "type_plante": "Vivace",
                    "prix": "8,90 €",
                    "description": "Lavande officinale aux fleurs parfumées",
                    "icon": "🌿",
                    "url": ""
                }
            ],
            "rosier": [
                {
                    "nom_francais": "Rosier David Austin",
                    "nom_latin": "Rosa 'Abraham Darby'",
                    "exposition": "Soleil",
                    "type_plante": "Rosier",
                    "prix": "24,90 €",
                    "description": "Rosier anglais aux fleurs parfumées",
                    "icon": "🌹",
                    "url": ""
                }
            ]
        }
    
    def search_plants(self, query: str, max_results: int = 10) -> List[PlantInfo]:
        """Recherche dans les données mock"""
        print(f"⚠️ Utilisation du scraper de secours (mock) pour: '{query}'")
        
        results = []
        query_lower = query.lower()
        
        for key, plants_data in self.mock_data.items():
            if key in query_lower:
                for plant_data in plants_data[:max_results]:
                    plant = PlantInfo(**plant_data)
                    results.append(plant)
        
        return results

class SimpleDatabase:
    """Base de données en mémoire"""
    
    def __init__(self):
        self.plants = []
        self.library = []
    
    def search_local(self, query: str) -> List[PlantInfo]:
        query_lower = query.lower()
        results = []
        
        for plant in self.plants:
            if (query_lower in plant.nom_francais.lower() or 
                query_lower in plant.nom_latin.lower()):
                results.append(plant)
        
        return results
    
    def save_plant(self, plant: PlantInfo) -> int:
        for i, existing in enumerate(self.plants):
            if (existing.nom_francais == plant.nom_francais and 
                (not plant.nom_latin or existing.nom_latin == plant.nom_latin)):
                return i
        
        self.plants.append(plant)
        return len(self.plants) - 1
    
    def add_to_library(self, plant_id: int, notes: str = "", quantity: int = 1):
        if 0 <= plant_id < len(self.plants):
            for item in self.library:
                if item['plant_id'] == plant_id:
                    item['quantity'] += quantity
                    return True
            
            self.library.append({
                'plant_id': plant_id,
                'notes': notes,
                'quantity': quantity,
                'plant': self.plants[plant_id],
                'date_added': '2024-03-15'
            })
            return True
        return False
    
    def get_library(self):
        return self.library
    
    def get_stats(self):
        total = len(self.library)
        reminders = 0
        types = {}
        
        for item in self.library:
            plant_type = item['plant'].type_plante
            types[plant_type] = types.get(plant_type, 0) + item['quantity']
        
        return {
            'total': total,
            'reminders': reminders,
            'types': types,
            'total_plants': sum(item['quantity'] for item in self.library)
        }

# Instances globales
db = SimpleDatabase()
real_scraper = PromesseDeFleursScraper()
mock_scraper = MockScraper()

# Route pour servir le frontend
@app.route('/')
def index():
    return send_from_directory('static', 'index.html')

# Routes API
@app.route('/api/search', methods=['GET'])
def search():
    query = request.args.get('q', '')
    force_web = request.args.get('force_web', 'false').lower() == 'true'
    
    if not query:
        return jsonify({'error': 'Query parameter required'}), 400
    
    results = {
        'local': [],
        'web': [],
        'total_found': 0,
        'source': 'unknown'
    }
    
    # Recherche locale d'abord
    if not force_web:
        local_results = db.search_local(query)
        results['local'] = [asdict(p) for p in local_results]
        results['total_found'] = len(local_results)
        results['source'] = 'local'
    
    # Recherche web si pas assez de résultats
    if len(results['local']) < 3:
        print(f"\n🌐 Recherche web pour: {query}")
        
        # Essayer le vrai scraper
        web_results = real_scraper.search_plants(query, max_results=10)
        
        # Si échec, utiliser le mock
        if not web_results:
            print("⚠️ Scraper réel échoué, utilisation du mock")
            web_results = mock_scraper.search_plants(query, max_results=5)
            results['source'] = 'mock'
        else:
            results['source'] = 'promesse_de_fleurs'
        
        # Sauvegarder dans la BDD locale
        for plant in web_results:
            db.save_plant(plant)
        
        results['web'] = [asdict(p) for p in web_results]
        results['total_found'] += len(web_results)
    
    return jsonify(results)

@app.route('/api/library', methods=['GET'])
def get_library():
    library = db.get_library()
    library_data = []
    
    for item in library:
        plant_dict = asdict(item['plant'])
        library_data.append({
            'plant': plant_dict,
            'notes': item['notes'],
            'quantity': item['quantity'],
            'date_added': item['date_added']
        })
    
    return jsonify(library_data)

@app.route('/api/library/add', methods=['POST'])
def add_to_library():
    data = request.get_json()
    
    if not data or 'plant' not in data:
        return jsonify({'error': 'Plant data required'}), 400
    
    plant_data = data['plant']
    notes = data.get('notes', '')
    quantity = data.get('quantity', 1)
    
    plant = PlantInfo(**plant_data)
    plant_id = db.save_plant(plant)
    success = db.add_to_library(plant_id, notes, quantity)
    
    if success:
        return jsonify({'success': True, 'message': 'Plante ajoutée à la bibliothèque'})
    else:
        return jsonify({'error': 'Failed to add plant'}), 500

@app.route('/api/stats', methods=['GET'])
def get_stats():
    stats = db.get_stats()
    return jsonify(stats)

@app.route('/api/suggestions', methods=['GET'])
def get_suggestions():
    # Utiliser le vrai scraper pour les suggestions
    suggestions_queries = ["rose", "lavande", "olivier", "hortensia"]
    suggestions = []
    
    for query in suggestions_queries:
        results = real_scraper.search_plants(query, max_results=1)
        if results:
            suggestions.append(asdict(results[0]))
        else:
            # Fallback sur mock
            mock_results = mock_scraper.search_plants(query, max_results=1)
            if mock_results:
                suggestions.append(asdict(mock_results[0]))
    
    return jsonify(suggestions)

@app.route('/api/test-scraper', methods=['GET'])
def test_scraper():
    """Route de test pour vérifier le scraper"""
    query = request.args.get('q', 'lavande')
    
    results = real_scraper.search_plants(query, max_results=3)
    
    return jsonify({
        'query': query,
        'count': len(results),
        'results': [asdict(p) for p in results],
        'success': len(results) > 0
    })

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    print("🌿 SERVEUR DÉMARRÉ - Botanus v2.0 avec Scraper Réel")
    print("=" * 60)
    print(f"Port: {port}")
    print(f"Scraper: Promesse de Fleurs (avec fallback mock)")
    print("=" * 60)
    app.run(host='0.0.0.0', port=port, debug=False)
