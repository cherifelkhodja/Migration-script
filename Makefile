# Makefile pour Meta Ads Analyzer
# Usage: make [commande]

.PHONY: help build up down restart logs shell db-shell clean prune dev install test

# Variables
COMPOSE = docker-compose
APP_CONTAINER = meta_ads_app
DB_CONTAINER = meta_ads_db

# Couleurs pour l'affichage
BLUE = \033[0;34m
GREEN = \033[0;32m
YELLOW = \033[0;33m
NC = \033[0m # No Color

# ═══════════════════════════════════════════════════════════════════════════════
# AIDE
# ═══════════════════════════════════════════════════════════════════════════════

help: ## Affiche cette aide
	@echo "$(BLUE)═══════════════════════════════════════════════════════════════$(NC)"
	@echo "$(GREEN)Meta Ads Analyzer - Commandes disponibles$(NC)"
	@echo "$(BLUE)═══════════════════════════════════════════════════════════════$(NC)"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  $(YELLOW)%-15s$(NC) %s\n", $$1, $$2}'
	@echo ""

# ═══════════════════════════════════════════════════════════════════════════════
# DOCKER - BUILD
# ═══════════════════════════════════════════════════════════════════════════════

build: ## Build les images Docker
	@echo "$(GREEN)Building Docker images...$(NC)"
	$(COMPOSE) build

build-no-cache: ## Build les images sans cache
	@echo "$(GREEN)Building Docker images (no cache)...$(NC)"
	$(COMPOSE) build --no-cache

# ═══════════════════════════════════════════════════════════════════════════════
# DOCKER - UP/DOWN
# ═══════════════════════════════════════════════════════════════════════════════

up: ## Démarre les containers en arrière-plan
	@echo "$(GREEN)Starting containers...$(NC)"
	$(COMPOSE) up -d
	@echo "$(GREEN)Application disponible sur http://localhost:8501$(NC)"

up-logs: ## Démarre les containers avec les logs
	@echo "$(GREEN)Starting containers with logs...$(NC)"
	$(COMPOSE) up

up-build: ## Build et démarre les containers
	@echo "$(GREEN)Building and starting containers...$(NC)"
	$(COMPOSE) up -d --build
	@echo "$(GREEN)Application disponible sur http://localhost:8501$(NC)"

down: ## Arrête les containers
	@echo "$(YELLOW)Stopping containers...$(NC)"
	$(COMPOSE) down

down-v: ## Arrête les containers et supprime les volumes
	@echo "$(YELLOW)Stopping containers and removing volumes...$(NC)"
	$(COMPOSE) down -v

restart: ## Redémarre les containers
	@echo "$(YELLOW)Restarting containers...$(NC)"
	$(COMPOSE) restart

restart-app: ## Redémarre uniquement l'application
	@echo "$(YELLOW)Restarting app container...$(NC)"
	$(COMPOSE) restart app

# ═══════════════════════════════════════════════════════════════════════════════
# DOCKER - LOGS & STATUS
# ═══════════════════════════════════════════════════════════════════════════════

logs: ## Affiche les logs de tous les containers
	$(COMPOSE) logs -f

logs-app: ## Affiche les logs de l'application
	$(COMPOSE) logs -f app

logs-db: ## Affiche les logs de la base de données
	$(COMPOSE) logs -f db

ps: ## Affiche le statut des containers
	$(COMPOSE) ps

# ═══════════════════════════════════════════════════════════════════════════════
# DOCKER - SHELL
# ═══════════════════════════════════════════════════════════════════════════════

shell: ## Ouvre un shell dans le container app
	@echo "$(GREEN)Opening shell in app container...$(NC)"
	docker exec -it $(APP_CONTAINER) /bin/bash

db-shell: ## Ouvre un shell PostgreSQL
	@echo "$(GREEN)Opening PostgreSQL shell...$(NC)"
	docker exec -it $(DB_CONTAINER) psql -U postgres -d meta_ads

# ═══════════════════════════════════════════════════════════════════════════════
# DATABASE
# ═══════════════════════════════════════════════════════════════════════════════

db-backup: ## Sauvegarde la base de données
	@echo "$(GREEN)Backing up database...$(NC)"
	@mkdir -p backups
	docker exec $(DB_CONTAINER) pg_dump -U postgres meta_ads > backups/backup_$$(date +%Y%m%d_%H%M%S).sql
	@echo "$(GREEN)Backup saved to backups/$(NC)"

db-restore: ## Restaure la base de données (usage: make db-restore FILE=backups/backup.sql)
	@echo "$(YELLOW)Restoring database from $(FILE)...$(NC)"
	docker exec -i $(DB_CONTAINER) psql -U postgres -d meta_ads < $(FILE)

db-reset: ## Réinitialise la base de données (ATTENTION: supprime toutes les données)
	@echo "$(YELLOW)Resetting database...$(NC)"
	docker exec -i $(DB_CONTAINER) psql -U postgres -c "DROP DATABASE IF EXISTS meta_ads;"
	docker exec -i $(DB_CONTAINER) psql -U postgres -c "CREATE DATABASE meta_ads;"
	@echo "$(GREEN)Database reset complete$(NC)"

# ═══════════════════════════════════════════════════════════════════════════════
# NETTOYAGE
# ═══════════════════════════════════════════════════════════════════════════════

clean: ## Nettoie les fichiers temporaires Python
	@echo "$(YELLOW)Cleaning Python cache...$(NC)"
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	find . -type f -name "*.pyo" -delete 2>/dev/null || true

prune: ## Nettoie les ressources Docker non utilisées
	@echo "$(YELLOW)Pruning Docker resources...$(NC)"
	docker system prune -f

prune-all: ## Nettoie tout Docker (images, volumes, etc.)
	@echo "$(YELLOW)Pruning all Docker resources...$(NC)"
	docker system prune -a -f --volumes

# ═══════════════════════════════════════════════════════════════════════════════
# DÉVELOPPEMENT LOCAL (sans Docker)
# ═══════════════════════════════════════════════════════════════════════════════

install: ## Installe les dépendances Python
	@echo "$(GREEN)Installing Python dependencies...$(NC)"
	pip install -r requirements.txt

dev: ## Lance l'application en mode développement (sans Docker)
	@echo "$(GREEN)Starting app in dev mode...$(NC)"
	@echo "$(YELLOW)Note: Assurez-vous que PostgreSQL est lancé localement$(NC)"
	streamlit run app/dashboard.py

run: ## Alias pour 'make dev'
	$(MAKE) dev

# ═══════════════════════════════════════════════════════════════════════════════
# SETUP INITIAL
# ═══════════════════════════════════════════════════════════════════════════════

setup: ## Configuration initiale du projet
	@echo "$(GREEN)Setting up project...$(NC)"
	@if [ ! -f .env ]; then \
		cp .env.example .env; \
		echo "$(YELLOW).env créé - Éditez-le avec votre token Meta$(NC)"; \
	else \
		echo "$(YELLOW).env existe déjà$(NC)"; \
	fi
	@mkdir -p résultats backups
	@echo "$(GREEN)Setup complete!$(NC)"
	@echo ""
	@echo "Prochaines étapes:"
	@echo "  1. Éditez .env avec votre META_ACCESS_TOKEN"
	@echo "  2. Lancez: make up-build"
	@echo "  3. Ouvrez: http://localhost:8501"
