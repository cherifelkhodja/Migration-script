# Meta Ads Analyzer - API Documentation

Documentation complete de l'API REST du Meta Ads Analyzer.

## Base URL

```
http://localhost:8000/api/v1
```

## Authentification

L'API utilise des **JWT tokens**. Incluez le token dans le header `Authorization`:

```bash
Authorization: Bearer <access_token>
```

### Obtenir un token

```bash
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "password123"}'
```

**Reponse:**
```json
{
  "access_token": "eyJ...",
  "refresh_token": "eyJ...",
  "token_type": "bearer",
  "expires_in": 1800
}
```

---

## Endpoints

### Authentication (`/auth`)

#### POST /auth/login
Authentifie un utilisateur et retourne les tokens JWT.

```bash
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "john", "password": "secret123"}'
```

#### POST /auth/refresh
Rafraichit l'access token avec le refresh token.

```bash
curl -X POST http://localhost:8000/api/v1/auth/refresh \
  -H "Content-Type: application/json" \
  -d '{"refresh_token": "eyJ..."}'
```

#### GET /auth/me
Retourne le profil de l'utilisateur authentifie.

```bash
curl http://localhost:8000/api/v1/auth/me \
  -H "Authorization: Bearer $TOKEN"
```

#### POST /auth/forgot-password
Demande un reset de mot de passe (envoie un email).

```bash
curl -X POST http://localhost:8000/api/v1/auth/forgot-password \
  -H "Content-Type: application/json" \
  -d '{"email": "user@example.com"}'
```

#### POST /auth/reset-password
Execute le reset avec le token recu par email.

```bash
curl -X POST http://localhost:8000/api/v1/auth/reset-password \
  -H "Content-Type: application/json" \
  -d '{"token": "abc123...", "new_password": "NewSecureP@ss123"}'
```

---

### Ads Search (`/ads`)

#### POST /ads/search
Recherche des annonces Meta par mots-cles.

```bash
curl -X POST http://localhost:8000/api/v1/ads/search \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "keywords": ["bijoux", "montres"],
    "countries": ["FR"],
    "languages": ["fr"],
    "min_ads": 3,
    "exclude_blacklisted": true
  }'
```

**Reponse:**
```json
{
  "pages": [
    {
      "page_id": "123456",
      "page_name": "Bijoux Paris",
      "ads_count": 5,
      "ads": [...],
      "keywords_found": ["bijoux"]
    }
  ],
  "total_ads_found": 150,
  "unique_ads_count": 45,
  "pages_count": 12,
  "search_duration_ms": 3500,
  "keywords_stats": {"bijoux": 80, "montres": 70}
}
```

#### GET /ads/winning
Liste les winning ads avec pagination.

```bash
curl "http://localhost:8000/api/v1/ads/winning?page=1&page_size=20" \
  -H "Authorization: Bearer $TOKEN"
```

#### GET /ads/winning/{id}
Recupere une winning ad par son ID.

```bash
curl http://localhost:8000/api/v1/ads/winning/42 \
  -H "Authorization: Bearer $TOKEN"
```

#### DELETE /ads/winning/{id}
Supprime une winning ad.

```bash
curl -X DELETE http://localhost:8000/api/v1/ads/winning/42 \
  -H "Authorization: Bearer $TOKEN"
```

---

### Website Analysis (`/websites`)

#### POST /websites/analyze
Analyse un site e-commerce (detection CMS, comptage produits).

```bash
curl -X POST http://localhost:8000/api/v1/websites/analyze \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://example-shop.com",
    "country_code": "FR"
  }'
```

**Reponse:**
```json
{
  "url": "https://example-shop.com",
  "is_success": true,
  "cms": "Shopify",
  "theme": "Dawn",
  "product_count": 245,
  "currency": "EUR",
  "analyzed_at": "2024-01-15T10:30:00Z"
}
```

#### POST /websites/analyze/batch
Analyse plusieurs sites en batch (max 50).

```bash
curl -X POST http://localhost:8000/api/v1/websites/analyze/batch \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "urls": [
      "https://shop1.com",
      "https://shop2.com",
      "https://shop3.com"
    ],
    "country_code": "FR",
    "max_concurrent": 5
  }'
```

