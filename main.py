from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
from dataclasses import dataclass, asdict
from typing import List, Dict, Optional
from datetime import datetime
import json
import os
import requests
from bs4 import BeautifulSoup
import re

# Imports des modules d'agrégation de données
try:
    from plant_matcher import plant_matcher
    from rustica_scraper import rustica_scraper
    from aujardin_scraper import aujardin_scraper
    ENRICHMENT_ENABLED = True
    print("✅ Modules d'enrichissement chargés")
except ImportError as e:
    print(f"⚠️ Modules d'enrichissement non disponibles: {e}")
    ENRICHMENT_ENABLED = False
    aujardin_scraper = None

# Import du client Airtable
try:
    from airtable_client import airtable_client
    AIRTABLE_ENABLED = airtable_client.enabled
    if AIRTABLE_ENABLED:
        print("✅ Airtable activé")
except ImportError as e:
    print(f"⚠️ Airtable non disponible: {e}")
    AIRTABLE_ENABLED = False
    airtable_client = None

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

@dataclass
class PlantDetailInfo:
    """Structure complète pour les détails d'une plante"""
    # Identification
    nom_complet: str = ""
    nom_latin: str = ""
    nom_francais: str = ""
    genre: str = ""
    espece: str = ""
    cultivar: str = ""
    famille: str = ""
    origine: str = ""
    autres_noms: str = ""
    
    # Catégorisation (depuis breadcrumb)
    type_plante: str = ""
    sous_categorie: str = ""
    
    # Descriptions
    description_courte: str = ""
    description_detaillee: str = ""
    
    # Caractéristiques visuelles
    exposition: str = ""
    rusticite: str = ""
    zone_usda: str = ""
    humidite_sol: str = ""
    
    # Dimensions
    hauteur_maturite: str = ""
    largeur_maturite: str = ""
    taille_fleur: str = ""
    port: str = ""
    croissance: str = ""
    
    # Floraison
    couleur_fleur: str = ""
    periode_floraison: str = ""
    inflorescence: str = ""
    
    # Récolte (pour fruitiers)
    periode_recolte: str = ""
    
    # Feuillage
    persistance_feuillage: str = ""
    couleur_feuillage: str = ""
    
    # Plantation
    meilleure_periode_plantation: str = ""
    periode_raisonnable_plantation: str = ""
    calendrier_plantation: Dict[str, str] = None
    calendrier_floraison: Dict[str, str] = None
    
    # Culture
    convient_pour: str = ""
    type_utilisation: str = ""
    climat_preference: str = ""
    difficulte_culture: str = ""
    ph_sol: str = ""
    type_sol: str = ""
    
    # Entretien
    taille: str = ""
    resistance_maladies: str = ""
    hivernage: str = ""
    
    # Entretien détaillé (NOUVEAU)
    descriptif_taille_detaille: str = ""
    periode_taille: str = ""
    frequence_taille: str = ""
    densite_plantation: str = ""
    arrosage_conseils: str = ""
    produits_associes: List[Dict] = None
    
    # Formats disponibles
    formats: List[Dict] = None
    
    # Images
    image_principale: str = ""
    images_galerie: List[str] = None
    
    def __post_init__(self):
        if self.calendrier_plantation is None:
            self.calendrier_plantation = {}
        if self.calendrier_floraison is None:
            self.calendrier_floraison = {}
        if self.formats is None:
            self.formats = []
        if self.images_galerie is None:
            self.images_galerie = []

