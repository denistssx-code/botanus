"""
Scraper pour AuJardin.info - Extraction des données d'entretien complètes
(arrosage, fertilisation, taille, maladies, parasites, multiplication)
"""

import requests
from bs4 import BeautifulSoup
from typing import Optional, Dict, List
from urllib.parse import quote
import re
import time
from dataclasses import dataclass, field

@dataclass
class AuJardinPlantData:
    """Données complètes extraites d'AuJardin.info"""
    # Identification
    nom_francais: str = ""
    nom_latin: str = ""
    autres_noms: List[str] = field(default_factory=list)
    famille: str = ""
    url: str = ""
    
    # Dimensions
    hauteur: str = ""
    port: str = ""
    feuillage: str = ""
    
    # Floraison
    periode_floraison: str = ""
    couleur_fleurs: str = ""
    
    # Plantation
    exposition: str = ""
    rusticite: str = ""
    sol_type: str = ""
    sol_acidite: str = ""
    sol_humidite: str = ""
    utilisation: str = ""
    periode_plantation: str = ""
    
    # Entretien
    arrosage: str = ""
    arrosage_detail: str = ""
    
    fertilisation: str = ""
    fertilisation_detail: str = ""
    
    taille_periode: str = ""
    taille_technique: str = ""
    
    # Multiplication
    multiplication: str = ""
    multiplication_detail: str = ""
    
    # Maladies et ravageurs
    maladies: List[str] = field(default_factory=list)
    ravageurs: List[str] = field(default_factory=list)
    
    # Descriptions
    description: str = ""
    description_botanique: str = ""
    
    # Toxicité
    toxicite: str = ""
    
    # Variétés
    varietes: List[Dict] = field(default_factory=list)


