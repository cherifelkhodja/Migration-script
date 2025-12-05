# Déploiement sur Railway

Guide rapide pour déployer Meta Ads Analyzer sur Railway.

## Architecture

```
┌─────────────────────┐     ┌─────────────────────┐
│   Service Web       │     │   Service Worker    │
│   (Streamlit)       │     │   (Scheduler)       │
│   Port: $PORT       │     │   Cron: 5 min       │
└─────────┬───────────┘     └─────────┬───────────┘
          │                           │
          └───────────┬───────────────┘
                      ▼
              ┌───────────────┐
              │  PostgreSQL   │
              │   (Add-on)    │
              └───────────────┘
```

## Étapes de déploiement

### 1. Créer un nouveau projet Railway

1. Aller sur [railway.app](https://railway.app)
2. Cliquer sur "New Project"
3. Sélectionner "Deploy from GitHub repo"
4. Autoriser l'accès et sélectionner ce repository

### 2. Ajouter PostgreSQL

1. Dans le projet, cliquer sur "+ New"
2. Sélectionner "Database" → "PostgreSQL"
3. Railway crée automatiquement `DATABASE_URL`

### 3. Configurer les variables d'environnement

Dans les settings du service web, ajouter :

| Variable | Valeur |
|----------|--------|
| `META_ACCESS_TOKEN` | Votre token Meta API |
| `DATABASE_URL` | (automatique via PostgreSQL) |

### 4. Déployer le service Worker (optionnel)

Pour les scans automatiques :

1. Cliquer sur "+ New" → "Empty Service"
2. Connecter au même repo GitHub
3. Dans Settings → Deploy :
   - Start Command: `python scheduler.py`
4. Ajouter les mêmes variables d'environnement
5. Lier au même PostgreSQL

### 5. Domaine personnalisé (optionnel)

1. Aller dans Settings du service web
2. Section "Networking" → "Generate Domain"
3. Ou ajouter un domaine personnalisé

## Variables d'environnement

| Variable | Description | Requis |
|----------|-------------|--------|
| `META_ACCESS_TOKEN` | Token API Meta Ads | ✅ |
| `DATABASE_URL` | URL PostgreSQL | ✅ (auto) |
| `PORT` | Port Streamlit | ✅ (auto) |

## Commandes utiles

```bash
# Logs du service web
railway logs -s web

# Logs du scheduler
railway logs -s worker

# Variables d'environnement
railway variables

# Shell dans le container
railway shell
```

## Coûts estimés

- **Hobby Plan** (~5$/mois) : Suffisant pour usage personnel
- **Pro Plan** : Pour usage intensif avec plus de ressources

## Troubleshooting

### L'app ne démarre pas
- Vérifier les logs : `railway logs`
- Vérifier que `META_ACCESS_TOKEN` est défini
- Vérifier la connexion PostgreSQL

### Les scans ne s'exécutent pas
- Vérifier que le service worker tourne
- Vérifier les logs du worker
- Vérifier que des scans sont programmés et actifs dans l'UI

### Erreur de base de données
- Les tables sont créées automatiquement au premier lancement
- Vérifier que `DATABASE_URL` est bien liée au PostgreSQL
