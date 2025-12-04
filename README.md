# Meta Ads Shopify Analyzer

Application dashboard pour la recherche et l'analyse des annonces Meta (Facebook Ads) ciblant les sites Shopify.

## Fonctionnalités

- **Recherche par mots-clés** : Recherche d'annonces actives via l'API Meta Ads Archive
- **Détection Shopify** : Vérification automatique HTTP pour identifier les sites Shopify
- **Analyse complète des sites** :
  - Détection du CMS et du thème
  - Identification des moyens de paiement
  - Classification thématique des produits
  - Comptage des produits via sitemaps
- **Dashboard interactif** : Interface Streamlit moderne avec graphiques
- **Export CSV** : 3 types d'exports (pages, annonces, suivi)

## Installation

```bash
# Cloner le repository
git clone <repository-url>
cd Migration-script

# Créer un environnement virtuel (recommandé)
python -m venv venv
source venv/bin/activate  # Linux/Mac
# ou: venv\Scripts\activate  # Windows

# Installer les dépendances
pip install -r requirements.txt
```

## Configuration

### Token Meta API

Vous avez besoin d'un token d'accès Meta Ads API. Deux options :

1. **Variable d'environnement** :
```bash
export META_ACCESS_TOKEN="votre_token_ici"
```

2. **Fichier .env** :
```
META_ACCESS_TOKEN=votre_token_ici
```

3. **Dans l'interface** : Entrez le token directement dans la sidebar

### Fichier Blacklist (optionnel)

Créez un fichier `blacklist.csv` avec les pages à exclure :
```csv
page_id;page_name
123456789;NomPage1
987654321;NomPage2
```

## Utilisation

### Dashboard (recommandé)

```bash
# Option 1: Via le script de lancement
python run.py

# Option 2: Directement avec Streamlit
streamlit run app/dashboard.py
```

Ouvrez ensuite http://localhost:8501 dans votre navigateur.

### Script CLI (original)

```bash
python V5_recherche_ads_complete.py
```

## Structure du projet

```
Migration-script/
├── app/
│   ├── __init__.py          # Package init
│   ├── config.py             # Configuration et constantes
│   ├── meta_api.py           # Client API Meta
│   ├── web_analyzer.py       # Analyse des sites web
│   ├── shopify_detector.py   # Détection Shopify
│   ├── utils.py              # Utilitaires et exports
│   └── dashboard.py          # Application Streamlit
├── résultats/                # Dossier des exports CSV
├── run.py                    # Script de lancement
├── requirements.txt          # Dépendances Python
├── V5_recherche_ads_complete.py  # Script CLI original
└── README.md
```

## Seuils de filtrage

| Seuil | Valeur par défaut | Description |
|-------|-------------------|-------------|
| MIN_ADS_INITIAL | 5 | Filtre préliminaire (recherche) |
| MIN_ADS_FOR_EXPORT | 15 | Export CSV pages et suivi |
| MIN_ADS_FOR_ADS_CSV | 25 | Export CSV annonces |

## Exports CSV

### 1. Liste des pages (`liste_pages_*.csv`)
Contient toutes les pages Shopify avec ≥15 ads :
- Informations page (ID, nom, site)
- Analyse web (CMS, thème, paiements)
- Classification (thématique, produits)

### 2. Liste des annonces (`liste_ads_*.csv`)
Toutes les annonces des pages avec ≥25 ads :
- Détails de l'annonce
- Contenu créatif
- Ciblage

### 3. Suivi site (`suivi_site_*.csv`)
Données de suivi pour monitoring :
- Nombre d'ads actives
- Nombre de produits
- Date de scan

## Dépendances principales

- **Streamlit** : Framework dashboard
- **Pandas** : Traitement des données
- **Plotly** : Visualisations interactives
- **BeautifulSoup** : Parsing HTML
- **Requests** : Requêtes HTTP

## Licence

MIT License