class AuJardinScraper:
    """Scraper pour extraire les données depuis AuJardin.info"""
    
    def __init__(self):
        self.base_url = "https://www.aujardin.info"
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'fr-FR,fr;q=0.9,en;q=0.8',
        }
        self.session = requests.Session()
        self.session.headers.update(self.headers)
    
    def _clean_text(self, text: str) -> str:
        """Nettoie le texte extrait"""
        if not text:
            return ""
        # Enlever les sauts de ligne multiples et espaces superflus
        text = re.sub(r'\s+', ' ', text)
        return text.strip()
    
    def construct_url(self, nom_latin: str) -> str:
        """
        Construit l'URL depuis le nom latin
        Format: https://www.aujardin.info/plantes/genre_espece.php
        """
        # Nettoyer le nom latin (enlever variété/cultivar)
        parts = nom_latin.lower().split()
        if len(parts) >= 2:
            # Garder seulement genre + espèce
            genre_espece = f"{parts[0]}_{parts[1]}"
        else:
            genre_espece = parts[0]
        
        return f"{self.base_url}/plantes/{genre_espece}.php"
    
    def extract_plant_data(self, url: str) -> Optional[AuJardinPlantData]:
        """Extrait toutes les données d'une page AuJardin.info"""
        print(f"📥 Extraction AuJardin: {url}")
        
        try:
            time.sleep(1)  # Rate limiting respectueux
            
            response = self.session.get(url, timeout=15)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            data = AuJardinPlantData(url=url)
            
            # Titre (nom français)
            h1 = soup.find('h1')
            if h1:
                title = self._clean_text(h1.get_text())
                # Souvent format: "Nom français, Autre nom, Nom latin"
                if ',' in title:
                    parts = [p.strip() for p in title.split(',')]
                    data.nom_francais = parts[0]
                    data.autres_noms = parts[1:-1]  # Entre premier et dernier
                    data.nom_latin = parts[-1] if parts[-1] else ""
                else:
                    data.nom_francais = title
            
            # Nom scientifique (dans les métadonnées ou texte)
            nom_sci = soup.find('strong', text=re.compile('Nom scientifique'))
            if nom_sci:
                data.nom_latin = self._clean_text(nom_sci.parent.get_text().replace('Nom scientifique :', ''))
            
            # Famille
            famille = soup.find('strong', text=re.compile('Famille'))
            if famille:
                data.famille = self._clean_text(famille.parent.get_text().replace('Famille :', ''))
            
            # Description principale
            self._extract_description(soup, data)
            
            # Bloc "La plante en bref" (tableau résumé)
            self._extract_plant_summary(soup, data)
            
            # Sections détaillées
            self._extract_plantation_section(soup, data)
            self._extract_entretien_section(soup, data)
            
            # Variétés intéressantes
            self._extract_varietes(soup, data)
            
            print(f"  ✅ Extraction réussie")
            print(f"     - Arrosage: {'Oui' if data.arrosage else 'Non'}")
            print(f"     - Taille: {'Oui' if data.taille_periode else 'Non'}")
            print(f"     - Multiplication: {'Oui' if data.multiplication else 'Non'}")
            
            return data
            
        except Exception as e:
            print(f"  ❌ Erreur extraction: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def _extract_description(self, soup: BeautifulSoup, data: AuJardinPlantData):
        """Extrait les descriptions"""
        # Description principale (premier paragraphe après h1)
        h1 = soup.find('h1')
        if h1:
            next_p = h1.find_next('p')
            if next_p:
                data.description = self._clean_text(next_p.get_text())
    
    def _extract_plant_summary(self, soup: BeautifulSoup, data: AuJardinPlantData):
        """
        Extrait le bloc 'La plante en bref' qui contient un tableau structuré
        avec exposition, rusticité, sol, etc.
        """
        # Chercher les sections avec des labels spécifiques
        labels_mapping = {
            'Exposition': 'exposition',
            'Rusticité': 'rusticite',
            'Sol': 'sol_type',
            'Acidité': 'sol_acidite',
            'Humidité': 'sol_humidite',
            'Utilisation': 'utilisation',
            'Hauteur': 'hauteur',
            'Type': 'port',
            'Feuillage': 'feuillage',
            'Période favorable': 'periode_plantation',
            'Toxicité': 'toxicite',
            'Arrosage': 'arrosage',
        }
        
        for label, attr in labels_mapping.items():
            # Chercher le label
            label_elem = soup.find(text=re.compile(f'^{label}\\s*$', re.IGNORECASE))
            if label_elem:
                # Le parent contient généralement le label, et le next sibling la valeur
                parent = label_elem.find_parent(['dt', 'div', 'strong', 'th'])
                if parent:
                    # Chercher la valeur (souvent dans dd, next div, next td, etc.)
                    value_elem = parent.find_next_sibling(['dd', 'td', 'div'])
                    if value_elem:
                        value = self._clean_text(value_elem.get_text())
                        setattr(data, attr, value)
    
    def _extract_plantation_section(self, soup: BeautifulSoup, data: AuJardinPlantData):
        """Extrait les informations de la section Plantation"""
        # Chercher le titre de section
        section_title = soup.find(['h2', 'h3'], text=re.compile('Plantation', re.IGNORECASE))
        
        if not section_title:
            return
        
        # Trouver tout le contenu jusqu'à la prochaine section
        section_content = []
        for sibling in section_title.find_next_siblings():
            if sibling.name in ['h2', 'h3']:
                break  # Prochaine section
            section_content.append(sibling)
        
        # Extraire le texte complet
        full_text = ' '.join([self._clean_text(elem.get_text()) for elem in section_content])
        
        # Parser des infos spécifiques depuis le texte
        if 'exposition' not in data.exposition or not data.exposition:
            if 'soleil' in full_text.lower():
                if 'plein soleil' in full_text.lower():
                    data.exposition = 'Plein soleil'
                elif 'mi-ombre' in full_text.lower():
                    data.exposition = 'Mi-ombre'
        
        # Stocker le texte complet dans periode_plantation si vide
        if not data.periode_plantation and section_content:
            data.periode_plantation = full_text[:500]  # Premiers 500 caractères
    
    def _extract_entretien_section(self, soup: BeautifulSoup, data: AuJardinPlantData):
        """Extrait les informations de la section Entretien & Multiplication"""
        # Chercher le titre de section
        section_title = soup.find(['h2', 'h3'], text=re.compile('Entretien|Multiplication', re.IGNORECASE))
        
        if not section_title:
            return
        
        # Trouver tout le contenu jusqu'à la prochaine section
        section_content = []
        for sibling in section_title.find_next_siblings():
            if sibling.name in ['h2', 'h3']:
                break
            section_content.append(sibling)
        
        # Chercher des sous-sections spécifiques
        for elem in section_content:
            text = self._clean_text(elem.get_text())
            text_lower = text.lower()
            
            # Arrosage
            if any(keyword in text_lower for keyword in ['arrosage', 'arroser', 'eau']):
                if not data.arrosage_detail:
                    data.arrosage_detail = text
            
            # Fertilisation
            if any(keyword in text_lower for keyword in ['fertilisation', 'engrais', 'fertiliser', 'apport']):
                if not data.fertilisation_detail:
                    data.fertilisation_detail = text
            
            # Taille
            if any(keyword in text_lower for keyword in ['taille', 'tailler', 'rabattre']):
                if not data.taille_technique:
                    data.taille_technique = text
                # Extraire la période si possible
                mois = re.findall(r'(janvier|février|mars|avril|mai|juin|juillet|août|septembre|octobre|novembre|décembre)', text_lower, re.IGNORECASE)
                if mois and not data.taille_periode:
                    data.taille_periode = ', '.join(mois).capitalize()
            
            # Multiplication
            if any(keyword in text_lower for keyword in ['multiplication', 'semis', 'bouturage', 'division']):
                if not data.multiplication_detail:
                    # Nettoyer le texte : enlever le titre "Multiplication" au début
                    cleaned_text = re.sub(r'^Multiplication\s*:?\s*', '', text, flags=re.IGNORECASE).strip()
                    data.multiplication_detail = cleaned_text
                # Extraire les méthodes
                methodes = []
                if 'semis' in text_lower:
                    methodes.append('Semis')
                if 'bouturage' in text_lower:
                    methodes.append('Bouturage')
                if 'division' in text_lower:
                    methodes.append('Division')
                if 'marcottage' in text_lower:
                    methodes.append('Marcottage')
                if methodes and not data.multiplication:
                    data.multiplication = ', '.join(methodes)
            
            # Maladies et ravageurs
            if any(keyword in text_lower for keyword in ['maladie', 'ravageur', 'parasite']):
                # Chercher des noms spécifiques
                maladies_courantes = ['oïdium', 'mildiou', 'rouille', 'botrytis', 'septoriose', 'tavelure']
                for maladie in maladies_courantes:
                    if maladie in text_lower and maladie not in [m.lower() for m in data.maladies]:
                        data.maladies.append(maladie.capitalize())
                
                ravageurs_courants = ['puceron', 'cochenille', 'araignée rouge', 'thrips', 'aleurode', 'chenille']
                for ravageur in ravageurs_courants:
                    if ravageur in text_lower and ravageur not in [r.lower() for r in data.ravageurs]:
                        data.ravageurs.append(ravageur.capitalize())
    
    def _extract_varietes(self, soup: BeautifulSoup, data: AuJardinPlantData):
        """Extrait les variétés intéressantes"""
        # Chercher la section variétés
        varietes_section = soup.find(['h2', 'h3'], text=re.compile('Espèces.*variétés|Variétés', re.IGNORECASE))
        
        if not varietes_section:
            return
        
        # Trouver les items de liste
        liste = varietes_section.find_next(['ul', 'dl'])
        if liste:
            items = liste.find_all(['li', 'dt'])
            for item in items[:10]:  # Max 10 variétés
                text = self._clean_text(item.get_text())
                if text:
                    # Parser format: "Nom variété : description"
                    if ':' in text:
                        nom, desc = text.split(':', 1)
                        data.varietes.append({
                            'nom': nom.strip(),
                            'description': desc.strip()
                        })
                    else:
                        data.varietes.append({
                            'nom': text,
                            'description': ''
                        })
    
    def get_plant_data(self, nom_latin: str) -> Optional[AuJardinPlantData]:
        """
        Méthode principale: construit l'URL et extrait les données d'une plante
        """
        # Construire l'URL
        url = self.construct_url(nom_latin)
        
        print(f"🔍 URL AuJardin: {url}")
        
        # Extraire les données
        return self.extract_plant_data(url)
    
    def scrape_url_direct(self, url: str) -> Optional[AuJardinPlantData]:
        """
        Scrape directement une URL fournie (pour scraping manuel)
        """
        print(f"🔍 Scraping URL directe: {url}")
        
        # Extraire les données
        return self.extract_plant_data(url)


# Instance globale
aujardin_scraper = AuJardinScraper()


if __name__ == "__main__":
    # Tests
    print("=== Test scraper AuJardin.info ===\n")
    
    scraper = AuJardinScraper()
    
    # Test avec Lilas des Indes
    data = scraper.get_plant_data("Lagerstroemia indica")
    
    if data:
        print("\n📊 Résultats:")
        print(f"Nom: {data.nom_francais}")
        print(f"Latin: {data.nom_latin}")
        print(f"Famille: {data.famille}")
        print(f"Exposition: {data.exposition}")
        print(f"Rusticité: {data.rusticite}")
        print(f"Arrosage: {data.arrosage}")
        print(f"Taille période: {data.taille_periode}")
        print(f"Multiplication: {data.multiplication}")
        print(f"Maladies ({len(data.maladies)}): {data.maladies}")
        print(f"Ravageurs ({len(data.ravageurs)}): {data.ravageurs}")
        print(f"Variétés ({len(data.varietes)}): {[v['nom'] for v in data.varietes[:3]]}")
    else:
        print("❌ Aucune donnée extraite")
