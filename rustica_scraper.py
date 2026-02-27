"""
Scraper pour Rustica.fr - Extraction des données d'entretien des plantes
(arrosage, fertilisation, maladies, parasites)
"""

import requests
from bs4 import BeautifulSoup
from typing import Optional, Dict, List
from urllib.parse import quote, urljoin
import re
import time
from dataclasses import dataclass, asdict

@dataclass
class RusticaPlantData:
    """Données d'entretien extraites de Rustica"""
    # Identification
    nom_francais: str = ""
    nom_latin: str = ""
    url: str = ""
    
    # Arrosage
    arrosage_frequence: str = ""
    arrosage_besoins: str = ""
    arrosage_conseils: str = ""
    
    # Fertilisation
    fertilisation_periode: str = ""
    fertilisation_type: str = ""
    fertilisation_frequence: str = ""
    
    # Maladies
    maladies: List[Dict] = None
    
    # Parasites
    parasites: List[Dict] = None
    
    # Multiplication
    multiplication_methodes: List[str] = None
    multiplication_periode: str = ""
    
    # Division (vivaces)
    division_frequence: str = ""
    division_periode: str = ""
    
    # Autres entretiens
    paillage: str = ""
    tuteurage: str = ""
    rabattage_periode: str = ""
    
    def __post_init__(self):
        if self.maladies is None:
            self.maladies = []
        if self.parasites is None:
            self.parasites = []
        if self.multiplication_methodes is None:
            self.multiplication_methodes = []


