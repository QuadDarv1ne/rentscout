# =============================================================================
# RentScout Makefile
# =============================================================================
# Расширенный Makefile для разработки, тестирования и деплоя.
# =============================================================================

.PHONY: help install dev clean test lint format build \
        docker-build docker-up docker-down docker-logs docker-clean \
        docker-restart docker-rebuild test-integration test-coverage \
        db-migrate db-reset db-backup db-restore \
        docs serve-docs metrics logs-tail backup-db restore-db \
        security-check deploy-staging deploy-production

# =============================================================================
# Help
# =============================================================================

help:
	@echo "RentScout - Makefile commands"
	@echo ""
	@echo "📦 Installation & Setup:"
	@echo "  install         - Install all dependencies"
	@echo "  dev             - Start development server with hot-reload"
	@echo "  clean           - Clean cache and build files"
	@echo ""
	@echo "🧪 Testing:"
	@echo "  test            - Run all tests"
	@echo "  test-coverage   - Run tests with coverage report"
	@echo "  test-watch      - Run tests in watch mode"
	@echo "  test-integration - Run integration tests"
	@echo "  test-fast       - Run tests without coverage (faster)"
	@echo ""
	@echo "📏 Code Quality:"
	@echo "  lint            - Run all linters"
	@echo "  lint-fix        - Auto-fix linting issues"
	@echo "  format          - Format code with black"
	@echo "  format-check    - Check code formatting"
	@echo "  type-check      - Run mypy type checker"
	@echo "  security-check  - Run security scanners (bandit, safety)"
	@echo ""
	@echo "🐳 Docker:"
	@echo "  docker-build    - Build Docker images"
	@echo "  docker-up       - Start all Docker services"
	@echo "  docker-down     - Stop all Docker services"
	@echo "  docker-logs     - View logs of all services"
	@echo "  docker-clean    - Remove all Docker containers and volumes"
	@echo "  docker-restart  - Restart all Docker services"
	@echo "  docker-rebuild  - Rebuild and restart Docker images"
	@echo "  docker-dev      - Start development Docker services"
	@echo ""
	@echo "🗄️  Database:"
	@echo "  db-migrate      - Run database migrations"
	@echo "  db-reset        - Reset and migrate database"
	@echo "  db-backup       - Backup database"
	@echo "  db-restore      - Restore database from backup"
	@echo "  db-shell        - Open database shell"
	@echo ""
	@echo "📚 Documentation:"
	@echo "  docs            - Generate documentation"
	@echo "  serve-docs      - Serve documentation locally"
	@echo ""
	@echo "🔧 Utilities:"
	@echo "  metrics         - Open metrics dashboard"
	@echo "  logs-tail       - Tail logs in real-time"
	@echo "  backup-db       - Backup database"
	@echo "  restore-db      - Restore database from backup"
	@echo "  shell           - Open Python shell"
	@echo ""
	@echo "🚀 Deployment:"
	@echo "  deploy-staging  - Deploy to staging environment"
	@echo "  deploy-production - Deploy to production environment"
	@echo "  deploy          - Deploy based on current branch"

# =============================================================================
# Installation & Setup
# =============================================================================

install:
	@echo "📦 Installing dependencies..."
	pip install -r requirements.txt
	pip install -r requirements-dev.txt
	pre-commit install
	@echo "✅ Installation complete!"

dev:
	@echo "🚀 Starting development server..."
	uvicorn app.main:app --reload --host 0.0.0.0 --port 8000 --log-level debug

# =============================================================================
# Testing
# =============================================================================

test:
	@echo "🧪 Running tests..."
	pytest tests/ -v --tb=short

test-coverage:
	@echo "🧪 Running tests with coverage..."
	pytest tests/ -v --cov=app --cov-report=html --cov-report=term-missing
	@echo "📊 Coverage report generated in htmlcov/index.html"
	@echo "🌐 Opening coverage report..."
	@start htmlcov/index.html 2>/dev/null || open htmlcov/index.html 2>/dev/null || echo "Open htmlcov/index.html in browser"

test-watch:
	@echo "👁️  Running tests in watch mode..."
	ptw -- --cov=app tests/

test-integration:
	@echo "🔗 Running integration tests..."
	pytest tests/integration/ -v --tb=short

test-fast:
	@echo "⚡ Running tests (fast mode, no coverage)..."
	pytest tests/ -v --tb=short -n auto

# =============================================================================
# Code Quality
# =============================================================================

lint:
	@echo "📏 Running linters..."
	ruff check app/ tests/
	mypy app/ --ignore-missing-imports

lint-fix:
	@echo "🔧 Auto-fixing lint issues..."
	ruff check app/ tests/ --fix
	isort app/ tests/

format:
	@echo "🎨 Formatting code..."
	black app/ tests/
	isort app/ tests/

format-check:
	@echo "🔍 Checking code formatting..."
	black --check app/ tests/
	isort --check-only app/ tests/

type-check:
	@echo "🔍 Running type checker..."
	mypy app/ --ignore-missing-imports --pretty