---

### Pages/Shops (`/pages`)

#### GET /pages
Liste les pages avec pagination et filtres.

```bash
# Liste simple
curl "http://localhost:8000/api/v1/pages?page=1&page_size=20" \
  -H "Authorization: Bearer $TOKEN"

# Avec filtres
curl "http://localhost:8000/api/v1/pages?etat=L,XL&cms=Shopify&is_favorite=true" \
  -H "Authorization: Bearer $TOKEN"

# Recherche textuelle
curl "http://localhost:8000/api/v1/pages?query=bijoux" \
  -H "Authorization: Bearer $TOKEN"
```

**Parametres de filtre:**
- `etat`: L, XL, XXL (separes par virgule)
- `cms`: Shopify, WooCommerce, etc.
- `category`: Categorie de produits
- `is_favorite`: true/false
- `is_blacklisted`: true/false
- `query`: Recherche textuelle
- `order_by`: Champ de tri (default: updated_at)
- `descending`: true/false

#### GET /pages/stats
Retourne les statistiques globales.

```bash
curl http://localhost:8000/api/v1/pages/stats \
  -H "Authorization: Bearer $TOKEN"
```

**Reponse:**
```json
{
  "total_pages": 1250,
  "total_with_website": 980,
  "total_with_cms": 750,
  "total_favorites": 45,
  "total_blacklisted": 120,
  "etat_distribution": {"L": 500, "XL": 300, "XXL": 100},
  "cms_distribution": {"Shopify": 600, "WooCommerce": 150},
  "category_distribution": {"Fashion": 400, "Electronics": 200}
}
```

#### GET /pages/{page_id}
Recupere une page par son ID.

```bash
curl http://localhost:8000/api/v1/pages/123456789 \
  -H "Authorization: Bearer $TOKEN"
```

#### POST /pages
Cree une nouvelle page.

```bash
curl -X POST http://localhost:8000/api/v1/pages \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "page_id": "123456789",
    "name": "Ma Boutique",
    "website": "https://maboutique.com"
  }'
```

#### PUT /pages/{page_id}
Met a jour une page.

```bash
curl -X PUT http://localhost:8000/api/v1/pages/123456789 \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "category": "Fashion",
    "subcategory": "Jewelry"
  }'
```

#### DELETE /pages/{page_id}
Supprime une page.

```bash
curl -X DELETE http://localhost:8000/api/v1/pages/123456789 \
  -H "Authorization: Bearer $TOKEN"
```

#### PUT /pages/{page_id}/classification
Met a jour la classification d'une page.

```bash
curl -X PUT http://localhost:8000/api/v1/pages/123456789/classification \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "category": "Fashion",
    "subcategory": "Jewelry",
    "confidence": 0.95
  }'
```

#### PUT /pages/{page_id}/favorite
Toggle le statut favori.

```bash
curl -X PUT http://localhost:8000/api/v1/pages/123456789/favorite \
  -H "Authorization: Bearer $TOKEN"
```

#### PUT /pages/{page_id}/blacklist
Toggle le statut blacklist.

```bash
curl -X PUT http://localhost:8000/api/v1/pages/123456789/blacklist \
  -H "Authorization: Bearer $TOKEN"
```

---

### Users (`/users`) - Admin Only

#### GET /users
Liste les utilisateurs (admin seulement).

```bash
curl "http://localhost:8000/api/v1/users?page=1&role=analyst" \
  -H "Authorization: Bearer $ADMIN_TOKEN"
```

#### POST /users
Cree un nouvel utilisateur.

```bash
curl -X POST http://localhost:8000/api/v1/users \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "username": "newuser",
    "email": "newuser@example.com",
    "password": "SecurePass123",
    "role": "analyst"
  }'
```

**Roles disponibles:** `admin`, `analyst`, `viewer`

#### PUT /users/{id}
Met a jour un utilisateur.

```bash
curl -X PUT http://localhost:8000/api/v1/users/uuid-here \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "role": "admin",
    "is_active": true
  }'
```

#### DELETE /users/{id}
Supprime un utilisateur.

