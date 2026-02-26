from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
from dataclasses import dataclass, asdict
from typing import List, Dict, Optional
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

@dataclass
class PlantDetailInfo:
    """Structure complète pour les détails d'une plante"""
    # Identification
    nom_complet: str = ""
    nom_latin: str = ""
    nom_francais: str = ""
    genre: str = ""
    espece: str = ""
    famille: str = ""
    origine: str = ""
    
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
            
            # 2.5. TYPE DE PLANTE depuis le fil d'Ariane (breadcrumb)
            breadcrumb = soup.find('ol', class_='items')
            if breadcrumb:
                # Trouver tous les items du breadcrumb
                all_items = breadcrumb.find_all('li', class_='item')
                print(f"🍞 Breadcrumb: {len(all_items)} niveaux trouvés")
                
                # Afficher tous les niveaux pour debug
                for idx, item in enumerate(all_items):
                    link = item.find('a')
                    if link:
                        print(f"  [{idx}] {self.clean_text(link.get_text())} (classes: {item.get('class', [])})")
                
                # Filtrer les items (ignorer "home" qui est l'accueil)
                items = [item for item in all_items if 'home' not in item.get('class', [])]
                print(f"  → {len(items)} niveaux après filtrage 'home'")
                
                # Structure après filtrage: [0] = Type (Vivaces/Arbustes/etc), [1] = Sous-catégorie, [2] = Détail
                if len(items) >= 1:
                    # Prendre le 1er élément après "home" = le type
                    type_item = items[0]
                    type_link = type_item.find('a')
                    if type_link:
                        type_text = self.clean_text(type_link.get_text())
                        detail.type_plante = type_text
                        print(f"  ✅ Type extrait: {type_text}")
                    
                    # Bonus: extraire la sous-catégorie si elle existe
                    if len(items) >= 2:
                        subcat_item = items[1]
                        subcat_link = subcat_item.find('a')
                        if subcat_link:
                            subcat_text = self.clean_text(subcat_link.get_text())
                            detail.sous_categorie = subcat_text
                            print(f"  📂 Sous-catégorie: {subcat_text}")
                else:
                    print(f"  ⚠️ Breadcrumb vide après filtrage, utilisation fallback")
            else:
                print(f"  ⚠️ Breadcrumb non trouvé")
            
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
                            
                            # Mapper selon la section
                            if section_title == 'Port':
                                if label == 'Port':
                                    detail.port = value
                                elif 'Croissance' in label:
                                    detail.croissance = value
                            
                            elif section_title == 'Floraison':
                                if 'couleur' in label.lower():
                                    detail.couleur_fleur = value
                                elif 'Période' in label:
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
                                elif 'Famille' in label:
                                    detail.famille = value
                                elif 'Origine' in label:
                                    detail.origine = value
                            
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

def get_next_plant_id():
    """Génère un ID unique pour une plante"""
    if not library_db:
        return 1
    return max(library_db.keys()) + 1

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

@app.route('/api/library/add', methods=['POST'])
def add_to_library():
    """Ajoute une plante à la bibliothèque"""
    data = request.json
    
    if not data or 'nom_francais' not in data:
        return jsonify({'error': 'Données invalides'}), 400
    
    # Générer un nouvel ID
    plant_id = get_next_plant_id()
    
    # Stocker la plante
    library_db[plant_id] = {
        'nom_francais': data.get('nom_francais', ''),
        'nom_latin': data.get('nom_latin', ''),
        'exposition': data.get('exposition', ''),
        'type_plante': data.get('type_plante', ''),
        'prix': data.get('prix', ''),
        'description': data.get('description', ''),
        'icon': data.get('icon', '🌿'),
        'url': data.get('url', ''),
        'details': data.get('details', {})
    }
    
    # Initialiser notes vides
    notes_db[plant_id] = {
        'notes': '',
        'quantity': 0
    }
    
    return jsonify({
        'success': True,
        'plant_id': plant_id,
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
        'details': data.get('details', {})
    }
    
    print(f"✅ Nouvelle plante créée - ID {plant_id}")
    print(f"   Details stockés: {bool(library_db[plant_id]['details'])}")
    if library_db[plant_id]['details']:
        print(f"   periode_taille: {library_db[plant_id]['details'].get('periode_taille', 'NON')}")
    
    # Initialiser notes vides
    notes_db[plant_id] = {
        'notes': '',
        'quantity': 0
    }
    
    return jsonify({
        'plant_id': plant_id,
        'exists': False
    })

@app.route('/api/library/<int:plant_id>', methods=['DELETE'])
def delete_from_library(plant_id):
    """Supprime une plante de la bibliothèque"""
    if plant_id in library_db:
        del library_db[plant_id]
        if plant_id in notes_db:
            del notes_db[plant_id]
        return jsonify({'success': True})
    
    return jsonify({'error': 'Plante non trouvée'}), 404

@app.route('/api/library/<int:plant_id>/notes', methods=['POST'])
def save_notes(plant_id):
    """Sauvegarde les notes et la quantité d'une plante"""
    data = request.json
    
    if plant_id not in library_db:
        return jsonify({'error': 'Plante non trouvée'}), 404
    
    # Conserver la photo personnalisée si elle existe
    existing_photo = notes_db.get(plant_id, {}).get('custom_photo')
    
    notes_db[plant_id] = {
        'notes': data.get('notes', ''),
        'quantity': data.get('quantity', 0),
        'custom_photo': existing_photo
    }
    
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
        notes_db[plant_id] = {'notes': '', 'quantity': 0}
    
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

@app.after_request
def add_no_cache_headers(response):
    """Ajoute des headers pour éviter le cache navigateur"""
    # Ne pas cacher les fichiers statiques HTML/JS
    if request.path.endswith(('.html', '.js')) or request.path.startswith('/api/'):
        response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate, public, max-age=0'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
    return response

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