security-check:
	@echo "🔒 Running security scanners..."
	bandit -r app/ -ll
	safety check -r requirements.txt
	pip-audit -r requirements.txt || true

# =============================================================================
# Docker
# =============================================================================

docker-build:
	@echo "🐳 Building Docker images..."
	docker-compose build

docker-up:
	@echo "🚀 Starting Docker services..."
	docker-compose up -d
	@echo "✅ Services started!"
	@echo "📍 API: http://localhost:8000"
	@echo "📍 Docs: http://localhost:8000/docs"
	@echo "📍 Prometheus: http://localhost:9091"
	@echo "📍 Grafana: http://localhost:3001"

docker-down:
	@echo "🛑 Stopping Docker services..."
	docker-compose down

docker-logs:
	@echo "📋 Viewing Docker logs..."
	docker-compose logs -f

docker-clean:
	@echo "🧹 Cleaning Docker..."
	docker-compose down -v
	docker system prune -f

docker-restart:
	@echo "🔄 Restarting Docker services..."
	docker-compose restart

docker-rebuild:
	@echo "🔄 Rebuilding Docker images..."
	docker-compose down
	docker-compose build --no-cache
	docker-compose up -d

docker-dev:
	@echo "🚀 Starting development Docker services..."
	docker-compose -f docker-compose.dev.yml up -d

# =============================================================================
# Database
# =============================================================================

db-migrate:
	@echo "🗄️  Running database migrations..."
	alembic upgrade head

db-reset:
	@echo "⚠️  Resetting database..."
	alembic downgrade base
	alembic upgrade head
	@echo "✅ Database reset complete!"

db-backup:
	@echo "💾 Backing up database..."
	@mkdir -p backups
	docker exec rentscout-postgres pg_dump -U rentscout rentscout > backups/db_backup_$$(date +%Y%m%d_%H%M%S).sql
	@echo "✅ Backup created in backups/"

db-restore:
	@echo "⚠️  Restoring database from backup..."
	@ls -t backups/*.sql | head -1 | xargs -I {} docker exec -i rentscout-postgres psql -U rentscout -d rentscout < {}
	@echo "✅ Database restored!"

db-shell:
	@echo "🗄️  Opening database shell..."
	docker exec -it rentscout-postgres psql -U rentscout -d rentscout

# =============================================================================
# Documentation
# =============================================================================

docs:
	@echo "📚 Generating documentation..."
	@mkdir -p docs/generated
	pdoc --html --output-dir docs/generated app/

serve-docs:
	@echo "📖 Serving documentation..."
	mkdocs serve

# =============================================================================
# Utilities
# =============================================================================

metrics:
	@echo "📊 Opening metrics dashboard..."
	@echo "Prometheus: http://localhost:9091"
	@echo "Grafana: http://localhost:3001"
	@start http://localhost:9091 2>/dev/null || open http://localhost:9091 2>/dev/null || echo "Open http://localhost:9091 in browser"

logs-tail:
	@echo "📋 Tailing logs in real-time..."
	tail -f logs/*.log

shell:
	@echo "🐍 Opening Python shell..."
	python -c "import code; code.interact(local=dict(globals(), **locals()))"

backup-db: db-backup

restore-db: db-restore

# =============================================================================
# Deployment
# =============================================================================

deploy-staging:
	@echo "🚀 Deploying to staging..."
	git push origin develop
	@echo "✅ Deployed to staging!"
	@echo "📍 Staging URL: https://staging.rentscout.dev"

deploy-production:
	@echo "🚀 Deploying to production..."
	git push origin main
	@echo "✅ Deployed to production!"
	@echo "📍 Production URL: https://api.rentscout.dev"

deploy:
	@echo "🚀 Deploying..."
	@if [ "$$(git rev-parse --abbrev-ref HEAD)" = "develop" ]; then \
		$(MAKE) deploy-staging; \
	elif [ "$$(git rev-parse --abbrev-ref HEAD)" = "main" ]; then \
		$(MAKE) deploy-production; \
	else \
		echo "❌ Deploy only from 'main' or 'develop' branch"; \
		exit 1; \
	fi

# =============================================================================
# Pre-commit hooks
# =============================================================================

pre-commit-install:
	@echo "🔧 Installing pre-commit hooks..."
	pre-commit install

pre-commit-run:
	@echo "🔍 Running pre-commit hooks..."
	pre-commit run --all-files

# =============================================================================
# CI/CD helpers
# =============================================================================

ci-test:
	@echo "🧪 Running CI tests..."
	pytest tests/ -v --cov=app --cov-report=xml --tb=short

ci-lint:
	@echo "📏 Running CI lint..."
	black --check app/ tests/
	ruff check app/ tests/
	mypy app/ --ignore-missing-imports

ci-security:
	@echo "🔒 Running CI security checks..."
	bandit -r app/ -ll -f json -o bandit-report.json || true
	safety check -r requirements.txt --json > safety-report.json || true

# =============================================================================
# Quick commands
# =============================================================================

q: clean
	@echo "⚡ Quick clean done!"

qa: lint test
	@echo "✅ Quality assurance complete!"

qb: docker-build docker-up
	@echo "✅ Quick build and start complete!"