class RusticaScraper:
    """Scraper pour extraire les données d'entretien depuis Rustica.fr"""
    
    def __init__(self):
        self.base_url = "https://www.rustica.fr"
        self.headers = {
            'User-Agent': 'Ma Bibliothèque Végétale - Bot d\'agrégation de données botaniques',
            'Accept': 'text/html,application/xhtml+xml',
            'Accept-Language': 'fr-FR,fr;q=0.9',
        }
        self.session = requests.Session()
        self.session.headers.update(self.headers)
    
    def _clean_text(self, text: str) -> str:
        """Nettoie le texte extrait"""
        if not text:
            return ""
        return ' '.join(text.strip().split())
    
    def search_plant(self, nom_latin: str) -> Optional[str]:
        """
        Recherche une plante sur Rustica par son nom latin
        Retourne l'URL de la fiche si trouvée
        """
        print(f"🔍 Recherche Rustica: {nom_latin}")
        
        try:
            # URL de recherche
            search_url = f"{self.base_url}/recherche"
            params = {'q': nom_latin}
            
            response = self.session.get(search_url, params=params, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Chercher les résultats de recherche
            # Structure peut varier, chercher plusieurs patterns
            result_links = []
            
            # Pattern 1: Articles de plantes
            articles = soup.find_all('article', class_=re.compile('plant|result'))
            for article in articles:
                link = article.find('a', href=re.compile(r'/plantes?[/-]'))
                if link:
                    result_links.append(link)
            
            # Pattern 2: Liens directs vers plantes
            if not result_links:
                result_links = soup.find_all('a', href=re.compile(r'/plantes?[/-]'))
            
            # Vérifier chaque résultat
            nom_latin_lower = nom_latin.lower()
            for link in result_links:
                href = link.get('href', '')
                text = self._clean_text(link.get_text()).lower()
                
                # Vérifier que le nom latin est dans le texte ou l'URL
                if nom_latin_lower in text or nom_latin_lower.replace(' ', '-') in href:
                    url = urljoin(self.base_url, href)
                    print(f"  ✅ Trouvé: {url}")
                    return url
            
            print(f"  ❌ Pas trouvé sur Rustica")
            return None
            
        except Exception as e:
            print(f"  ❌ Erreur recherche: {e}")
            return None
    
    def extract_plant_data(self, url: str) -> Optional[RusticaPlantData]:
        """Extrait toutes les données d'entretien d'une page Rustica"""
        print(f"📥 Extraction Rustica: {url}")
        
        try:
            time.sleep(2)  # Rate limiting respectueux
            
            response = self.session.get(url, timeout=15)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            data = RusticaPlantData(url=url)
            
            # Titre et nom latin
            h1 = soup.find('h1')
            if h1:
                data.nom_francais = self._clean_text(h1.get_text())
            
            # Nom latin (souvent dans un span ou paragraphe italic)
            latin = soup.find(['span', 'p', 'em'], class_=re.compile('latin|italic|scientific'))
            if latin:
                data.nom_latin = self._clean_text(latin.get_text())
            
            # Chercher les sections d'entretien
            self._extract_arrosage(soup, data)
            self._extract_fertilisation(soup, data)
            self._extract_maladies(soup, data)
            self._extract_parasites(soup, data)
            self._extract_multiplication(soup, data)
            
            print(f"  ✅ Extraction réussie")
            print(f"     - Arrosage: {'Oui' if data.arrosage_frequence else 'Non'}")
            print(f"     - Fertilisation: {'Oui' if data.fertilisation_periode else 'Non'}")
            print(f"     - Maladies: {len(data.maladies)}")
            print(f"     - Parasites: {len(data.parasites)}")
            
            return data
            
        except Exception as e:
            print(f"  ❌ Erreur extraction: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def _extract_arrosage(self, soup: BeautifulSoup, data: RusticaPlantData):
        """Extrait les informations d'arrosage"""
        # Chercher section arrosage
        keywords = ['arrosage', 'eau', 'irrigation', 'besoins en eau']
        
        for keyword in keywords:
            section = soup.find(text=re.compile(keyword, re.IGNORECASE))
            if section:
                # Remonter au parent pour trouver le contenu
                parent = section.find_parent(['div', 'section', 'p', 'li'])
                if parent:
                    text = self._clean_text(parent.get_text())
                    
                    # Parser le texte pour extraire fréquence et besoins
                    if 'modéré' in text.lower() or 'régulier' in text.lower():
                        data.arrosage_frequence = 'Modéré'
                    elif 'abondant' in text.lower() or 'copieux' in text.lower():
                        data.arrosage_frequence = 'Abondant'
                    elif 'faible' in text.lower() or 'peu' in text.lower():
                        data.arrosage_frequence = 'Faible'
                    
                    data.arrosage_conseils = text[:200]  # Premiers 200 caractères
                    break
    
    def _extract_fertilisation(self, soup: BeautifulSoup, data: RusticaPlantData):
        """Extrait les informations de fertilisation"""
        keywords = ['fertilisation', 'engrais', 'fertiliser', 'apport', 'amendement']
        
        for keyword in keywords:
            section = soup.find(text=re.compile(keyword, re.IGNORECASE))
            if section:
                parent = section.find_parent(['div', 'section', 'p', 'li'])
                if parent:
                    text = self._clean_text(parent.get_text())
                    
                    # Extraire période
                    mois = ['janvier', 'février', 'mars', 'avril', 'mai', 'juin',
                            'juillet', 'août', 'septembre', 'octobre', 'novembre', 'décembre',
                            'printemps', 'été', 'automne', 'hiver']
                    
                    for mois_nom in mois:
                        if mois_nom in text.lower():
                            data.fertilisation_periode = mois_nom.capitalize()
                            break
                    
                    # Type d'engrais
                    if 'organique' in text.lower():
                        data.fertilisation_type = 'Organique'
                    elif 'compost' in text.lower():
                        data.fertilisation_type = 'Compost'
                    elif 'fumier' in text.lower():
                        data.fertilisation_type = 'Fumier'
                    
                    break
    
    def _extract_maladies(self, soup: BeautifulSoup, data: RusticaPlantData):
        """Extrait les maladies et traitements"""
        keywords = ['maladie', 'maladies', 'pathologie', 'infection']
        
        for keyword in keywords:
            section = soup.find(text=re.compile(keyword, re.IGNORECASE))
            if section:
                parent = section.find_parent(['div', 'section', 'ul'])
                if parent:
                    # Chercher liste de maladies
                    items = parent.find_all('li')
                    for item in items:
                        text = self._clean_text(item.get_text())
                        if len(text) > 5:  # Éviter items vides
                            # Parser nom maladie et traitement
                            parts = text.split(':', 1)
                            if len(parts) == 2:
                                data.maladies.append({
                                    'nom': self._clean_text(parts[0]),
                                    'traitement': self._clean_text(parts[1])
                                })
                            else:
                                data.maladies.append({
                                    'nom': text,
                                    'traitement': ''
                                })
                    
                    if data.maladies:
                        break
    
    def _extract_parasites(self, soup: BeautifulSoup, data: RusticaPlantData):
        """Extrait les parasites et traitements"""
        keywords = ['parasite', 'insecte', 'ravageur', 'puceron', 'cochenille']
        
        for keyword in keywords:
            section = soup.find(text=re.compile(keyword, re.IGNORECASE))
            if section:
                parent = section.find_parent(['div', 'section', 'ul'])
                if parent:
                    items = parent.find_all('li')
                    for item in items:
                        text = self._clean_text(item.get_text())
                        if len(text) > 5:
                            parts = text.split(':', 1)
                            if len(parts) == 2:
                                data.parasites.append({
                                    'nom': self._clean_text(parts[0]),
                                    'traitement': self._clean_text(parts[1])
                                })
                            else:
                                data.parasites.append({
                                    'nom': text,
                                    'traitement': ''
                                })
                    
                    if data.parasites:
                        break
    
    def _extract_multiplication(self, soup: BeautifulSoup, data: RusticaPlantData):
        """Extrait les méthodes de multiplication"""
        keywords = ['multiplication', 'bouturage', 'semis', 'division', 'marcottage']
        
        for keyword in keywords:
            section = soup.find(text=re.compile(keyword, re.IGNORECASE))
            if section:
                parent = section.find_parent(['div', 'section', 'p'])
                if parent:
                    text = self._clean_text(parent.get_text()).lower()
                    
                    if 'bouturage' in text:
                        data.multiplication_methodes.append('Bouturage')
                    if 'semis' in text:
                        data.multiplication_methodes.append('Semis')
                    if 'division' in text:
                        data.multiplication_methodes.append('Division')
                        # Si division, extraire période
                        if 'printemps' in text:
                            data.division_periode = 'Printemps'
                        elif 'automne' in text:
                            data.division_periode = 'Automne'
                    if 'marcottage' in text:
                        data.multiplication_methodes.append('Marcottage')
                    
                    break
    
    def get_plant_data(self, nom_latin: str) -> Optional[RusticaPlantData]:
        """
        Méthode principale: recherche et extrait les données d'une plante
        """
        # Rechercher la plante
        url = self.search_plant(nom_latin)
        
        if not url:
            return None
        
        # Extraire les données
        return self.extract_plant_data(url)


# Instance globale
rustica_scraper = RusticaScraper()


if __name__ == "__main__":
    # Tests
    print("=== Test scraper Rustica ===\n")
    
    scraper = RusticaScraper()
    
    # Test avec Lavande
    data = scraper.get_plant_data("Lavandula angustifolia")
    
    if data:
        print("\n📊 Résultats:")
        print(f"Nom: {data.nom_francais}")
        print(f"Latin: {data.nom_latin}")
        print(f"Arrosage: {data.arrosage_frequence} - {data.arrosage_conseils[:50]}...")
        print(f"Fertilisation: {data.fertilisation_periode} - {data.fertilisation_type}")
        print(f"Maladies ({len(data.maladies)}): {[m['nom'] for m in data.maladies[:3]]}")
        print(f"Parasites ({len(data.parasites)}): {[p['nom'] for p in data.parasites[:3]]}")
    else:
        print("❌ Aucune donnée extraite")
