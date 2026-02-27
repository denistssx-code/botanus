"""
Module de matching et correspondance entre différentes sources de plantes
Permet de retrouver la même plante sur différents sites (Promesse de Fleurs, Rustica, etc.)
"""

import json
import os
from typing import Optional, Dict, List, Tuple
from fuzzywuzzy import fuzz
import re

class PlantMatcher:
    """Gère les correspondances entre différentes sources de données botaniques"""
    
    def __init__(self, cache_file='plant_mapping_cache.json'):
        self.cache_file = cache_file
        self.mapping_cache = self._load_cache()
    
    def _load_cache(self) -> Dict:
        """Charge le cache des correspondances depuis le fichier JSON"""
        if os.path.exists(self.cache_file):
            try:
                with open(self.cache_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                print(f"⚠️ Erreur lecture cache: {e}")
                return {}
        return {}
    
    def _save_cache(self):
        """Sauvegarde le cache des correspondances"""
        try:
            with open(self.cache_file, 'w', encoding='utf-8') as f:
                json.dump(self.mapping_cache, f, indent=2, ensure_ascii=False)
            print(f"✅ Cache sauvegardé : {len(self.mapping_cache)} entrées")
        except Exception as e:
            print(f"❌ Erreur sauvegarde cache: {e}")
    
    def normalize_latin_name(self, nom_latin: str) -> str:
        """
        Normalise un nom latin pour le matching
        Enlève les variétés, cultivars, et garde seulement Genre + espèce
        
        Exemples:
        "Lavandula angustifolia 'Hidcote'" → "lavandula angustifolia"
        "Rosa 'Pierre de Ronsard'" → "rosa"
        "Olea europaea subsp. europaea" → "olea europaea"
        """
        if not nom_latin:
            return ""
        
        # Enlever les cultivars entre quotes
        cleaned = re.sub(r"['\"].*?['\"]", "", nom_latin)
        
        # Enlever subsp., var., f., etc.
        cleaned = re.sub(r'\b(subsp\.|var\.|f\.|cv\.|×)\b.*$', '', cleaned, flags=re.IGNORECASE)
        
        # Garder seulement les 2 premiers mots (Genre espèce)
        parts = cleaned.strip().split()
        if len(parts) >= 2:
            return f"{parts[0]} {parts[1]}".lower().strip()
        elif len(parts) == 1:
            return parts[0].lower().strip()
        
        return ""
    
    def get_from_cache(self, nom_latin: str, source: str) -> Optional[str]:
        """Récupère une correspondance depuis le cache"""
        normalized = self.normalize_latin_name(nom_latin)
        if normalized in self.mapping_cache:
            return self.mapping_cache[normalized].get(source)
        return None
    
    def add_to_cache(self, nom_latin: str, source: str, url: str):
        """Ajoute une correspondance au cache"""
        normalized = self.normalize_latin_name(nom_latin)
        if normalized not in self.mapping_cache:
            self.mapping_cache[normalized] = {}
        
        self.mapping_cache[normalized][source] = url
        self._save_cache()
        print(f"💾 Cache: {nom_latin} ({normalized}) → {source}")
    
    def fuzzy_match_name(self, target: str, candidates: List[str], threshold: int = 80) -> Optional[Tuple[str, int]]:
        """
        Trouve la meilleure correspondance floue entre un nom et une liste de candidats
        
        Args:
            target: Nom à chercher
            candidates: Liste de noms candidats
            threshold: Score minimum (0-100)
        
        Returns:
            Tuple (meilleur_candidat, score) ou None si aucun match
        """
        if not target or not candidates:
            return None
        
        target_clean = target.lower().strip()
        best_score = 0
        best_match = None
        
        for candidate in candidates:
            candidate_clean = candidate.lower().strip()
            
            # Calculer plusieurs scores et prendre le meilleur
            ratio = fuzz.ratio(target_clean, candidate_clean)
            partial = fuzz.partial_ratio(target_clean, candidate_clean)
            token_sort = fuzz.token_sort_ratio(target_clean, candidate_clean)
            
            score = max(ratio, partial, token_sort)
            
            if score > best_score:
                best_score = score
                best_match = candidate
        
        if best_score >= threshold:
            return (best_match, best_score)
        
        return None
    
    def extract_genre(self, nom_latin: str) -> str:
        """Extrait le genre d'un nom latin"""
        if not nom_latin:
            return ""
        parts = nom_latin.split()
        return parts[0].lower().strip() if parts else ""
    
    def is_same_genus(self, nom_latin1: str, nom_latin2: str) -> bool:
        """Vérifie si deux noms latins sont du même genre"""
        return self.extract_genre(nom_latin1) == self.extract_genre(nom_latin2)
    
    def match_confidence(self, promesse_plant: Dict, rustica_plant: Dict) -> int:
        """
        Calcule un score de confiance (0-100) que deux plantes correspondent
        
        Basé sur:
        - Nom latin (poids fort)
        - Nom français (poids moyen)
        - Genre botanique (poids faible)
        """
        score = 0
        
        # Nom latin (60 points max)
        if promesse_plant.get('nom_latin') and rustica_plant.get('nom_latin'):
            promesse_norm = self.normalize_latin_name(promesse_plant['nom_latin'])
            rustica_norm = self.normalize_latin_name(rustica_plant['nom_latin'])
            
            if promesse_norm == rustica_norm:
                score += 60
            elif self.is_same_genus(promesse_plant['nom_latin'], rustica_plant['nom_latin']):
                score += 20
        
        # Nom français (30 points max)
        if promesse_plant.get('nom_francais') and rustica_plant.get('nom_francais'):
            match = self.fuzzy_match_name(
                promesse_plant['nom_francais'],
                [rustica_plant['nom_francais']],
                threshold=70
            )
            if match:
                _, match_score = match
                score += int(match_score * 0.3)  # Convertir score fuzzy (0-100) en points (0-30)
        
        # Famille botanique si disponible (10 points max)
        if promesse_plant.get('famille') and rustica_plant.get('famille'):
            if promesse_plant['famille'].lower() == rustica_plant['famille'].lower():
                score += 10
        
        return min(score, 100)  # Cap à 100


# Instance globale
plant_matcher = PlantMatcher()


if __name__ == "__main__":
    # Tests unitaires
    matcher = PlantMatcher()
    
    print("=== Tests de normalisation ===")
    tests = [
        "Lavandula angustifolia 'Hidcote'",
        "Rosa 'Pierre de Ronsard'",
        "Olea europaea subsp. europaea",
        "Prunus avium",
    ]
    
    for test in tests:
        normalized = matcher.normalize_latin_name(test)
        print(f"{test:50} → {normalized}")
    
    print("\n=== Tests de fuzzy matching ===")
    target = "Lavande vraie"
    candidates = ["Lavande officinale", "Lavande papillon", "Lavandin", "Rose"]
    
    match = matcher.fuzzy_match_name(target, candidates)
    if match:
        best, score = match
        print(f"'{target}' → '{best}' (score: {score}%)")
    
    print("\n=== Tests de cache ===")
    matcher.add_to_cache("Lavandula angustifolia", "rustica", "https://rustica.fr/lavande-123.html")
    cached = matcher.get_from_cache("Lavandula angustifolia 'Hidcote'", "rustica")
    print(f"Cache lookup: {cached}")
    
    print("\n✅ Tests terminés")