class PromesseDeFleursScraper:
    """Scraper enrichi pour Promesse de Fleurs"""
    
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
            'magnolia': '🌸',
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
        """Devine le type de plante depuis le nom et description"""
        text = (name + " " + description).lower()
        
        # Ordre d'importance (du plus spécifique au plus général)
        
        # Plantes grasses et succulentes
        if any(word in text for word in ['succulente', 'cactus', 'crassula', 'echeveria', 'sedum', 'aloe', 'agave']):
            return "Succulente"
        
        # Rosiers (très spécifique)
        if any(word in text for word in ['rosier', 'rose ']):
            return "Rosier"
        
        # Plantes aromatiques et potager
        if any(word in text for word in ['aromatique', 'basilic', 'thym', 'romarin', 'persil', 'menthe', 'sauge', 'ciboulette', 'origan']):
            return "Aromatique"
        
        if any(word in text for word in ['potager', 'tomate', 'courgette', 'aubergine', 'poivron', 'salade', 'légume']):
            return "Potager"
        
        # Bulbes et tubercules
        if any(word in text for word in ['bulbe', 'tulipe', 'narcisse', 'jacinthe', 'dahlia', 'glaïeul', 'crocus']):
            return "Bulbe"
        
        # Grimpantes
        if any(word in text for word in ['grimpant', 'clématite', 'glycine', 'vigne', 'lierre', 'chèvrefeuille', 'jasmin grimpant']):
            return "Grimpante"
        
        # Arbres (avant arbustes car certains arbustes contiennent "arbre")
        if any(word in text for word in ['arbre ', 'érable', 'chêne', 'bouleau', 'tilleul', 'fruitier', 'pommier', 'cerisier', 'prunier']):
            return "Arbre"
        
        # Arbustes
        if any(word in text for word in ['arbuste', 'hortensia', 'buddleia', 'magnolia', 'forsythia', 'weigela', 'spirée', 'lilas']):
            return "Arbuste"
        
        # Vivaces
        if any(word in text for word in ['vivace', 'lavande', 'hémérocalle', 'géranium vivace', 'campanule', 'hosta', 'astilbe', 'rudbeckia']):
            return "Vivace"
        
        # Graminées
        if any(word in text for word in ['graminée', 'miscanthus', 'stipa', 'pennisetum', 'festuca', 'carex', 'bambou']):
            return "Graminée"
        
        # Annuelles et bisannuelles
        if any(word in text for word in ['annuelle', 'bisannuelle', 'pétunia', 'géranium ', 'impatiens', 'bégonia']):
            return "Annuelle"
        
        # Plantes d'intérieur
        if any(word in text for word in ['intérieur', 'plante d\'intérieur', 'ficus', 'monstera', 'pothos', 'philodendron']):
            return "Intérieur"
        
        # Aquatiques
        if any(word in text for word in ['aquatique', 'nénuphar', 'iris d\'eau', 'papyrus']):
            return "Aquatique"
        
        # Fougères
        if any(word in text for word in ['fougère', 'polystichum', 'dryopteris']):
            return "Fougère"
        
        # Par défaut
        return "Plante"
    
    def fetch_plant_detail(self, url: str) -> Optional[PlantDetailInfo]:
        """
        Extrait TOUTES les informations détaillées d'une page produit
        """
        print(f"🔍 Extraction détails: {url}")
        
        try:
            # Faire la requête
            response = requests.get(url, headers=self.headers, timeout=15)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            detail = PlantDetailInfo()
            
            # 1. TITRE PRINCIPAL
            h1 = soup.find('h1')
            if h1:
                detail.nom_complet = self.clean_text(h1.get_text())
            
            # 2. NOM LATIN & FRANÇAIS
            h2 = soup.find('h2', class_='italic')
            if h2:
                parts = h2.get_text(separator='|', strip=True).split('|')
                if len(parts) >= 1:
                    detail.nom_latin = parts[0].strip()
                if len(parts) >= 2:
                    detail.nom_francais = parts[1].strip()
            
            # 2.5. TYPE DE PLANTE - Extraction depuis l'URL
            # URL format: https://www.promessedefleurs.com/VIVACES/vivaces-par-variete/...
            #                                              ^^^^^^^ = type_plante
            print("  📂 Extraction type de plante depuis URL...")
            url_parts = url.split('/')
            if len(url_parts) > 3:
                type_from_url = url_parts[3].lower()  # Premier segment après le domaine
                
                # Mapping pour normaliser les types
                type_mapping = {
                    'arbustes': 'Arbuste',
                    'arbuste': 'Arbuste',
                    'arbres': 'Arbre',
                    'arbre': 'Arbre',
                    'vivaces': 'Vivace',
                    'vivace': 'Vivace',
                    'grimpantes': 'Grimpante',
                    'grimpante': 'Grimpante',
                    'annuelles': 'Annuelle',
                    'annuelle': 'Annuelle',
                    'bulbes': 'Bulbe',
                    'bulbe': 'Bulbe',
                    'rosiers': 'Rosier',
                    'rosier': 'Rosier',
                    'graminees': 'Graminée',
                    'graminee': 'Graminée',
                    'plantes-potageres': 'Plante potagère',
                    'plantes-aromatiques': 'Plante aromatique',
                    'fruitiers': 'Fruitier'
                }
                
                detail.type_plante = type_mapping.get(type_from_url, type_from_url.capitalize())
                print(f"  ✅ Type extrait depuis URL: {type_from_url} → {detail.type_plante}")
            else:
                detail.type_plante = 'Non défini'
                print(f"  ⚠️ Impossible d'extraire le type depuis l'URL")
            
            # Breadcrumb: extraire seulement la sous-catégorie (optionnel)
            breadcrumb = soup.find('ol', class_='items')
            if breadcrumb:
                all_items = breadcrumb.find_all('li', class_='item')
                # Filtrer les items (ignorer "home")
                items = [item for item in all_items if 'home' not in item.get('class', [])]
                
                # Extraire la sous-catégorie (généralement le 3ème élément)
                # Format breadcrumb: [0]=Type, [1]="par variété", [2]=Sous-catégorie (ex: "Agapanthes")
                if len(items) >= 3:
                    subcat_item = items[2]
                    subcat_link = subcat_item.find('a')
                    if subcat_link:
                        subcat_text = self.clean_text(subcat_link.get_text())
                        detail.sous_categorie = subcat_text
                        print(f"  📂 Sous-catégorie: {subcat_text}")
            
            # 3. DESCRIPTION COURTE
            desc_short = soup.find('div', class_='product-description')
            if desc_short:
                detail.description_courte = self.clean_text(desc_short.get_text())
            
            # 4. DESCRIPTION DÉTAILLÉE (entretien - sous "Plantations et soins")
            # Chercher le h2 "Plantations et soins" puis le div.prose qui suit
            h2_plantation = soup.find('h2', string=re.compile(r'Plantations et soins', re.IGNORECASE))
            if h2_plantation:
                # Chercher le div.prose.max-w-max qui suit ce h2
                prose_div = h2_plantation.find_next('div', class_='prose')
                if prose_div:
                    detail.description_detaillee = self.clean_text(prose_div.get_text())
                    print(f"✅ Description entretien trouvée: {len(detail.description_detaillee)} caractères")
            else:
                # Fallback: chercher n'importe quel div.prose.max-w-max
                desc_long = soup.find('div', class_='prose max-w-max')
                if desc_long and 'product-description' not in desc_long.get('class', []):
                    detail.description_detaillee = self.clean_text(desc_long.get_text())
                    print(f"⚠️ Description fallback: {len(detail.description_detaillee)} caractères")
            
            # 5. ATTRIBUTS VISUELS
            visual_attrs = soup.find('div', class_='visual-attributes')
            if visual_attrs:
                for attr_div in visual_attrs.find_all('div', attrs={'data-attribute': True}):
                    attr_name = attr_div.get('data-attribute')
                    attr_value = attr_div.find('span', class_='font-bold')
                    if attr_value:
                        value = self.clean_text(attr_value.get_text())
                        
                        if attr_name == 'exposition':
                            detail.exposition = value
                        elif attr_name == 'zone_climatique':
                            detail.rusticite = value
                            # Extraire zone USDA
                            usda_match = re.search(r'zone USDA (\d+)', value, re.IGNORECASE)
                            if usda_match:
                                detail.zone_usda = usda_match.group(1)
                        elif attr_name == 'hauteur':
                            detail.hauteur_maturite = value
                        elif attr_name == 'largeur':
                            detail.largeur_maturite = value
                        elif attr_name == 'taille_fleur':
                            detail.taille_fleur = value
                        elif attr_name == 'humidite_sol':
                            detail.humidite_sol = value
            
            # 6. SECTIONS DÉTAILLÉES (il peut y avoir plusieurs conteneurs)
            sections_containers = soup.find_all('div', class_='gap-y-8')
            print(f"📦 {len(sections_containers)} conteneurs de sections trouvés")
            
            for container_idx, sections_container in enumerate(sections_containers):
                print(f"\n📦 Conteneur {container_idx + 1}:")
                for section in sections_container.find_all('div', recursive=False):
                    title_elem = section.find('p', class_='font-bold')
                    if not title_elem:
                        continue
                    
                    section_title = self.clean_text(title_elem.get_text())
                    print(f"  📋 Section: {section_title}")
                    
                    # Extraire les paires label/valeur
                    rows = section.find_all('div', class_='flex-row')
                    for row in rows:
                        spans = row.find_all(['span', 'h2'])
                        if len(spans) >= 2:
                            label = self.clean_text(spans[0].get_text())
                            value = self.clean_text(spans[1].get_text())
                            print(f"    • {label}: {value[:50]}...")
                            
                            # VÉRIFICATION GLOBALE : Période de récolte (pour fruitiers)
                            # Chercher dans TOUTES les sections, pas seulement Floraison
                            if 'récolte' in label.lower() and 'période' in label.lower():
                                detail.periode_recolte = value
                                print(f"    ✅ Période de récolte trouvée: {value}")
                            
                            # Mapper selon la section
                            if section_title == 'Port':
                                if label == 'Port':
                                    detail.port = value
                                elif 'Croissance' in label:
                                    detail.croissance = value
                            
                            elif section_title == 'Floraison':
                                if 'couleur' in label.lower():
                                    detail.couleur_fleur = value
                                elif 'Période' in label and 'floraison' in label.lower():
                                    detail.periode_floraison = value
                                elif 'Inflorescence' in label:
                                    detail.inflorescence = value
                            
                            elif section_title == 'Feuillage':
                                if 'Persistance' in label:
                                    detail.persistance_feuillage = value
                                elif 'couleur' in label.lower():
                                    detail.couleur_feuillage = value
                            
                            elif section_title == 'Botanique':
                                if 'Genre' in label:
                                    detail.genre = value
                                elif 'Espèce' in label:
                                    detail.espece = value
                                elif 'Cultivar' in label:
                                    detail.cultivar = value
                                elif 'Famille' in label:
                                    detail.famille = value
                                elif 'Origine' in label:
                                    detail.origine = value
                                elif 'Autres noms' in label:
                                    detail.autres_noms = value
                            
                            elif section_title == 'Quand planter ?':
                                if 'Meilleure' in label:
                                    detail.meilleure_periode_plantation = value
                                elif 'raisonnable' in label:
                                    detail.periode_raisonnable_plantation = value
                            
                            elif section_title == 'Pour quel endroit ?':
                                if 'Convient' in label:
                                    detail.convient_pour = value
                                elif 'utilisation' in label.lower():
                                    detail.type_utilisation = value
                                elif 'Climat' in label:
                                    detail.climat_preference = value
                                elif 'Difficulté' in label:
                                    detail.difficulte_culture = value
                                elif 'pH' in label:
                                    detail.ph_sol = value
                                elif 'Type de sol' in label:
                                    detail.type_sol = value
                                elif 'Densité' in label:
                                    detail.densite_plantation = value
                            
                            elif section_title == 'Soins':
                                if label == 'Taille':
                                    detail.taille = value
                                    detail.frequence_taille = value  # "Taille conseillée 1 fois par an"
                                elif 'Descriptif taille' in label:
                                    detail.descriptif_taille_detaille = value
                                elif 'Période de taille' in label:
                                    detail.periode_taille = value
                                elif 'Résistance' in label:
                                    detail.resistance_maladies = value
                                elif 'Hivernage' in label:
                                    detail.hivernage = value
            
            # 7. FORMATS & PRIX
            formats = soup.find_all('div', class_='child-product')
            for fmt in formats:
                format_data = {}
                
                # Référence
                ref_text = fmt.find(string=re.compile(r'Réf:\s*\d+'))
                if ref_text:
                    ref_match = re.search(r'Réf:\s*(\d+)', ref_text)
                    if ref_match:
                        format_data['reference'] = ref_match.group(1)
                
                # Format & hauteur
                product_name = fmt.find('p', class_='product-item-name')
                if product_name:
                    full_text = product_name.get_text()
                    # Extraire format
                    format_match = re.search(r'Pot de [^(]+', full_text)
                    if format_match:
                        format_data['format'] = format_match.group(0).strip()
                    
                    # Extraire hauteur livraison
                    height_match = re.search(r'Hauteur livrée env\. (\d+/\d+cm)', full_text)
                    if height_match:
                        format_data['hauteur_livraison'] = height_match.group(1)
                
                # Prix unitaire
                price_elem = fmt.find('span', attrs={'data-price-amount': True})
                if price_elem:
                    price_str = price_elem.get('data-price-amount')
                    try:
                        format_data['prix_unitaire'] = float(price_str)
                    except:
                        pass
                
                # Prix par lot
                tier_prices = fmt.find('ul', class_='prices-tier')
                if tier_prices:
                    format_data['prix_par_lot'] = {}
                    for li in tier_prices.find_all('li'):
                        text = li.get_text()
                        lot_match = re.search(r'Les (\d+).*?(\d+,\d+)\s*€\s*l\'unité', text)
                        if lot_match:
                            qty = lot_match.group(1)
                            price = lot_match.group(2).replace(',', '.')
                            format_data['prix_par_lot'][qty] = float(price)
                
                # Stock
                stock_elem = fmt.find('div', class_='stock-status')
                if stock_elem:
                    stock_span = stock_elem.find('span')
                    if stock_span:
                        try:
                            format_data['stock'] = int(stock_span.get_text(strip=True))
                        except:
                            pass
                
                # Badges (production locale, etc.)
                badges_div = fmt.find('div', class_='product-logos')
                if badges_div:
                    badges = []
                    for img in badges_div.find_all('img'):
                        alt = img.get('alt', '')
                        if alt:
                            badges.append(alt)
                    if badges:
                        format_data['badges'] = badges
                
                detail.formats.append(format_data)
            
            # 8. PRODUITS ASSOCIÉS (section avec icône pelle)
            produits_section = soup.find('svg', attrs={'xlink:href': '#shovel-symbol'})
            if produits_section:
                produits_container = produits_section.find_parent('div', class_='border')
                if produits_container:
                    detail.produits_associes = []
                    products = produits_container.find_all('div', class_='product-item')
                    for product in products[:4]:  # Limiter à 4 produits
                        prod_data = {}
                        
                        # Nom
                        name_elem = product.find('a', class_='product-item-link')
                        if name_elem:
                            prod_data['nom'] = self.clean_text(name_elem.get_text())
                        
                        # Prix
                        price_elem = product.find('span', class_='price')
                        if price_elem:
                            prod_data['prix'] = self.clean_text(price_elem.get_text())
                        
                        # Stock
                        stock_elem = product.find('div', class_='stock-status')
                        if stock_elem:
                            stock_text = self.clean_text(stock_elem.get_text())
                            stock_match = re.search(r'(\d+)', stock_text)
                            if stock_match:
                                prod_data['stock'] = int(stock_match.group(1))
                        
                        if prod_data.get('nom'):
                            detail.produits_associes.append(prod_data)
            
            # 9. CONSEILS D'ARROSAGE depuis description détaillée
            # NOTE: Extraction désactivée car peu fiable - les infos sont dans description_detaillee
            # if detail.description_detaillee:
            #     arrosage_patterns = [
            #         r'arrosage.*?\.(?:\s|$)',
            #         r'eau.*?\.(?:\s|$)',
            #         r'irrigation.*?\.(?:\s|$)'
            #     ]
            #     for pattern in arrosage_patterns:
            #         match = re.search(pattern, detail.description_detaillee, re.IGNORECASE | re.DOTALL)
            #         if match:
            #             detail.arrosage_conseils = match.group(0).strip()
            #             break
            
            # 10. IMAGE PRINCIPALE
            # Stratégie 1: Chercher par alt contenant le nom
            main_img = None
            if detail.nom_complet:
                main_img = soup.find('img', alt=re.compile(re.escape(detail.nom_complet), re.IGNORECASE))
            
            # Stratégie 2: Chercher l'image principale du produit (première image large)
            if not main_img:
                # Chercher dans la zone galerie/carousel
                gallery_img = soup.find('img', class_=re.compile(r'w-full|product-image'))
                if gallery_img:
                    main_img = gallery_img
            
            # Stratégie 3: Chercher toute image avec srcset (format haute qualité)
            if not main_img:
                imgs_with_srcset = soup.find_all('img', srcset=True)
                if imgs_with_srcset:
                    # Prendre la première image avec srcset qui n'est pas un logo
                    for img in imgs_with_srcset:
                        src = img.get('src', '')
                        if 'media/catalog/product' in src or 'media/ri' in src:
                            main_img = img
                            break
            
            if main_img:
                # Prendre le src ou la plus haute résolution du srcset
                src = main_img.get('src', '')
                srcset = main_img.get('srcset', '')
                
                if srcset:
                    # Parser le srcset pour trouver la plus haute résolution
                    # Format: "url1 320w, url2 640w, url3 1200w"
                    srcset_parts = srcset.split(',')
                    max_width = 0
                    best_url = src
                    for part in srcset_parts:
                        part = part.strip()
                        if ' ' in part:
                            url, width_str = part.rsplit(' ', 1)
                            try:
                                width = int(width_str.replace('w', ''))
                                if width > max_width:
                                    max_width = width
                                    best_url = url
                            except:
                                pass
                    detail.image_principale = best_url
                    print(f"  📸 Image trouvée (srcset {max_width}w): {best_url[:80]}...")
                else:
                    detail.image_principale = src
                    print(f"  📸 Image trouvée (src): {src[:80]}...")
            else:
                print(f"  ⚠️ Image principale non trouvée")
            
            print(f"✅ Extraction réussie: {len(detail.formats)} formats trouvés")
            return detail
            
        except Exception as e:
            print(f"❌ Erreur extraction détails: {e}")
            import traceback
            traceback.print_exc()
            return None

