# 🌿 BOTANUS v13.5 - PROGRESSIVE WEB APP (PWA)

## ✨ NOUVEAUTÉS PWA

Cette version transforme Botanus en **Progressive Web App** avec :

✅ **Installation sur écran d'accueil** (comme une vraie app)
✅ **Mode offline** (fonctionne sans Internet)
✅ **Plein écran** (pas de barre navigateur)
✅ **Icône personnalisée** (olivier + B)
✅ **Mise à jour automatique**
✅ **Raccourcis rapides** (Bibliothèque, Tâches, Journal)

---

## 📦 FICHIERS PWA AJOUTÉS

```
static/
├── manifest.json          # Configuration PWA
├── service-worker.js      # Fonctionnement offline
├── icon.svg              # Icône Botanus (SVG adaptatif)
└── index.html            # Modifié avec meta tags PWA

main.py                   # Routes PWA ajoutées
```

---

## 🚀 DÉPLOIEMENT

### Railway (comme d'habitude)

1. Upload tous les fichiers
2. Railway détecte automatiquement
3. Déploiement normal !

**Aucun changement nécessaire !** Tous les fichiers sont compatibles.

---

## 📱 INSTALLATION SUR TÉLÉPHONE

### Android (Chrome)

1. Ouvrir `botanus.railway.app` dans Chrome
2. Bannière apparaît : **"Installer Botanus"**
3. Cliquer **"Installer"**
4. Icône 🌿 Botanus sur écran d'accueil !

**OU MANUELLEMENT :**
1. Menu Chrome (⋮)
2. "Installer l'application"
3. Confirmer

### iOS (Safari)

1. Ouvrir `botanus.railway.app` dans Safari
2. Bouton **"Partager"** (carré avec flèche)
3. **"Sur l'écran d'accueil"**
4. Confirmer

---

## 🎯 FONCTIONNALITÉS PWA

### ✅ Mode Offline

**Fonctionne SANS Internet :**
- Voir bibliothèque plantes
- Consulter tâches
- Lire journal
- Interface complète

**Nécessite Internet :**
- Synchronisation Airtable
- Recherche web
- Météo en temps réel
- Ajout nouvelles plantes (scraping)

**Stratégie :** Network First avec fallback cache

### 🔄 Mise à Jour Automatique

Quand nouvelle version déployée :
1. Détection automatique
2. Popup : *"Nouvelle version disponible !"*
3. Clic **"Recharger"**
4. Mise à jour instantanée

### 🎨 Icône Adaptive

**Light Mode :** Vert clair
**Dark Mode :** Vert foncé
**Thème système :** S'adapte automatiquement

### ⚡ Raccourcis Rapides

**Appui long sur icône Botanus :**
- 📚 Ma bibliothèque
- ✅ Mes tâches
- 📔 Mon journal

Accès direct !

---

## 🔧 TECHNIQUE

### Service Worker

**Cache stratégique :**
```javascript
// API requests : Network First
/api/* → Réseau puis cache

// Fichiers statiques : Cache First
/static/* → Cache puis réseau
```

**Nettoyage automatique** des anciens caches.

### Manifest

**Configuration complète :**
- Nom : Botanus
- Couleur thème : #4CAF50
- Mode : standalone (plein écran)
- Orientation : portrait
- Catégories : productivity, lifestyle

---

## 📊 COMPATIBILITÉ

### ✅ Compatible
- ✅ Android (Chrome, Edge, Samsung Internet)
- ✅ iOS (Safari 11.3+)
- ✅ Windows (Edge, Chrome)
- ✅ macOS (Safari, Chrome)
- ✅ Linux (Chrome, Firefox)

### ⚠️ Limitations iOS
- Notifications push : Non supportées (Safari)
- Shortcuts : Non supportés
- Background sync : Non supporté

**Mais installation + offline fonctionnent !**

---

## 🎯 HÉRITE TOUTES FONCTIONNALITÉS v13.5

✅ Multi-zones Airtable
✅ Recherche ville automatique (géolocalisation)
✅ Toggle buttons tri
✅ Miniatures photos
✅ Tous bugs corrigés
✅ + PWA !

---

## 🐛 DEBUG

### Service Worker ne s'enregistre pas

**Console navigateur :**
```javascript
navigator.serviceWorker.getRegistrations()
  .then(registrations => console.log(registrations));
```

**Vérifier :**
- HTTPS activé (Railway = OK)
- service-worker.js accessible
- Pas d'erreurs console

### Installation ne s'affiche pas

**Conditions requises :**
- HTTPS actif
- manifest.json valide
- Service worker enregistré
- Pas déjà installé

**Forcer affichage :**
Chrome DevTools → Application → Manifest → "Add to homescreen"

### Mode offline ne marche pas

**Vérifier cache :**
Chrome DevTools → Application → Cache Storage

**Doit contenir :**
- botanus-v13-5
- botanus-runtime

---

## 📝 NOTES IMPORTANTES

**Cache automatique :**
Le service worker met AUTOMATIQUEMENT en cache :
- Pages visitées
- API calls réussies
- Fichiers statiques

**Pas besoin de configuration manuelle !**

**Mises à jour :**
Toujours déployer avec nouveau numéro version dans `CACHE_NAME`.

---

## 🚀 PROCHAINES AMÉLIORATIONS PWA

**Futures possibilités :**
- 🔔 Notifications push (rappels arrosage)
- 🔄 Background sync (Airtable)
- 📸 Partage fichiers (Share API)
- 📍 Géolocalisation avancée
- 🎙️ Commandes vocales

**Mais déjà opérationnel !** 🌿✨

---

**Developed with 🌿 for Denis @ Clos Saint Michel**