```bash
curl -X DELETE http://localhost:8000/api/v1/users/uuid-here \
  -H "Authorization: Bearer $ADMIN_TOKEN"
```

#### PUT /users/{id}/password
Change le mot de passe (utilisateur ou admin).

```bash
curl -X PUT http://localhost:8000/api/v1/users/uuid-here/password \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "current_password": "OldPass123",
    "new_password": "NewSecurePass456"
  }'
```

---

### Collections (`/collections`)

#### GET /collections
Liste toutes les collections.

```bash
curl http://localhost:8000/api/v1/collections \
  -H "Authorization: Bearer $TOKEN"
```

#### GET /collections/{id}
Recupere une collection avec ses pages.

```bash
curl http://localhost:8000/api/v1/collections/1 \
  -H "Authorization: Bearer $TOKEN"
```

**Reponse:**
```json
{
  "id": 1,
  "name": "Winning Shops",
  "description": "Mes meilleurs shops",
  "page_ids": ["123", "456", "789"],
  "page_count": 3,
  "created_at": "2024-01-10T10:00:00Z"
}
```

#### POST /collections
Cree une nouvelle collection.

```bash
curl -X POST http://localhost:8000/api/v1/collections \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Ma Collection",
    "description": "Description optionnelle"
  }'
```

#### PUT /collections/{id}
Met a jour une collection.

```bash
curl -X PUT http://localhost:8000/api/v1/collections/1 \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name": "Nouveau Nom"}'
```

#### DELETE /collections/{id}
Supprime une collection.

```bash
curl -X DELETE http://localhost:8000/api/v1/collections/1 \
  -H "Authorization: Bearer $TOKEN"
```

#### POST /collections/{id}/pages
Ajoute une page a une collection.

```bash
curl -X POST http://localhost:8000/api/v1/collections/1/pages \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"page_id": "123456789"}'
```

#### DELETE /collections/{id}/pages/{page_id}
Retire une page d'une collection.

```bash
curl -X DELETE http://localhost:8000/api/v1/collections/1/pages/123456789 \
  -H "Authorization: Bearer $TOKEN"
```

---

### Billing (`/billing`)

#### POST /billing/checkout
Cree une session de paiement Stripe.

```bash
curl -X POST http://localhost:8000/api/v1/billing/checkout \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "plan": "pro",
    "success_url": "https://app.com/success",
    "cancel_url": "https://app.com/cancel"
  }'
```

**Plans disponibles:** `starter`, `pro`, `enterprise`

#### GET /billing/subscription
Retourne le statut d'abonnement.

```bash
curl http://localhost:8000/api/v1/billing/subscription \
  -H "Authorization: Bearer $TOKEN"
```

#### POST /billing/portal
Cree un lien vers le portail client Stripe.

```bash
curl -X POST http://localhost:8000/api/v1/billing/portal \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"return_url": "https://app.com/settings"}'
```

---

### OAuth (`/oauth`)

#### GET /oauth/google
Initie le flux OAuth Google (redirect).

```bash
# Ouvre dans le navigateur
open http://localhost:8000/api/v1/oauth/google
```

#### GET /oauth/github
Initie le flux OAuth GitHub (redirect).

```bash
open http://localhost:8000/api/v1/oauth/github
```

---

## Codes d'erreur

| Code | Description |
|------|-------------|
| 400 | Bad Request - Donnees invalides |
| 401 | Unauthorized - Token manquant ou invalide |
| 403 | Forbidden - Permissions insuffisantes |
| 404 | Not Found - Ressource non trouvee |
| 409 | Conflict - Ressource existe deja |
| 500 | Internal Server Error |

**Format des erreurs:**
```json
{
  "detail": "Message d'erreur descriptif"
}
```

---

## Rate Limiting

- **Recherche ads:** 10 requetes/minute
- **Analyse websites:** 30 requetes/minute
- **Autres endpoints:** 100 requetes/minute

---

## Swagger UI

Documentation interactive disponible a:
- **Swagger UI:** http://localhost:8000/docs
- **ReDoc:** http://localhost:8000/redoc
- **OpenAPI JSON:** http://localhost:8000/openapi.json