# Instance globale du scraper
scraper = PromesseDeFleursScraper()

# Stockage simple en mémoire (à remplacer par DB en production)
library_db = {}
notes_db = {}
tags_db = {
    # Structure: { 'tag_id': { 'name': 'Massif Nord', 'color': '#4CAF50', 'created_at': '...' } }
}

tasks_db = {
    # Structure: { 'task_id': { 'title': '...', 'description': '...', 'category': '...', 'status': 'todo/done', 'created_at': '...', 'completed_at': '...', 'airtable_id': '...' } }
}

inventory_db = {
    # Structure: { 'inventory_id': { 'nom': '...', 'categorie': 'Outil/Matériau/Produit/Équipement', 'statut': 'Possédé/À acheter', 'etat': 'Bon/À réparer/À remplacer', 'quantite': 0, 'unite': '', 'seuil_alerte': 0, 'prix_estime': 0, 'date_expiration': '', 'dernier_entretien': '', 'notes': '', 'airtable_id': '' } }
}

journal_db = {
    # Structure: { 'journal_id': { 'date': 'YYYY-MM-DD', 'heure': 'HH:MM', 'categorie': '...', 'emplacement': '...', 'titre': '...', 'notes': '...', 'meteo': '...', 'airtable_id': '', 'created_at': '...' } }
}

zones_db = {
    # Structure: { 'zone_id': { 'nom': '...', 'icon': '...', 'description': '...', 'created_at': '...', 'airtable_id': '' } }
}

def get_next_tag_id():
    """Génère un ID unique pour un tag"""
    if not tags_db:
        return 1
    return max(tags_db.keys()) + 1

def get_next_task_id():
    """Génère un ID unique pour une tâche"""
    if not tasks_db:
        return 1
    return max(tasks_db.keys()) + 1

def get_next_inventory_id():
    """Génère un ID unique pour un item d'inventaire"""
    if not inventory_db:
        return 1
    return max(inventory_db.keys()) + 1

def get_next_journal_id():
    """Génère un ID unique pour une entrée journal"""
    if not journal_db:
        return 1
    return max(journal_db.keys()) + 1

def get_next_zone_id():
    """Génère un ID unique pour une zone"""
    if not zones_db:
        return 1
    return max(zones_db.keys()) + 1

def get_next_plant_id():
    """Génère un ID unique pour une plante"""
    if not library_db:
        return 1
    return max(library_db.keys()) + 1

def save_library_db():
    """Sauvegarde library_db (no-op pour l'instant, données en mémoire)"""
    # TODO: Implémenter sauvegarde fichier JSON si nécessaire
    pass

def save_notes_db():
    """Sauvegarde notes_db (no-op pour l'instant, données en mémoire)"""
    # TODO: Implémenter sauvegarde fichier JSON si nécessaire
    pass

@app.route('/')
def index():
    """Page d'accueil"""
    return send_from_directory('static', 'index.html')

@app.route('/<path:path>')
def serve_static(path):
    """Sert les fichiers statiques"""
    return send_from_directory('static', path)

@app.route('/api/stats', methods=['GET'])
def get_stats():
    """Statistiques de la bibliothèque"""
    total = len(library_db)
    
    # Compter par type
    type_counts = {}
    for plant_data in library_db.values():
        plant_type = plant_data.get('type_plante', 'Plante')
        type_counts[plant_type] = type_counts.get(plant_type, 0) + 1
    
    return jsonify({
        'total': total,
        'by_type': type_counts
    })

@app.route('/api/plant/detail', methods=['GET'])
def get_plant_detail():
    """Extrait les détails complets d'une plante"""
    url = request.args.get('url', '')
    
    if not url:
        return jsonify({'error': 'URL requise'}), 400
    
    print(f"\n{'='*60}")
    print(f"🔍 EXTRACTION DÉTAILS: {url}")
    print(f"{'='*60}\n")
    
    detail = scraper.fetch_plant_detail(url)
    
    if detail:
        print(f"\n✅ EXTRACTION RÉUSSIE")
        print(f"  • Nom: {detail.nom_francais}")
        print(f"  • Plantation: {detail.meilleure_periode_plantation}")
        print(f"  • Densité: {detail.densite_plantation}")
        print(f"  • Taille: {detail.taille}")
        print(f"  • Période taille: {detail.periode_taille}")
        print(f"  • Descriptif taille: {detail.descriptif_taille_detaille[:50] if detail.descriptif_taille_detaille else 'N/A'}...")
        print(f"  • Produits: {len(detail.produits_associes) if detail.produits_associes else 0}")
        print(f"{'='*60}\n")
        
        return jsonify({
            'success': True,
            'data': asdict(detail)
        })
    else:
        return jsonify({'error': 'Échec extraction'}), 500

@app.route('/api/plant/enrichment', methods=['GET'])
def get_plant_enrichment():
    """
    Récupère les données d'entretien enrichies depuis Rustica
    Query params:
        - nom_latin: Nom latin de la plante (requis)
        - force_refresh: Boolean pour forcer le refresh (optionnel)
    """
    if not ENRICHMENT_ENABLED:
        return jsonify({
            'success': False,
            'error': 'Module d\'enrichissement non disponible'
        }), 503
    
    nom_latin = request.args.get('nom_latin', '').strip()
    force_refresh = request.args.get('force_refresh', 'false').lower() == 'true'
    
    if not nom_latin:
        return jsonify({'error': 'nom_latin requis'}), 400
    
    print(f"\n{'='*60}")
    print(f"🌿 ENRICHISSEMENT: {nom_latin}")
    print(f"{'='*60}\n")
    
    try:
        # Vérifier le cache d'abord (sauf si force_refresh)
        if not force_refresh:
            cached_url = plant_matcher.get_from_cache(nom_latin, 'rustica')
            if cached_url:
                print(f"💾 Cache hit: {cached_url}")
                rustica_data = rustica_scraper.extract_plant_data(cached_url)
                if rustica_data:
                    return jsonify({
                        'success': True,
                        'source': 'cache',
                        'data': asdict(rustica_data)
                    })
        
        # Sinon, scraper Rustica
        rustica_data = rustica_scraper.get_plant_data(nom_latin)
        
        if rustica_data:
            # Sauvegarder dans le cache
            plant_matcher.add_to_cache(nom_latin, 'rustica', rustica_data.url)
            
            print(f"✅ Enrichissement réussi")
            print(f"  • Arrosage: {rustica_data.arrosage_frequence}")
            print(f"  • Fertilisation: {rustica_data.fertilisation_periode}")
            print(f"  • Maladies: {len(rustica_data.maladies)}")
            print(f"  • Parasites: {len(rustica_data.parasites)}")
            print(f"{'='*60}\n")
            
            return jsonify({
                'success': True,
                'source': 'rustica',
                'data': asdict(rustica_data)
            })
        else:
            print(f"⚠️ Pas de données Rustica trouvées")
            print(f"{'='*60}\n")
            return jsonify({
                'success': False,
                'error': 'Plante non trouvée sur Rustica'
            }), 404
            
    except Exception as e:
        print(f"❌ Erreur enrichissement: {e}")
        import traceback
        traceback.print_exc()
        print(f"{'='*60}\n")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/plant/aujardin-enrichment', methods=['GET'])
def get_aujardin_enrichment():
    """
    Récupère les données d'entretien depuis AuJardin.info
    Query params:
        - nom_latin: Nom latin de la plante (requis)
    """
    if not ENRICHMENT_ENABLED or not aujardin_scraper:
        return jsonify({
            'success': False,
            'error': 'Module AuJardin non disponible'
        }), 503
    
    nom_latin = request.args.get('nom_latin', '').strip()
    
    if not nom_latin:
        return jsonify({'error': 'nom_latin requis'}), 400
    
    print(f"\n{'='*60}")
    print(f"🌿 ENRICHISSEMENT AUJARDIN: {nom_latin}")
    print(f"{'='*60}\n")
    
    try:
        # Scraper AuJardin.info
        aujardin_data = aujardin_scraper.get_plant_data(nom_latin)
        
        if aujardin_data:
            print(f"✅ Enrichissement AuJardin réussi")
            print(f"  • Arrosage: {aujardin_data.arrosage or 'Non'}")
            print(f"  • Taille: {aujardin_data.taille_periode or 'Non'}")
            print(f"  • Multiplication: {aujardin_data.multiplication or 'Non'}")
            print(f"  • Maladies: {len(aujardin_data.maladies)}")
            print(f"  • Ravageurs: {len(aujardin_data.ravageurs)}")
            print(f"{'='*60}\n")
            
            # Convertir en dict pour JSON
            from dataclasses import asdict
            return jsonify({
                'success': True,
                'source': 'aujardin.info',
                'data': asdict(aujardin_data)
            })
        else:
            print(f"⚠️ Pas de données AuJardin trouvées")
            print(f"{'='*60}\n")
            return jsonify({
                'success': False,
                'error': 'Plante non trouvée sur AuJardin.info'
            }), 404
            
    except Exception as e:
        print(f"❌ Erreur enrichissement AuJardin: {e}")
        import traceback
        traceback.print_exc()
        print(f"{'='*60}\n")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/plant/aujardin-scrape-manual', methods=['POST'])
def scrape_aujardin_manual():
    """
    Scrape manuellement une URL AuJardin.info fournie par l'utilisateur
    Body: { "url": "https://www.aujardin.info/plantes/lavandula-angustifolia.php" }
    """
    if not ENRICHMENT_ENABLED or not aujardin_scraper:
        return jsonify({
            'success': False,
            'error': 'Module AuJardin non disponible'
        }), 503
    
    data = request.json
    url = data.get('url', '').strip()
    
    if not url:
        return jsonify({'error': 'URL requise'}), 400
    
    # Normaliser l'URL
    if not url.startswith('http'):
        url = 'https://' + url
    
    if 'aujardin.info' not in url:
        return jsonify({'error': 'URL doit être un lien aujardin.info'}), 400
    
    print(f"\n{'='*60}")
    print(f"🔍 SCRAPING MANUEL AUJARDIN: {url}")
    print(f"{'='*60}\n")
    
    try:
        # Scraper directement l'URL
        aujardin_data = aujardin_scraper.scrape_url_direct(url)
        
        if aujardin_data:
            print(f"✅ Scraping manuel réussi")
            print(f"  • Arrosage: {aujardin_data.arrosage or 'Non'}")
            print(f"  • Taille: {aujardin_data.taille_periode or 'Non'}")
            print(f"  • Multiplication: {aujardin_data.multiplication or 'Non'}")
            print(f"  • Maladies: {len(aujardin_data.maladies)}")
            print(f"  • Ravageurs: {len(aujardin_data.ravageurs)}")
            print(f"{'='*60}\n")
            
            # Convertir en dict pour JSON
            from dataclasses import asdict
            return jsonify({
                'success': True,
                'source': 'aujardin.info (manuel)',
                'data': asdict(aujardin_data)
            })
        else:
            print(f"⚠️ Impossible de scraper cette URL")
            print(f"{'='*60}\n")
            return jsonify({
                'success': False,
                'error': 'Impossible de scraper cette URL'
            }), 404
            
    except Exception as e:
        print(f"❌ Erreur scraping manuel: {e}")
        import traceback
        traceback.print_exc()
        print(f"{'='*60}\n")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/suggestions', methods=['GET'])
