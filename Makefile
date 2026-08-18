.PHONY: help setup up down migrate seed run test lint fmt typecheck check vendor-htmx

HTMX_VERSION := 2.0.4

help:
	@grep -E '^[a-zA-Z-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-14s\033[0m %s\n", $$1, $$2}'

setup:  ## Instala dependências e cria .env a partir do exemplo
	uv sync
	@test -f .env || (cp .env.example .env && echo "Criado .env — gere um SECRET_KEY antes de usar em produção.")

up:  ## Sobe PostgreSQL e Redis
	docker compose up -d
	@echo "Aguardando o banco..."
	@until docker compose exec -T db pg_isready -U buddhadharma >/dev/null 2>&1; do sleep 1; done
	@echo "Pronto."

down:  ## Derruba os containers
	docker compose down

migrate:  ## Aplica as migrações
	uv run python manage.py migrate

seed:  ## Popula categorias e emojis iniciais
	uv run python manage.py seed_forum

run:  ## Servidor de desenvolvimento
	uv run python manage.py runserver

test:  ## Roda a suíte
	DJANGO_SETTINGS_MODULE=config.settings.test uv run pytest

test-fast:  ## Só os testes que não precisam de banco
	DJANGO_SETTINGS_MODULE=config.settings.test uv run pytest -m "not django_db" -p no:cacheprovider

lint:  ## Lint
	uv run ruff check .

fmt:  ## Formata
	uv run ruff format .
	uv run ruff check . --fix

typecheck:  ## Checagem de tipos
	uv run mypy apps config

check:  ## Tudo que o CI roda
	uv run ruff check .
	uv run python manage.py check
	uv run python manage.py makemigrations --check --dry-run
	DJANGO_SETTINGS_MODULE=config.settings.test uv run pytest

vendor-htmx:  ## Baixa o HTMX para static/js (usado a partir da Fase 2)
	@mkdir -p static/js
	curl -fsSL -o static/js/htmx.min.js \
		https://unpkg.com/htmx.org@$(HTMX_VERSION)/dist/htmx.min.js
	@echo "HTMX $(HTMX_VERSION) em static/js/htmx.min.js — confira o hash antes de commitar."
