# Meta Ads Shopify Analyzer

Application dashboard pour la recherche et l'analyse des annonces Meta (Facebook Ads) ciblant les sites Shopify.

## Architecture

Ce projet suit une **architecture hexagonale** (Ports & Adapters) avec les principes **SOLID** et **Clean Code**.

```
src/
├── domain/                    # Coeur metier (0 dependances externes)
│   ├── entities/              # Page, Ad, WinningAd, Collection
│   ├── value_objects/         # PageId, Etat, CMS, Url, Reach, etc.
│   ├── services/              # WinningAdDetector, PageStateCalculator
│   └── exceptions.py          # Exceptions metier
│
├── application/               # Orchestration
│   ├── ports/                 # Interfaces (repositories, services)
│   │   ├── repositories/      # PageRepository, AdRepository, etc.
│   │   └── services/          # AdsSearchService, ClassificationService
│   └── use_cases/             # SearchAds, DetectWinningAds, etc.
│
└── infrastructure/            # Adapters (implementations)
    ├── external_services/     # MetaAdsSearchAdapter
    └── persistence/           # SQLAlchemyPageRepository

app/                           # Couche Presentation (legacy)
├── dashboard.py               # Application Streamlit
├── meta_api.py                # Client API Meta
├── database.py                # Gestion PostgreSQL
└── ...
```

## Fonctionnalites

- **Recherche par mots-cles** : Recherche d'annonces actives via l'API Meta Ads Archive
- **Detection Winning Ads** : Identification des annonces performantes selon des criteres age/reach
- **Detection Shopify** : Verification automatique HTTP pour identifier les sites Shopify
- **Analyse complete des sites** :
  - Detection du CMS et du theme
  - Identification des moyens de paiement
  - Classification thematique des produits
  - Comptage des produits via sitemaps
- **Dashboard interactif** : Interface Streamlit moderne avec graphiques
- **Export CSV** : 3 types d'exports (pages, annonces, suivi)

## Installation

```bash
# Cloner le repository
git clone <repository-url>
cd Migration-script

# Creer un environnement virtuel
python -m venv venv
source venv/bin/activate  # Linux/Mac
# ou: venv\Scripts\activate  # Windows

# Installer les dependances
pip install -e ".[dev]"
```

## Configuration

### Token Meta API

Vous avez besoin d'un token d'acces Meta Ads API. Trois options :

1. **Variable d'environnement** :
```bash
export META_ACCESS_TOKEN="votre_token_ici"
```

2. **Fichier .env** :
```
META_ACCESS_TOKEN=votre_token_ici
```

3. **Dans l'interface** : Entrez le token directement dans la sidebar

### Base de donnees PostgreSQL

```
DATABASE_URL=postgresql://user:password@host:5432/database
```

## Utilisation

### Dashboard

```bash
# Lancer l'application
python run.py

# Ou directement avec Streamlit
streamlit run app/dashboard.py
```

Ouvrez ensuite http://localhost:8501 dans votre navigateur.

### Utilisation programmatique

```python
from src.domain.entities import Ad, Page
from src.domain.value_objects import PageId, Reach
from src.application.use_cases import SearchAdsUseCase, DetectWinningAdsUseCase
from src.infrastructure.external_services import MetaAdsSearchAdapter

# Creer l'adapter
from app.meta_api import MetaAdsClient
client = MetaAdsClient(access_token="...")
adapter = MetaAdsSearchAdapter(client)

# Executer une recherche
use_case = SearchAdsUseCase(ads_service=adapter)
from src.application.use_cases.search_ads import SearchAdsRequest
request = SearchAdsRequest(keywords=["bijoux"], countries=["FR"])
response = use_case.execute(request)

print(f"{response.pages_count} pages trouvees")
```

## Tests

```bash
# Lancer tous les tests
pytest

# Tests avec couverture
pytest --cov=src --cov-report=html

# Tests specifiques
pytest tests/unit/domain/  # Tests domaine seulement
pytest tests/unit/application/  # Tests use cases seulement
```

### Statistiques actuelles
- **245 tests** unitaires
- **84%+ coverage** sur le code source

## Qualite du code

```bash
# Linting avec Ruff
ruff check src/ tests/

# Formatage
ruff format src/ tests/

# Type checking avec MyPy
mypy src/
```

## Concepts du domaine

### Etats des pages (Etat)

| Etat | Nombre d'ads | Description |
|------|--------------|-------------|
| XS   | 1-9          | Tres petit  |
| S    | 10-19        | Petit       |
| M    | 20-34        | Moyen       |
| L    | 35-79        | Grand       |
| XL   | 80-149       | Tres grand  |
| XXL  | 150+         | Enorme      |

### Criteres Winning Ads

Une annonce est "winning" si elle atteint un seuil de reach en fonction de son age :

| Age (jours) | Reach minimum |
|-------------|---------------|
| 4           | 15 000        |
| 5           | 20 000        |
| 6           | 30 000        |
| 7           | 40 000        |
| 8           | 50 000        |
| 15          | 100 000       |
| 22          | 200 000       |
| 29          | 400 000       |

## CI/CD

Le projet utilise GitHub Actions pour :
- Tests automatiques (Python 3.10, 3.11, 3.12)
- Verification de la couverture (minimum 84%)
- Linting avec Ruff
- Type checking avec MyPy
- Scan de securite avec Bandit

## Structure des exports CSV

### 1. Liste des pages (`liste_pages_*.csv`)
Pages Shopify avec >=15 ads : informations page, analyse web, classification.

### 2. Liste des annonces (`liste_ads_*.csv`)
Annonces des pages avec >=25 ads : details, contenu creatif, ciblage.

### 3. Suivi site (`suivi_site_*.csv`)
Donnees de monitoring : nombre d'ads actives, produits, date de scan.

## Dependances principales

- **Streamlit** : Framework dashboard
- **SQLAlchemy** : ORM et persistence
- **Pandas** : Traitement des donnees
- **Plotly** : Visualisations interactives
- **Pytest** : Framework de tests
- **Ruff** : Linting et formatage

## Licence

MIT License