def get_suggestions():
    """Suggestions de plantes populaires"""
    # Suggestions par défaut si la bibliothèque est vide
    default_suggestions = [
        PlantInfo(
            nom_francais="Lavande vraie",
            nom_latin="Lavandula angustifolia",
            exposition="Plein soleil",
            type_plante="Vivace",
            prix="8,90 €",
            description="Lavande officinale aux fleurs parfumées et mellifères",
            icon="🌿",
            url=""
        ),
        PlantInfo(
            nom_francais="Rosier Pierre de Ronsard",
            nom_latin="Rosa 'Pierre de Ronsard'",
            exposition="Soleil",
            type_plante="Rosier",
            prix="24,90 €",
            description="Rosier grimpant aux grandes fleurs roses et blanches",
            icon="🌹",
            url=""
        ),
        PlantInfo(
            nom_francais="Hortensia paniculé",
            nom_latin="Hydrangea paniculata",
            exposition="Mi-ombre",
            type_plante="Arbuste",
            prix="19,90 €",
            description="Arbuste à grandes panicules de fleurs blanches virant au rose",
            icon="🌺",
            url=""
        )
    ]
    
    return jsonify([asdict(plant) for plant in default_suggestions])

@app.route('/api/search', methods=['GET'])
def search():
    """Endpoint de recherche"""
    query = request.args.get('q', '')
    max_results = int(request.args.get('max', 10))
    
    if not query:
        return jsonify({'error': 'Paramètre "q" requis'}), 400
    
    results = scraper.search_plants(query, max_results)
    
    return jsonify({
        'query': query,
        'count': len(results),
        'results': [asdict(plant) for plant in results]
    })

@app.route('/api/library', methods=['GET', 'DELETE'])
def handle_library():
    """Récupère ou réinitialise la bibliothèque complète"""
    if request.method == 'DELETE':
        # Réinitialiser complètement la bibliothèque
        library_db.clear()
        notes_db.clear()
        return jsonify({
            'success': True,
            'message': 'Bibliothèque réinitialisée'
        })
    
    # GET - Récupérer la bibliothèque
    plants_with_notes = []
    
    for plant_id, plant_data in library_db.items():
        plant_with_notes = plant_data.copy()
        plant_with_notes['plant_id'] = plant_id
        
        # Ajouter notes, quantité et photo personnalisée si existants
        if plant_id in notes_db:
            plant_with_notes['notes'] = notes_db[plant_id].get('notes', '')
            plant_with_notes['quantity'] = notes_db[plant_id].get('quantity', 0)
            plant_with_notes['custom_photo'] = notes_db[plant_id].get('custom_photo')
        else:
            plant_with_notes['notes'] = ''
            plant_with_notes['quantity'] = 0
            plant_with_notes['custom_photo'] = None
        
        plants_with_notes.append(plant_with_notes)
    
    return jsonify({
        'count': len(plants_with_notes),
        'plants': plants_with_notes
    })

@app.route('/api/library/all-notes', methods=['GET'])
def get_all_notes():
    """Retourne TOUTES les notes/tags en une seule requête (optimisation frontend)"""
    all_notes = {}
    
    for plant_id in library_db.keys():
        notes_data = notes_db.get(plant_id, {})
        all_notes[plant_id] = {
            'notes': notes_data.get('notes', ''),
            'quantity': notes_data.get('quantity', 0),
            'custom_photo': notes_data.get('custom_photo'),
            'tags': notes_data.get('tags', [])
        }
    
    return jsonify({
        'success': True,
        'notes': all_notes
    })

@app.route('/api/library/add', methods=['POST'])
def add_to_library():
    """Ajoute une plante à la bibliothèque"""
    data = request.json
    
    if not data or 'nom_francais' not in data:
        return jsonify({'error': 'Données invalides'}), 400
    
    # Générer un nouvel ID
    plant_id = get_next_plant_id()
    
    # Stocker la plante localement
    library_db[plant_id] = {
        'nom_francais': data.get('nom_francais', ''),
        'nom_latin': data.get('nom_latin', ''),
        'exposition': data.get('exposition', ''),
        'type_plante': data.get('type_plante', ''),
        'prix': data.get('prix', ''),
        'description': data.get('description', ''),
        'icon': data.get('icon', '🌿'),
        'url': data.get('url', ''),
        'details': data.get('details', {}),
        'image_principale': data.get('image_principale', '')
    }
    
    # Initialiser notes vides
    notes_db[plant_id] = {
        'notes': '',
        'quantity': 0,
        'tags': []
    }
    
    # Synchroniser avec Airtable si activé
    airtable_record_id = None
    if AIRTABLE_ENABLED and airtable_client:
        try:
            airtable_record_id = airtable_client.upsert_plant(library_db[plant_id])
            if airtable_record_id:
                print(f"✅ Plante synchronisée avec Airtable: {airtable_record_id}")
        except Exception as e:
            print(f"⚠️ Erreur sync Airtable: {e}")
            # Continue quand même (stockage local fonctionne)
    
    return jsonify({
        'success': True,
        'plant_id': plant_id,
        'airtable_record_id': airtable_record_id,
        'message': 'Plante ajoutée avec succès'
    })

@app.route('/api/library/get-or-create-id', methods=['POST'])
def get_or_create_plant_id():
    """
    Retourne l'ID d'une plante existante ou en crée un nouveau
    Basé sur nom_francais + nom_latin pour identifier les doublons
    Stocke TOUTES les données détaillées si disponibles
    """
    data = request.json
    
    print(f"\n{'='*60}")
    print(f"📥 get_or_create_plant_id - Données reçues:")
    print(f"   Nom: {data.get('nom_francais', 'N/A')}")
    print(f"   Details présents: {'details' in data}")
    if 'details' in data:
        print(f"   Details keys: {list(data['details'].keys())[:10]}")
        print(f"   periode_taille: {data['details'].get('periode_taille', 'NON PRÉSENT')}")
    print(f"{'='*60}\n")
    
    if not data or 'nom_francais' not in data:
        return jsonify({'error': 'Données invalides'}), 400
    
    nom_francais = data.get('nom_francais', '').strip()
    nom_latin = data.get('nom_latin', '').strip()
    
    # Chercher si la plante existe déjà
    for plant_id, plant_data in library_db.items():
        if (plant_data['nom_francais'] == nom_francais and 
            plant_data['nom_latin'] == nom_latin):
            # Plante existe déjà - mettre à jour les détails si fournis
            if 'details' in data and data['details']:
                plant_data['details'] = data['details']
                print(f"✅ Plante existe - Détails mis à jour pour ID {plant_id}")
                
                # Synchroniser avec Airtable si activé
                if AIRTABLE_ENABLED and airtable_client:
                    try:
                        airtable_client.upsert_plant(plant_data)
                    except Exception as e:
                        print(f"⚠️ Erreur sync Airtable: {e}")
            
            return jsonify({
                'plant_id': plant_id,
                'exists': True
            })
    
    # Plante n'existe pas, créer un nouvel ID
    plant_id = get_next_plant_id()
    
    # Stocker la plante avec toutes les données disponibles
    library_db[plant_id] = {
        # Données de base (toujours présentes)
        'nom_francais': nom_francais,
        'nom_latin': nom_latin,
        'exposition': data.get('exposition', ''),
        'type_plante': data.get('type_plante', ''),
        'prix': data.get('prix', ''),
        'description': data.get('description', ''),
        'icon': data.get('icon', '🌿'),
        'url': data.get('url', ''),
        
        # Données détaillées (si disponibles)
        'details': data.get('details', {}),
        'image_principale': data.get('image_principale', '')
    }
    
    print(f"✅ Nouvelle plante créée - ID {plant_id}")
    print(f"   Details stockés: {bool(library_db[plant_id]['details'])}")
    if library_db[plant_id]['details']:
        print(f"   periode_taille: {library_db[plant_id]['details'].get('periode_taille', 'NON')}")
    
    # Synchroniser avec Airtable si activé
    if AIRTABLE_ENABLED and airtable_client:
        try:
            airtable_record_id = airtable_client.upsert_plant(library_db[plant_id])
            print(f"✅ Plante synchronisée avec Airtable: {airtable_record_id}")
        except Exception as e:
            print(f"⚠️ Erreur sync Airtable: {e}")
    
    # Initialiser notes vides
    notes_db[plant_id] = {
        'notes': '',
        'quantity': 0,
        'tags': []
    }
    
    return jsonify({
        'plant_id': plant_id,
        'exists': False
    })

@app.route('/api/library/<int:plant_id>', methods=['DELETE'])
def delete_from_library(plant_id):
    """Supprime une plante de la bibliothèque"""
    
    print(f"\n🗑️ DELETE plant_id: {plant_id} (type: {type(plant_id).__name__})")
    print(f"   library_db keys: {list(library_db.keys())}")
    print(f"   notes_db keys: {list(notes_db.keys())}")
    
    if plant_id in library_db:
        plant_data = library_db[plant_id]
        
        print(f"📋 Données plante à supprimer:")
        print(f"   - nom_francais: {plant_data.get('nom_francais', 'N/A')}")
        print(f"   - nom_latin: {plant_data.get('nom_latin', 'N/A')}")
        print(f"   - Clés disponibles: {list(plant_data.keys())}")
        
        # Supprimer de la base locale
        del library_db[plant_id]
        save_library_db()
        
        if plant_id in notes_db:
            del notes_db[plant_id]
            save_notes_db()
        
        # Supprimer dans Airtable si activé
        if AIRTABLE_ENABLED and airtable_client:
            try:
                nom_latin = plant_data.get('nom_latin', '').strip()
                if nom_latin:
                    airtable_client.delete_plant_by_latin_name(nom_latin)
                else:
                    print(f"⚠️ Pas de nom latin pour supprimer dans Airtable")
                    print(f"   plant_data complet: {plant_data}")
            except Exception as e:
                print(f"⚠️ Erreur suppression Airtable: {e}")
        
        print(f"✅ Plante {plant_id} supprimée")
        return jsonify({'success': True})
    
    print(f"❌ Plante {plant_id} non trouvée. IDs disponibles: {list(library_db.keys())}")
    return jsonify({'error': 'Plante non trouvée'}), 404

