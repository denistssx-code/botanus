# 🌿 Ma Bibliothèque Végétale - Déploiement Railway

Application web de gestion de plantes prête pour Railway.

## 🚂 Déploiement sur Railway

### Méthode 1 : Déploiement depuis GitHub (Recommandé)

1. **Créer un repo GitHub**
   ```bash
   git init
   git add .
   git commit -m "Initial commit"
   git remote add origin https://github.com/TON-USERNAME/bibliotheque-vegetale.git
   git push -u origin main
   ```

2. **Connecter à Railway**
   - Va sur [railway.app](https://railway.app)
   - Clique sur "New Project"
   - Sélectionne "Deploy from GitHub repo"
   - Choisis ton repo
   - Railway détectera automatiquement Python et déploiera ! 🎉

### Méthode 2 : Déploiement direct via Railway CLI

1. **Installer Railway CLI**
   ```bash
   npm i -g @railway/cli
   ```

2. **Login et déployer**
   ```bash
   railway login
   railway init
   railway up
   ```

## 📁 Structure des fichiers pour Railway

```
.
├── main.py              # Serveur Flask principal
├── static/
│   └── index.html       # Frontend de l'application
├── requirements.txt     # Dépendances Python
├── Procfile            # Configuration Railway
└── runtime.txt         # Version Python
```

## ⚙️ Configuration automatique

Railway configurera automatiquement :
- ✅ Port (via variable `PORT`)
- ✅ Dépendances Python (`requirements.txt`)
- ✅ Commande de démarrage (`Procfile`)

## 🌐 Après déploiement

Une fois déployé, tu obtiendras une URL type :
```
https://ton-app.up.railway.app
```

L'application sera **entièrement fonctionnelle** :
- 🏠 Page d'accueil : `https://ton-app.up.railway.app/`
- 🔍 API de recherche : `https://ton-app.up.railway.app/api/search?q=lavande`
- 📚 API bibliothèque : `https://ton-app.up.railway.app/api/library`

## 🔧 Variables d'environnement (optionnel)

Railway détecte automatiquement la variable `PORT`, mais tu peux ajouter :

```bash
# Via Railway Dashboard
PORT=8080  # (automatique, pas besoin de le définir)
```

## 📊 Monitoring

Railway te fournit :
- 📈 Logs en temps réel
- 💾 Usage mémoire/CPU
- 🔄 Redéploiement automatique sur push Git

## ⚠️ Limitations actuelles

- **Données en mémoire** : Les plantes ajoutées disparaissent au redémarrage
- **Solution** : Ajouter une vraie base de données (PostgreSQL disponible sur Railway)

### Pour ajouter PostgreSQL :

1. Dans Railway Dashboard → "New" → "Database" → "PostgreSQL"
2. Modifier `main.py` pour utiliser SQLAlchemy
3. Les données persisteront ! 🎉

## 🆓 Plan gratuit Railway

- ✅ 500 heures d'exécution/mois
- ✅ 1GB RAM
- ✅ 1GB disque
- ✅ Parfait pour ce projet !

## 🐛 Dépannage

### Erreur de build
```
Vérifier que requirements.txt contient :
flask==3.0.0
flask-cors==4.0.0
```

### L'app ne démarre pas
```
Vérifier les logs Railway :
railway logs
```

### Port déjà utilisé
```
Railway gère automatiquement le port via la variable PORT
Pas besoin de configuration manuelle !
```

## 📝 Commandes utiles

```bash
# Voir les logs
railway logs

# Ouvrir l'app dans le navigateur
railway open

# Redéployer
git push origin main

# Lier un projet Railway existant
railway link
```

## 🎯 Checklist de déploiement

- [ ] Fichiers présents : `main.py`, `static/index.html`, `requirements.txt`, `Procfile`
- [ ] Compte Railway créé
- [ ] Repo GitHub créé (optionnel mais recommandé)
- [ ] Push sur Railway
- [ ] Test de l'URL générée
- [ ] ✅ Application en ligne !

## 🚀 Prochaines étapes

Une fois déployé, tu peux :
- [ ] Ajouter PostgreSQL pour persistance
- [ ] Configurer un nom de domaine custom
- [ ] Ajouter des variables d'environnement
- [ ] Mettre en place un CI/CD

---

Bon déploiement ! 🌿🚂
