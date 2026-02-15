from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
from dataclasses import dataclass, asdict
from typing import List, Dict
import json
import os

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

class MockScraper:
    """Version simulée pour tester la logique sans requêtes réseau"""
    
    def __init__(self):
        self.mock_data = {
            "lavande": [
                {
                    "nom_francais": "Lavande vraie",
                    "nom_latin": "Lavandula angustifolia",
                    "exposition": "Plein soleil",
                    "type_plante": "Vivace",
                    "prix": "8,90 €",
                    "description": "Lavande officinale aux fleurs parfumées, résistante à la sécheresse",
                    "icon": "🌿"
                },
                {
                    "nom_francais": "Lavande papillon",
                    "nom_latin": "Lavandula stoechas",
                    "exposition": "Plein soleil",
                    "type_plante": "Vivace",
                    "prix": "9,50 €",
                    "description": "Lavande ornementale aux bractées colorées",
                    "icon": "🌿"
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
                    "icon": "🌹"
                },
                {
                    "nom_francais": "Rose de Damas",
                    "nom_latin": "Rosa damascena",
                    "exposition": "Soleil",
                    "type_plante": "Rosier",
                    "prix": "22,90 €",
                    "description": "Rose ancienne très parfumée",
                    "icon": "🌹"
                }
            ],
            "hortensia": [
                {
                    "nom_francais": "Hortensia macrophylla",
                    "nom_latin": "Hydrangea macrophylla",
                    "exposition": "Mi-ombre",
                    "type_plante": "Arbuste",
                    "prix": "18,90 €",
                    "description": "Arbuste à fleurs changeant de couleur selon le pH",
                    "icon": "🌺"
                }
            ],
            "olivier": [
                {
                    "nom_francais": "Olivier européen",
                    "nom_latin": "Olea europaea",
                    "exposition": "Plein soleil",
                    "type_plante": "Arbre",
                    "prix": "45,90 €",
                    "description": "Arbre méditerranéen produisant des olives",
                    "icon": "🌳"
                }
            ],
            "érable": [
                {
                    "nom_francais": "Érable japonais",
                    "nom_latin": "Acer palmatum",
                    "exposition": "Mi-ombre",
                    "type_plante": "Arbre",
                    "prix": "39,90 €",
                    "description": "Petit arbre ornemental au feuillage décoratif",
                    "icon": "🌳"
                }
            ],
            "cerisier": [
                {
                    "nom_francais": "Cerisier du Japon",
                    "nom_latin": "Prunus serrulata",
                    "exposition": "Soleil",
                    "type_plante": "Arbre",
                    "prix": "42,90 €",
                    "description": "Arbre à floraison printanière spectaculaire",
                    "icon": "🌸"
                }
            ],
            "graminée": [
                {
                    "nom_francais": "Graminée ornementale",
                    "nom_latin": "Miscanthus sinensis",
                    "exposition": "Soleil",
                    "type_plante": "Vivace",
                    "prix": "12,90 €",
                    "description": "Graminée décorative aux inflorescences plumeuses",
                    "icon": "🌾"
                }
            ],
            "tomate": [
                {
                    "nom_francais": "Tomate coeur de boeuf",
                    "nom_latin": "Solanum lycopersicum",
                    "exposition": "Plein soleil",
                    "type_plante": "Annuelle",
                    "prix": "3,50 €",
                    "description": "Tomate charnue et savoureuse",
                    "icon": "🍅"
                }
            ],
            "basilic": [
                {
                    "nom_francais": "Basilic grand vert",
                    "nom_latin": "Ocimum basilicum",
                    "exposition": "Soleil",
                    "type_plante": "Annuelle",
                    "prix": "2,90 €",
                    "description": "Plante aromatique incontournable",
                    "icon": "🌿"
                }
            ]
        }
    
    def search_plants(self, query: str, max_results: int = 10) -> List[PlantInfo]:
        """Simulation de recherche avec données mock"""
        results = []
        query_lower = query.lower()
        
        for key, plants_data in self.mock_data.items():
            if key in query_lower or any(word in key for word in query_lower.split()):
                for plant_data in plants_data[:max_results]:
                    plant = PlantInfo(**plant_data)
                    results.append(plant)
        
        if not results:
            for plants_data in self.mock_data.values():
                for plant_data in plants_data:
                    if any(word in plant_data["nom_francais"].lower() 
                          or word in plant_data["nom_latin"].lower()
                          for word in query_lower.split() if len(word) > 2):
                        plant = PlantInfo(**plant_data)
                        results.append(plant)
                        if len(results) >= max_results:
                            break
                if len(results) >= max_results:
                    break
        
        return results[:max_results]

class SimpleDatabase:
    """Base de données simulée en mémoire"""
    
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
            if (existing.nom_latin == plant.nom_latin and 
                existing.nom_francais == plant.nom_francais):
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
scraper = MockScraper()

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
        'total_found': 0
    }
    
    if not force_web:
        local_results = db.search_local(query)
        results['local'] = [asdict(p) for p in local_results]
        results['total_found'] = len(local_results)
    
    if len(results['local']) < 5:
        web_results = scraper.search_plants(query, max_results=10)
        
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
    suggestions = [
        scraper.search_plants("rose", max_results=1)[0] if scraper.search_plants("rose", max_results=1) else None,
        scraper.search_plants("lavande", max_results=1)[0] if scraper.search_plants("lavande", max_results=1) else None,
        scraper.search_plants("olivier", max_results=1)[0] if scraper.search_plants("olivier", max_results=1) else None,
        scraper.search_plants("hortensia", max_results=1)[0] if scraper.search_plants("hortensia", max_results=1) else None,
    ]
    
    suggestions = [asdict(s) for s in suggestions if s]
    return jsonify(suggestions)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    print("🌿 SERVEUR DÉMARRÉ")
    print("=" * 50)
    print(f"API disponible sur le port: {port}")
    print("=" * 50)
    app.run(host='0.0.0.0', port=port, debug=False)