@app.route('/api/library/<int:plant_id>/notes', methods=['GET', 'POST', 'PUT'])
def save_notes(plant_id):
    """Sauvegarde ou récupère les notes et la quantité d'une plante"""
    
    print(f"\n{'='*60}")
    print(f"📝 ENDPOINT NOTES - Method: {request.method}, plant_id: {plant_id} (type: {type(plant_id).__name__})")
    print(f"   library_db keys: {list(library_db.keys())} (types: {[type(k).__name__ for k in list(library_db.keys())[:3]]})")
    print(f"   notes_db keys: {list(notes_db.keys())} (types: {[type(k).__name__ for k in list(notes_db.keys())[:3]]})")
    print(f"{'='*60}\n")
    
    # GET - Récupérer les notes
    if request.method == 'GET':
        if plant_id in notes_db:
            print(f"✅ Notes trouvées pour plant_id {plant_id}")
            return jsonify(notes_db[plant_id])
        else:
            print(f"⚠️ Pas de notes pour plant_id {plant_id}, retour valeurs par défaut")
            return jsonify({
                'notes': '',
                'quantity': 0,
                'custom_photo': None
            })
    
    # POST/PUT - Sauvegarder les notes
    data = request.json
    plant_id_str = str(plant_id)
    
    print(f"📥 Données reçues: {data}")
    print(f"🔍 Vérification library_db:")
    print(f"   - plant_id (int) {plant_id} in library_db? {plant_id in library_db}")
    print(f"   - plant_id_str (str) '{plant_id_str}' in library_db? {plant_id_str in library_db}")
    
    # Vérifier avec INT d'abord
    if plant_id not in library_db and plant_id_str not in library_db:
        print(f"❌ Plante {plant_id} non trouvée pour notes. IDs disponibles: {list(library_db.keys())}")
        return jsonify({'error': 'Plante non trouvée'}), 404
    
    # Conserver la photo personnalisée si elle existe
    existing_photo = notes_db.get(plant_id, {}).get('custom_photo')
    
    # Conserver les tags si ils existent
    existing_tags = notes_db.get(plant_id, {}).get('tags', [])
    
    notes_db[plant_id] = {
        'notes': data.get('notes', ''),
        'quantity': data.get('quantity', 0),
        'custom_photo': existing_photo,
        'tags': existing_tags
    }
    
    print(f"✅ Notes/quantité sauvegardées pour plante {plant_id}: quantity={data.get('quantity', 0)}")
    print(f"📊 notes_db[{plant_id}] = {notes_db[plant_id]}")
    
    # Synchroniser avec Airtable
    if AIRTABLE_ENABLED and airtable_client and plant_id in library_db:
        plant_data = library_db[plant_id]
        if 'airtable_id' in plant_data and plant_data['airtable_id']:
            airtable_client.update_plant_notes_quantity(
                plant_data['airtable_id'],
                data.get('notes', ''),
                data.get('quantity', 0)
            )
    
    return jsonify({'success': True})

@app.route('/api/library/plant/<int:plant_id>/photo', methods=['POST'])
def save_custom_photo(plant_id):
    """Sauvegarde une photo personnalisée pour une plante"""
    data = request.json
    
    if plant_id not in library_db:
        return jsonify({'error': 'Plante non trouvée'}), 404
    
    photo = data.get('photo', '')
    
    # Vérifier que c'est une image base64
    if not photo.startswith('data:image'):
        return jsonify({'error': 'Format photo invalide'}), 400
    
    # Initialiser notes_db si nécessaire
    if plant_id not in notes_db:
        notes_db[plant_id] = {'notes': '', 'quantity': 0, 'tags': []}
    
    notes_db[plant_id]['custom_photo'] = photo
    
    return jsonify({'success': True})

@app.route('/api/library/plant/<int:plant_id>/photo', methods=['DELETE'])
def delete_custom_photo(plant_id):
    """Supprime la photo personnalisée d'une plante"""
    if plant_id not in library_db:
        return jsonify({'error': 'Plante non trouvée'}), 404
    
    if plant_id in notes_db:
        notes_db[plant_id]['custom_photo'] = None
    
    return jsonify({'success': True})

@app.route('/api/library/plant/<int:plant_id>', methods=['GET'])
def get_plant_info(plant_id):
    """Récupère les infos complètes d'une plante (notes + photo)"""
    if plant_id not in library_db:
        return jsonify({'error': 'Plante non trouvée'}), 404
    
    plant_data = library_db[plant_id].copy()
    notes_data = notes_db.get(plant_id, {})
    
    return jsonify({
        'in_library': True,
        'plant': plant_data,
        'notes': notes_data.get('notes', ''),
        'quantity': notes_data.get('quantity', 0),
        'custom_photo': notes_data.get('custom_photo')
    })

# ====== ENDPOINTS TAGS ======

@app.route('/api/tags', methods=['GET'])
def get_tags():
    """Récupère tous les tags"""
    return jsonify({
        'success': True,
        'tags': [{'id': tag_id, **tag_data} for tag_id, tag_data in tags_db.items()]
    })

@app.route('/api/tags', methods=['POST'])
def create_tag():
    """Crée un nouveau tag"""
    data = request.json
    
    if not data or 'name' not in data:
        return jsonify({'error': 'Nom du tag requis'}), 400
    
    tag_id = get_next_tag_id()
    
    tag_data = {
        'name': data['name'],
        'color': data.get('color', '#4CAF50'),
        'created_at': datetime.now().strftime('%Y-%m-%d')
    }
    
    tags_db[tag_id] = tag_data
    
    # Synchroniser avec Airtable
    if AIRTABLE_ENABLED and airtable_client:
        tag_data_with_id = {
            'tag_id': tag_id,
            **tag_data
        }
        airtable_client.create_tag(tag_data_with_id)
    
    return jsonify({
        'success': True,
        'tag': {'id': tag_id, **tags_db[tag_id]}
    })

@app.route('/api/tags/<int:tag_id>', methods=['DELETE'])
def delete_tag(tag_id):
    """Supprime un tag"""
    if tag_id in tags_db:
        # Retirer le tag de toutes les plantes
        for plant_id, plant_notes in notes_db.items():
            if 'tags' in plant_notes and tag_id in plant_notes['tags']:
                plant_notes['tags'].remove(tag_id)
                
                # Mettre à jour dans Airtable si disponible
                if AIRTABLE_ENABLED and airtable_client and plant_id in library_db:
                    plant_data = library_db[plant_id]
                    if 'airtable_id' in plant_data:
                        airtable_client.update_plant_tags(
                            plant_data['airtable_id'],
                            plant_notes['tags']
                        )
        
        # Supprimer le tag
        del tags_db[tag_id]
        
        # Supprimer d'Airtable
        if AIRTABLE_ENABLED and airtable_client:
            airtable_client.delete_tag(tag_id)
        
        return jsonify({'success': True})
    
    return jsonify({'error': 'Tag non trouvé'}), 404

@app.route('/api/library/<int:plant_id>/tags', methods=['POST'])
def add_tag_to_plant(plant_id):
    """Ajoute un tag à une plante"""
    data = request.json
    tag_id = data.get('tag_id')
    
    if tag_id not in tags_db:
        return jsonify({'error': 'Tag non trouvé'}), 404
    
    if plant_id not in notes_db:
        notes_db[plant_id] = {'notes': '', 'quantity': 0, 'tags': []}
    
    if 'tags' not in notes_db[plant_id]:
        notes_db[plant_id]['tags'] = []
    
    if tag_id not in notes_db[plant_id]['tags']:
        notes_db[plant_id]['tags'].append(tag_id)
    
    # Synchroniser avec Airtable
    if AIRTABLE_ENABLED and airtable_client and plant_id in library_db:
        plant_data = library_db[plant_id]
        if 'airtable_id' in plant_data and plant_data['airtable_id']:
            airtable_client.update_plant_tags(
                plant_data['airtable_id'],
                notes_db[plant_id]['tags']
            )
    
    return jsonify({'success': True, 'tags': notes_db[plant_id]['tags']})

@app.route('/api/library/<int:plant_id>/tags/<int:tag_id>', methods=['DELETE'])
def remove_tag_from_plant(plant_id, tag_id):
    """Retire un tag d'une plante"""
    if plant_id in notes_db and 'tags' in notes_db[plant_id]:
        if tag_id in notes_db[plant_id]['tags']:
            notes_db[plant_id]['tags'].remove(tag_id)
            
            # Synchroniser avec Airtable
            if AIRTABLE_ENABLED and airtable_client and plant_id in library_db:
                plant_data = library_db[plant_id]
                if 'airtable_id' in plant_data and plant_data['airtable_id']:
                    airtable_client.update_plant_tags(
                        plant_data['airtable_id'],
                        notes_db[plant_id]['tags']
                    )
            
            return jsonify({'success': True})
    
    return jsonify({'error': 'Tag ou plante non trouvé'}), 404

@app.route('/api/library/bulk-action', methods=['POST'])
def bulk_action():
    """Actions groupées sur plusieurs plantes"""
    data = request.json
    plant_ids = data.get('plant_ids', [])
    action = data.get('action')
    
    if action == 'add_tag':
        tag_id = data.get('tag_id')
        if tag_id not in tags_db:
            return jsonify({'error': 'Tag non trouvé'}), 404
        
        for plant_id in plant_ids:
            if plant_id not in notes_db:
                notes_db[plant_id] = {'notes': '', 'quantity': 0, 'tags': []}
            if 'tags' not in notes_db[plant_id]:
                notes_db[plant_id]['tags'] = []
            if tag_id not in notes_db[plant_id]['tags']:
                notes_db[plant_id]['tags'].append(tag_id)
            
            # Synchroniser avec Airtable
            if AIRTABLE_ENABLED and airtable_client and plant_id in library_db:
                plant_data = library_db[plant_id]
                if 'airtable_id' in plant_data and plant_data['airtable_id']:
                    airtable_client.update_plant_tags(
                        plant_data['airtable_id'],
                        notes_db[plant_id]['tags']
                    )
        
        return jsonify({'success': True, 'affected': len(plant_ids)})
    
    elif action == 'delete':
        for plant_id in plant_ids:
            if plant_id in library_db:
                del library_db[plant_id]
            if plant_id in notes_db:
                del notes_db[plant_id]
        
        return jsonify({'success': True, 'deleted': len(plant_ids)})
    
    return jsonify({'error': 'Action non supportée'}), 400

# ====== ENDPOINTS TÂCHES ======

@app.route('/api/tasks', methods=['GET'])
def get_tasks():
    """Récupère toutes les tâches"""
    tasks_list = [{'id': task_id, **task_data} for task_id, task_data in tasks_db.items()]
    return jsonify({
        'success': True,
        'tasks': tasks_list
    })

@app.route('/api/tasks', methods=['POST'])
def create_task():
    """Crée une nouvelle tâche"""
    data = request.json
    
    if not data or 'title' not in data:
        return jsonify({'error': 'Titre de la tâche requis'}), 400
    
    task_id = get_next_task_id()
    
    from datetime import datetime
    task_data = {
        'title': data['title'],
        'description': data.get('description', ''),
        'category': data.get('category', 'Autre'),
        'status': 'todo',
        'created_at': datetime.now().strftime('%Y-%m-%d'),
        'subtasks': data.get('subtasks', [])  # Liste de {text: str, completed: bool}
    }
    
    tasks_db[task_id] = task_data
    
    # Synchroniser avec Airtable
    if AIRTABLE_ENABLED and airtable_client:
        task_data_with_id = {
            'task_id': task_id,
            **task_data
        }
        airtable_id = airtable_client.create_task(task_data_with_id)
        if airtable_id:
            tasks_db[task_id]['airtable_id'] = airtable_id
    
    return jsonify({
        'success': True,
        'task': {'id': task_id, **tasks_db[task_id]}
    })

@app.route('/api/tasks/<int:task_id>', methods=['PATCH'])
def update_task(task_id):
    """Met à jour une tâche (statut, description, etc.)"""
    if task_id not in tasks_db:
        return jsonify({'error': 'Tâche non trouvée'}), 404
    
    data = request.json
    
    # Mise à jour des champs
    if 'title' in data:
        tasks_db[task_id]['title'] = data['title']
    if 'description' in data:
        tasks_db[task_id]['description'] = data['description']
    if 'category' in data:
        tasks_db[task_id]['category'] = data['category']
    if 'subtasks' in data:
        tasks_db[task_id]['subtasks'] = data['subtasks']
    if 'status' in data:
        tasks_db[task_id]['status'] = data['status']
        
        # Si passage à "done", ajouter date de complétion
        if data['status'] == 'done' and not tasks_db[task_id].get('completed_at'):
            tasks_db[task_id]['completed_at'] = datetime.now().strftime('%Y-%m-%d')
        # Si retour à "todo", supprimer date de complétion
        elif data['status'] == 'todo':
            if 'completed_at' in tasks_db[task_id]:
                del tasks_db[task_id]['completed_at']
    
    # Synchroniser avec Airtable
    if AIRTABLE_ENABLED and airtable_client and 'airtable_id' in tasks_db[task_id]:
        # Préparer les données pour Airtable
        airtable_data = data.copy()
        
        # Si on est passé à "done", ajouter completed_at
        if 'status' in data and data['status'] == 'done' and 'completed_at' in tasks_db[task_id]:
            airtable_data['completed_at'] = tasks_db[task_id]['completed_at']
        # Si on est repassé à "todo", vider completed_at dans Airtable
        elif 'status' in data and data['status'] == 'todo':
            airtable_data['completed_at'] = None  # None devient null en JSON
        
        airtable_client.update_task(tasks_db[task_id]['airtable_id'], airtable_data)
    
    return jsonify({
        'success': True,
        'task': {'id': task_id, **tasks_db[task_id]}
    })

@app.route('/api/tasks/<int:task_id>', methods=['DELETE'])
def delete_task_route(task_id):
    """Supprime une tâche"""
    if task_id in tasks_db:
        # Supprimer d'Airtable
        if AIRTABLE_ENABLED and airtable_client:
            airtable_client.delete_task(task_id)
        
        del tasks_db[task_id]
        return jsonify({'success': True})
    
    return jsonify({'error': 'Tâche non trouvée'}), 404

# ========== ROUTES INVENTAIRE ==========

@app.route('/api/inventory', methods=['GET'])
def get_inventory():
    """Récupère tout l'inventaire"""
    items = [
        {'id': item_id, **item_data}
        for item_id, item_data in inventory_db.items()
    ]
    return jsonify({'items': items})

@app.route('/api/inventory', methods=['POST'])
def add_inventory_item():
    """Ajoute un item à l'inventaire"""
    data = request.json
    
    item_id = get_next_inventory_id()
    
    item = {
        'nom': data.get('nom', ''),
        'categorie': data.get('categorie', 'Outil'),  # Outil / Matériau / Produit / Équipement
        'statut': data.get('statut', 'Possédé'),  # Possédé / À acheter
        'etat': data.get('etat', 'Bon'),  # Bon / À réparer / À remplacer
        'quantite': data.get('quantite', 1),
        'unite': data.get('unite', ''),  # pièce / kg / L / sacs / etc.
        'seuil_alerte': data.get('seuil_alerte', 1),
        'prix_estime': data.get('prix_estime', 0),
        'notes': data.get('notes', ''),
        'airtable_id': '',
        'created_at': datetime.now().isoformat()
    }
    
    # Ajouter dates seulement si présentes
    if 'date_expiration' in data and data['date_expiration']:
        item['date_expiration'] = data['date_expiration']
    
    if 'dernier_entretien' in data and data['dernier_entretien']:
        item['dernier_entretien'] = data['dernier_entretien']
    
    inventory_db[item_id] = item
    
    # Sauvegarder dans Airtable
    if AIRTABLE_ENABLED and airtable_client:
        airtable_id = airtable_client.upsert_inventory_item(item_id, item)
        if airtable_id:
            inventory_db[item_id]['airtable_id'] = airtable_id
    
    return jsonify({
        'success': True,
        'item': {'id': item_id, **item}
    })

@app.route('/api/inventory/<int:item_id>', methods=['PATCH'])
def update_inventory_item(item_id):
    """Modifie un item de l'inventaire"""
    if item_id not in inventory_db:
        return jsonify({'error': 'Item non trouvé'}), 404
    
    data = request.json
    
    # Mettre à jour les champs fournis
    for key in ['nom', 'categorie', 'statut', 'etat', 'quantite', 'unite', 'seuil_alerte', 'prix_estime', 'date_expiration', 'dernier_entretien', 'notes']:
        if key in data:
            inventory_db[item_id][key] = data[key]
    
    inventory_db[item_id]['updated_at'] = datetime.now().isoformat()
    
    # Mettre à jour dans Airtable
    if AIRTABLE_ENABLED and airtable_client:
        airtable_client.upsert_inventory_item(item_id, inventory_db[item_id])
    
    return jsonify({
        'success': True,
        'item': {'id': item_id, **inventory_db[item_id]}
    })

@app.route('/api/inventory/<int:item_id>', methods=['DELETE'])
def delete_inventory_item(item_id):
    """Supprime un item de l'inventaire"""
    if item_id in inventory_db:
        # Supprimer d'Airtable
        if AIRTABLE_ENABLED and airtable_client:
            airtable_client.delete_inventory_item(item_id)
        
        del inventory_db[item_id]
        return jsonify({'success': True})
    
    return jsonify({'error': 'Item non trouvé'}), 404

# ========== ROUTES JOURNAL ==========

@app.route('/api/journal', methods=['GET'])
def get_journal():
    """Récupère toutes les entrées du journal"""
    entries = [
        {'id': entry_id, **entry_data}
        for entry_id, entry_data in journal_db.items()
    ]
    # Trier par date décroissante (plus récent en premier)
    entries.sort(key=lambda x: (x.get('date', ''), x.get('heure', '')), reverse=True)
    return jsonify({'entries': entries})

@app.route('/api/journal', methods=['POST'])
def add_journal_entry():
    """Ajoute une entrée au journal"""
    data = request.json
    
    entry_id = get_next_journal_id()
    
    entry = {
        'date': data.get('date', datetime.now().strftime('%Y-%m-%d')),
        'heure': data.get('heure', ''),
        'categorie': data.get('categorie', 'Autre'),
        'emplacement': data.get('emplacement', ''),
        'zone_id': data.get('zone_id', None),
        'titre': data.get('titre', ''),
        'notes': data.get('notes', ''),
        'meteo': data.get('meteo', ''),
        'airtable_id': '',
        'created_at': datetime.now().isoformat()
    }
    
    journal_db[entry_id] = entry
    
    # Sauvegarder dans Airtable
    if AIRTABLE_ENABLED and airtable_client:
        airtable_id = airtable_client.upsert_journal_entry(entry_id, entry)
        if airtable_id:
            journal_db[entry_id]['airtable_id'] = airtable_id
    
    return jsonify({
        'success': True,
        'entry': {'id': entry_id, **journal_db[entry_id]}
    })

@app.route('/api/journal/<int:entry_id>', methods=['PATCH'])
def update_journal_entry(entry_id):
    """Modifie une entrée du journal"""
    if entry_id not in journal_db:
        return jsonify({'error': 'Entrée non trouvée'}), 404
    
    data = request.json
    
    # Mettre à jour les champs fournis
    for key in ['date', 'heure', 'categorie', 'emplacement', 'zone_id', 'titre', 'notes', 'meteo']:
        if key in data:
            journal_db[entry_id][key] = data[key]
    
    journal_db[entry_id]['updated_at'] = datetime.now().isoformat()
    
    # Mettre à jour dans Airtable
    if AIRTABLE_ENABLED and airtable_client:
        airtable_client.upsert_journal_entry(entry_id, journal_db[entry_id])
    
    return jsonify({
        'success': True,
        'entry': {'id': entry_id, **journal_db[entry_id]}
    })

@app.route('/api/journal/<int:entry_id>', methods=['DELETE'])
def delete_journal_entry(entry_id):
    """Supprime une entrée du journal"""
    if entry_id in journal_db:
        # Supprimer d'Airtable
        if AIRTABLE_ENABLED and airtable_client:
            airtable_client.delete_journal_entry(entry_id)
        
        del journal_db[entry_id]
        return jsonify({'success': True})
    
    return jsonify({'error': 'Entrée non trouvée'}), 404

# ========== ROUTES RAPPELS ==========

@app.route('/api/reminders/states', methods=['GET'])
def get_reminders_states():
    """Récupère tous les états de rappels"""
    if AIRTABLE_ENABLED and airtable_client:
        reminders = airtable_client.get_all_reminders()
        # Créer dict pour accès rapide: {plant_id}_{type}_{month} -> is_checked
        states = {}
        for r in reminders:
            key = f"{r['plant_id']}_{r['reminder_type']}_{r['month']}"
            states[key] = r['is_checked']
        return jsonify({'states': states})
    return jsonify({'states': {}})

@app.route('/api/reminders/toggle', methods=['POST'])
def toggle_reminder():
    """Bascule l'état d'un rappel"""
    data = request.json
    
    plant_id = data.get('plant_id')
    reminder_type = data.get('reminder_type')
    month = data.get('month')
    is_checked = data.get('is_checked', False)
    
    if not plant_id or not reminder_type or not month:
        return jsonify({'error': 'Paramètres manquants'}), 400
    
    if AIRTABLE_ENABLED and airtable_client:
        success = airtable_client.toggle_reminder(plant_id, reminder_type, month, is_checked)
        if success:
            return jsonify({'success': True, 'is_checked': is_checked})
    
    return jsonify({'error': 'Erreur sauvegarde'}), 500

# ========== ROUTES ZONES ==========

@app.route('/api/zones', methods=['GET'])
def get_zones():
    """Récupère toutes les zones"""
    zones_list = [{'id': zone_id, **zone_data} for zone_id, zone_data in zones_db.items()]
    return jsonify({
        'success': True,
        'zones': zones_list
    })

@app.route('/api/zones', methods=['POST'])
def create_zone():
    """Crée une nouvelle zone"""
    data = request.json
    
    if not data or 'nom' not in data:
        return jsonify({'error': 'Nom de la zone requis'}), 400
    
    zone_id = get_next_zone_id()
    
    from datetime import datetime
    zone_data = {
        'nom': data['nom'],
        'icon': data.get('icon', '🗺️'),
        'description': data.get('description', ''),
        'created_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    }
    
    # Sauvegarder dans Airtable
    if AIRTABLE_ENABLED and airtable_client:
        airtable_id = airtable_client.create_zone({
            'zone_id': zone_id,
            **zone_data
        })
        if airtable_id:
            zone_data['airtable_id'] = airtable_id
    
    zones_db[zone_id] = zone_data
    
    return jsonify({
        'success': True,
        'zone': {'id': zone_id, **zone_data}
    })

@app.route('/api/zones/<int:zone_id>', methods=['PATCH'])
def update_zone(zone_id):
    """Met à jour une zone existante"""
    if zone_id not in zones_db:
        return jsonify({'error': 'Zone non trouvée'}), 404
    
    data = request.json
    
    # Mettre à jour localement
    if 'nom' in data:
        zones_db[zone_id]['nom'] = data['nom']
    if 'icon' in data:
        zones_db[zone_id]['icon'] = data['icon']
    if 'description' in data:
        zones_db[zone_id]['description'] = data['description']
    
    # Sauvegarder dans Airtable
    if AIRTABLE_ENABLED and airtable_client:
        airtable_client.update_zone(zone_id, data)
    
    return jsonify({
        'success': True,
        'zone': {'id': zone_id, **zones_db[zone_id]}
    })

@app.route('/api/zones/<int:zone_id>', methods=['DELETE'])
def delete_zone(zone_id):
    """Supprime une zone"""
    if zone_id in zones_db:
        # Supprimer d'Airtable
        if AIRTABLE_ENABLED and airtable_client:
            airtable_client.delete_zone(zone_id)
        
        del zones_db[zone_id]
        return jsonify({'success': True})
    
    return jsonify({'error': 'Zone non trouvée'}), 404

@app.route('/api/weather', methods=['GET'])
def get_weather():
    """Récupère la météo et génère des alertes pour Malaucène"""
    try:
        # Coordonnées Malaucène (Vaucluse, Provence)
        lat = 44.1736
        lon = 5.1314
        
        # API OpenWeatherMap gratuite (pas besoin de clé pour test, mais tu devras en créer une)
        # Pour production: https://openweathermap.org/api (gratuit jusqu'à 1000 appels/jour)
        api_key = os.environ.get('OPENWEATHER_API_KEY', 'demo')  # À configurer dans Railway
        
        # Prévisions 5 jours (gratuit)
        url = f"https://api.openweathermap.org/data/2.5/forecast?lat={lat}&lon={lon}&units=metric&lang=fr&appid={api_key}"
        
        response = requests.get(url, timeout=10)
        
        if response.status_code != 200:
            # Si API ne marche pas, retourner données de demo
            return jsonify({
                'current': {
                    'temp': 15,
                    'description': 'Ensoleillé',
                    'icon': '☀️'
                },
                'forecast': [
                    {'day': 'Demain', 'temp_min': 10, 'temp_max': 18, 'icon': '🌤️'},
                    {'day': 'Mercredi', 'temp_min': 12, 'temp_max': 20, 'icon': '☀️'}
                ],
                'alerts': [],
                'demo': True
            })
        
        data = response.json()
        
        # Météo actuelle (premier élément)
        current = data['list'][0]
        current_temp = round(current['main']['temp'])
        current_desc = current['weather'][0]['description'].capitalize()
        
        # Icône météo
        weather_icons = {
            'clear': '☀️',
            'clouds': '☁️',
            'rain': '🌧️',
            'drizzle': '🌦️',
            'thunderstorm': '⛈️',
            'snow': '❄️',
            'mist': '🌫️',
            'fog': '🌫️'
        }
        weather_main = current['weather'][0]['main'].lower()
        current_icon = weather_icons.get(weather_main, '🌤️')
        
        # Prévisions prochains jours (prendre midi de chaque jour)
        forecast = []
        days_processed = set()
        for item in data['list']:
            dt = datetime.fromtimestamp(item['dt'])
            day_key = dt.strftime('%Y-%m-%d')
            
            if day_key not in days_processed and dt.hour == 12:
                days_processed.add(day_key)
                
                day_name = 'Demain' if len(forecast) == 0 else dt.strftime('%A').capitalize()
                
                forecast.append({
                    'day': day_name,
                    'temp_min': round(item['main']['temp_min']),
                    'temp_max': round(item['main']['temp_max']),
                    'icon': weather_icons.get(item['weather'][0]['main'].lower(), '🌤️'),
                    'rain': item.get('rain', {}).get('3h', 0)
                })
                
                if len(forecast) >= 3:
                    break
        
        # Générer alertes
        alerts = []
        
        for item in data['list'][:16]:  # Prochains 2 jours (3h x 16 = 48h)
            dt = datetime.fromtimestamp(item['dt'])
            temp = item['main']['temp']
            temp_min = item['main']['temp_min']
            rain = item.get('rain', {}).get('3h', 0)
            wind = item.get('wind', {}).get('speed', 0) * 3.6  # m/s → km/h
            
            day_str = 'aujourd\'hui' if dt.date() == datetime.now().date() else 'demain'
            time_str = dt.strftime('%Hh')
            
            # Alerte GEL
            if temp_min < 2:
                alerts.append({
                    'type': 'gel',
                    'icon': '❄️',
                    'title': f'Gel prévu {day_str}',
                    'message': f'{round(temp_min)}°C à {time_str}',
                    'action': 'Préparer voiles d\'hivernage',
                    'severity': 'high' if temp_min < 0 else 'medium'
                })
                break  # Une seule alerte gel
            
            # Alerte PLUIE FORTE
            if rain > 10:
                alerts.append({
                    'type': 'rain',
                    'icon': '💧',
                    'title': f'Pluie forte {day_str}',
                    'message': f'{round(rain)}mm attendus à {time_str}',
                    'action': 'Rentrer outils, protéger semis',
                    'severity': 'medium'
                })
                break  # Une seule alerte pluie
            
            # Alerte VENT FORT
            if wind > 60:
                alerts.append({
                    'type': 'wind',
                    'icon': '💨',
                    'title': f'Vent fort {day_str}',
                    'message': f'Rafales {round(wind)} km/h à {time_str}',
                    'action': 'Tuteurer plantes fragiles',
                    'severity': 'high' if wind > 80 else 'medium'
                })
                break  # Une seule alerte vent
            
            # Alerte CANICULE
            if temp > 35:
                alerts.append({
                    'type': 'heat',
                    'icon': '☀️',
                    'title': f'Canicule {day_str}',
                    'message': f'{round(temp)}°C à {time_str}',
                    'action': 'Prévoir arrosage renforcé',
                    'severity': 'high'
                })
                break  # Une seule alerte canicule
        
        # Retirer doublons alertes
        seen_types = set()
        unique_alerts = []
        for alert in alerts:
            if alert['type'] not in seen_types:
                seen_types.add(alert['type'])
                unique_alerts.append(alert)
        
        return jsonify({
            'current': {
                'temp': current_temp,
                'description': current_desc,
                'icon': current_icon
            },
            'forecast': forecast,
            'alerts': unique_alerts,
            'location': 'Malaucène'
        })
        
    except Exception as e:
        print(f"⚠️ Erreur météo: {e}")
        # Retourner données de demo en cas d'erreur
        return jsonify({
            'current': {
                'temp': 15,
                'description': 'Ensoleillé',
                'icon': '☀️'
            },
            'forecast': [
                {'day': 'Demain', 'temp_min': 10, 'temp_max': 18, 'icon': '🌤️'},
                {'day': 'Mercredi', 'temp_min': 12, 'temp_max': 20, 'icon': '☀️'}
            ],
            'alerts': [],
            'error': str(e),
            'demo': True
        })

@app.after_request
def add_no_cache_headers(response):
    """Ajoute des headers pour éviter le cache navigateur"""
    # Ne pas cacher les fichiers statiques HTML/JS
    if request.path.endswith(('.html', '.js')) or request.path.startswith('/api/'):
        response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate, public, max-age=0'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
    return response

def load_from_airtable():
    """
    Charge toutes les plantes ET les tags ET les tâches depuis Airtable au démarrage de l'application
    Évite la perte de données en cas de redémarrage
    """
    global library_db, notes_db, tags_db, tasks_db, inventory_db, journal_db
    
    print("\n" + "="*60)
    print("🔄 CHARGEMENT DEPUIS AIRTABLE")
    print("="*60)
    
    if not AIRTABLE_ENABLED or not airtable_client:
        print("⚠️ Airtable désactivé - Démarrage avec base vide")
        print("="*60 + "\n")
        return
    
    try:
        # ====== CHARGER LES TAGS ======
        print("\n📥 Chargement des tags...")
        airtable_tags = airtable_client.get_all_tags()
        
        tags_db.clear()
        for tag in airtable_tags:
            tag_id = tag['id']
            tags_db[tag_id] = {
                'name': tag['name'],
                'color': tag['color'],
                'created_at': tag['created_at']
            }
        
        print(f"✅ {len(tags_db)} tags chargés")
        
        # ====== CHARGER LES TÂCHES ======
        print("\n📥 Chargement des tâches...")
        airtable_tasks = airtable_client.get_all_tasks()
        
        tasks_db.clear()
        for task in airtable_tasks:
            task_id = task['id']
            task_data = {
                'title': task['title'],
                'description': task['description'],
                'category': task['category'],
                'status': task['status'],
                'created_at': task['created_at'],
                'airtable_id': task.get('airtable_id', '')
            }
            
            # Charger les subtasks si présentes
            if task.get('subtasks'):
                try:
                    task_data['subtasks'] = json.loads(task['subtasks'])
                except:
                    task_data['subtasks'] = []
            else:
                task_data['subtasks'] = []
            
            # N'ajouter completed_at que s'il existe et n'est pas vide
            if task.get('completed_at'):
                task_data['completed_at'] = task['completed_at']
            
            tasks_db[task_id] = task_data
        
        print(f"✅ {len(tasks_db)} tâches chargées")
        
        # ====== CHARGER L'INVENTAIRE ======
        print("\n📥 Chargement de l'inventaire...")
        airtable_inventory = airtable_client.get_all_inventory_items()
        
        inventory_db.clear()
        for item in airtable_inventory:
            item_id = item['id']
            inventory_db[item_id] = {
                'nom': item.get('nom', ''),
                'categorie': item.get('categorie', 'Outil'),
                'statut': item.get('statut', 'Possédé'),
                'etat': item.get('etat', 'Bon'),
                'quantite': item.get('quantite', 1),
                'unite': item.get('unite', ''),
                'seuil_alerte': item.get('seuil_alerte', 1),
                'prix_estime': item.get('prix_estime', 0),
                'date_expiration': item.get('date_expiration', ''),
                'dernier_entretien': item.get('dernier_entretien', ''),
                'notes': item.get('notes', ''),
                'airtable_id': item.get('airtable_id', ''),
                'created_at': item.get('created_at', '')
            }
        
        print(f"✅ {len(inventory_db)} items d'inventaire chargés")
        
        # ====== CHARGER LE JOURNAL ======
        print("\n📥 Chargement du journal...")
        airtable_journal = airtable_client.get_all_journal_entries()
        
        journal_db.clear()
        for entry in airtable_journal:
            entry_id = entry['id']
            journal_db[entry_id] = {
                'date': entry.get('date', ''),
                'heure': entry.get('heure', ''),
                'categorie': entry.get('categorie', 'Autre'),
                'emplacement': entry.get('emplacement', ''),
                'zone_id': entry.get('zone_id', None),
                'titre': entry.get('titre', ''),
                'notes': entry.get('notes', ''),
                'meteo': entry.get('meteo', ''),
                'airtable_id': entry.get('airtable_id', ''),
                'created_at': entry.get('created_at', '')
            }
        
        print(f"✅ {len(journal_db)} entrées journal chargées")
        
        # ====== CHARGER LES ZONES ======
        print("\n📥 Chargement des zones...")
        airtable_zones = airtable_client.get_all_zones()
        
        global zones_db
        zones_db.clear()
        for zone in airtable_zones:
            zone_id = zone['id']
            zones_db[zone_id] = {
                'nom': zone['nom'],
                'icon': zone['icon'],
                'description': zone['description'],
                'created_at': zone.get('created_at', ''),
                'airtable_id': zone.get('airtable_id', '')
            }
        
        print(f"✅ {len(zones_db)} zones chargées")
        
        # ====== CHARGER LES PLANTES ======
        print("\n📥 Chargement des plantes...")
        # Récupérer toutes les plantes depuis Airtable
        airtable_plants = airtable_client.get_all_plants()
        
        if not airtable_plants:
            print("⚠️ Aucune plante trouvée dans Airtable")
            print("="*60 + "\n")
            return
        
        print(f"📥 {len(airtable_plants)} plantes trouvées dans Airtable")
        
        # Réinitialiser les bases
        library_db.clear()
        notes_db.clear()
        
        # Compteurs
        loaded = 0
        errors = 0
        
        # Convertir chaque plante Airtable en format library_db
        for idx, plant_fields in enumerate(airtable_plants, start=1):
            try:
                # Vérifier que les champs essentiels existent
                nom_francais = plant_fields.get('nom_francais', '').strip()
                nom_latin = plant_fields.get('nom_latin', '').strip()
                
                if not nom_francais and not nom_latin:
                    print(f"⚠️ Plante #{idx} ignorée (pas de nom)")
                    errors += 1
                    continue
                
                # Utiliser l'index comme ID (séquentiel)
                plant_id = idx
                
                # Récupérer l'ID Airtable pour les mises à jour futures
                airtable_record_id = plant_fields.get('airtable_record_id', '')
                
                # Construire l'objet plante au format library_db
                library_db[plant_id] = {
                    # ID Airtable pour synchronisation
                    'airtable_id': airtable_record_id,
                    
                    # Données de base
                    'nom_francais': nom_francais or 'Nom inconnu',
                    'nom_latin': nom_latin or '',
                    'exposition': plant_fields.get('exposition', ''),
                    'type_plante': plant_fields.get('type_plante', 'Plante'),
                    'prix': plant_fields.get('prix', ''),
                    'description': plant_fields.get('description_courte', plant_fields.get('description_complete', '')),
                    'icon': '🌿',  # Icône par défaut
                    'url': plant_fields.get('url_source', ''),
                    'image_principale': plant_fields.get('image_principale', ''),
                    
                    # Détails COMPLETS (TOUS les champs Airtable)
                    'details': {
                        # Botaniques
                        'genre': plant_fields.get('genre', ''),
                        'espece': plant_fields.get('espece', ''),
                        'cultivar': plant_fields.get('cultivar', ''),
                        'famille': plant_fields.get('famille', ''),
                        'origine': plant_fields.get('origine', ''),
                        'autres_noms': plant_fields.get('autres_noms', ''),
                        
                        # Type et catégorie
                        'type_plante': plant_fields.get('type_plante', ''),
                        'sous_categorie': plant_fields.get('sous_categorie', ''),
                        
                        # Descriptions
                        'description_courte': plant_fields.get('description_courte', ''),
                        'description_complete': plant_fields.get('description_complete', ''),
                        'description_detaillee': plant_fields.get('description_complete', ''),  # Alias pour frontend
                        
                        # Conditions de culture (MAPPING FRONTEND)
                        'exposition': plant_fields.get('exposition', ''),
                        'rusticite': plant_fields.get('rusticite_zone', ''),  # Frontend cherche "rusticite"
                        'rusticite_zone': plant_fields.get('rusticite_zone', ''),
                        'rusticite_min_celsius': plant_fields.get('rusticite_min_celsius', ''),
                        'type_sol': plant_fields.get('sol_type', ''),  # Frontend cherche "type_sol"
                        'sol_type': plant_fields.get('sol_type', ''),
                        'ph_sol': plant_fields.get('sol_ph', ''),  # Frontend cherche "ph_sol"
                        'sol_ph': plant_fields.get('sol_ph', ''),
                        'sol_humidite': plant_fields.get('sol_humidite', ''),
                        'sol_drainage': plant_fields.get('sol_drainage', ''),
                        
                        # Dimensions
                        'hauteur_maturite': plant_fields.get('hauteur_maturite', ''),
                        'largeur_maturite': plant_fields.get('largeur_maturite', ''),
                        'port': plant_fields.get('port', ''),
                        'feuillage': plant_fields.get('feuillage', ''),
                        'persistance_feuillage': plant_fields.get('feuillage', ''),  # Alias pour frontend
                        
                        # Floraison (MAPPING FRONTEND)
                        'periode_floraison': plant_fields.get('periode_floraison', ''),
                        'periode_recolte': plant_fields.get('periode_recolte', ''),
                        'couleur_fleur': plant_fields.get('couleur_fleurs', ''),  # Frontend cherche "couleur_fleur"
                        'couleur_fleurs': plant_fields.get('couleur_fleurs', ''),
                        'couleur_feuillage': plant_fields.get('couleur_feuillage', ''),
                        'duree_floraison': plant_fields.get('duree_floraison', ''),
                        
                        # Plantation
                        'meilleure_periode_plantation': plant_fields.get('meilleure_periode_plantation', ''),
                        'periode_raisonnable_plantation': plant_fields.get('periode_raisonnable_plantation', ''),
                        'densite_plantation': plant_fields.get('densite_plantation', ''),
                        
                        # Entretien (MAPPING FRONTEND)
                        'taille_periode': plant_fields.get('taille_periode', ''),
                        'periode_taille': plant_fields.get('periode_taille', ''),
                        'periode_raisonnable_taille': plant_fields.get('periode_raisonnable_taille', ''),
                        'taille_technique': plant_fields.get('taille_technique', ''),
                        'descriptif_taille_detaille': plant_fields.get('taille_technique', ''),  # Alias pour frontend
                        'arrosage_frequence': plant_fields.get('arrosage_frequence', ''),
                        'arrosage_detail': plant_fields.get('arrosage_detail', ''),
                        'fertilisation': plant_fields.get('fertilisation', ''),
                        'multiplication': plant_fields.get('multiplication', ''),
                        'paillage': plant_fields.get('paillage', ''),
                        'tuteurage': plant_fields.get('tuteurage', ''),
                        'rabattage_periode': plant_fields.get('rabattage_periode', ''),
                        
                        # Utilisation (MAPPING FRONTEND)
                        'utilisations': plant_fields.get('utilisations', ''),
                        'type_utilisation': plant_fields.get('utilisations', ''),  # Frontend cherche "type_utilisation"
                        
                        # Culture
                        'difficulte_culture': plant_fields.get('difficulte_culture', ''),
                        'resistance_maladies': plant_fields.get('resistance_maladies', ''),
                        'hivernage': plant_fields.get('hivernage', ''),
                        
                        # Autres
                        'prix': plant_fields.get('prix', ''),
                        'disponibilite': plant_fields.get('disponibilite', ''),
                        'source': plant_fields.get('source', ''),
                        'statut': plant_fields.get('statut', ''),
                        'url_source': plant_fields.get('url_source', ''),
                        'image_principale': plant_fields.get('image_principale', '')
                    }
                }
                
                # Nettoyer les valeurs vides dans details
                library_db[plant_id]['details'] = {
                    k: v for k, v in library_db[plant_id]['details'].items()
                    if v is not None and v != '' and v != []
                }
                
                # Charger les tags depuis Airtable (format JSON ou liste directe)
                plant_tags = []
                tags_data = plant_fields.get('tags', '')
                print(f"   🔍 DEBUG tags_data brut: {repr(tags_data)} (type: {type(tags_data).__name__})")
                if tags_data:
                    try:
                        # Si c'est déjà une liste Python (Airtable peut retourner ça)
                        if isinstance(tags_data, list):
                            plant_tags = tags_data
                            print(f"   📋 Tags (liste directe): {plant_tags}")
                        # Si c'est une string JSON
                        elif isinstance(tags_data, str):
                            plant_tags = json.loads(tags_data)
                            if not isinstance(plant_tags, list):
                                plant_tags = []
                            print(f"   📋 Tags (JSON parsé): {plant_tags}")
                    except Exception as e:
                        print(f"   ⚠️ Erreur parsing tags: {e}")
                        plant_tags = []
                else:
                    print(f"   ℹ️ Pas de tags pour cette plante")
                
                # Charger notes et quantité depuis Airtable
                plant_notes = plant_fields.get('notes', '')
                plant_quantity = plant_fields.get('quantity', 0)
                
                # Initialiser notes_db avec données depuis Airtable
                notes_db[plant_id] = {
                    'notes': plant_notes,
                    'quantity': plant_quantity if isinstance(plant_quantity, int) else 0,
                    'custom_photo': None,  # Photos custom non sauvegardées dans Airtable
                    'tags': plant_tags
                }
                
                loaded += 1
                
            except Exception as e:
                print(f"❌ Erreur plante #{idx}: {e}")
                errors += 1
        
        print(f"✅ {loaded} plantes chargées avec succès")
        if errors > 0:
            print(f"⚠️ {errors} erreurs lors du chargement")
        
        print(f"📊 État final:")
        print(f"   - library_db: {len(library_db)} plantes")
        print(f"   - notes_db: {len(notes_db)} entrées")
        print(f"   - tags_db: {len(tags_db)} tags")
        print(f"   - tasks_db: {len(tasks_db)} tâches")
        print(f"   - inventory_db: {len(inventory_db)} items")
        print("="*60 + "\n")
        
    except Exception as e:
        print(f"❌ ERREUR CRITIQUE lors du chargement Airtable: {e}")
        print("⚠️ Démarrage avec base vide")
        print("="*60 + "\n")

if __name__ == '__main__':
    # Charger les données depuis Airtable au démarrage
    load_from_airtable()
    
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
