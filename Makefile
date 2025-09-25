.PHONY: dev prod build clean logs shell

# Development commands
dev:
	docker-compose up --build

dev-detached:
	docker-compose up -d --build

# Production commands
prod:
	docker-compose -f docker-compose.prod.yml up -d --build

prod-logs:
	docker-compose -f docker-compose.prod.yml logs -f

# Build commands
build:
	docker-compose build

build-prod:
	docker-compose -f docker-compose.prod.yml build

# Database commands
db-migrate:
	docker-compose exec backend alembic upgrade head

db-create-migration:
	docker-compose exec backend alembic revision --autogenerate -m "$(MESSAGE)"

db-reset:
	docker-compose down -v
	docker-compose up -d db redis
	sleep 5
	docker-compose exec backend alembic upgrade head

# Utility commands
logs:
	docker-compose logs -f

logs-backend:
	docker-compose logs -f backend

logs-worker:
	docker-compose logs -f worker

logs-frontend:
	docker-compose logs -f frontend

shell-backend:
	docker-compose exec backend bash

shell-worker:
	docker-compose exec worker bash

shell-db:
	docker-compose exec db psql -U mediaapp -d mediaapp

# Cleanup commands
clean:
	docker-compose down
	docker-compose rm -f
	docker volume prune -f

clean-all:
	docker-compose down -v
	docker system prune -af

# Health check
health:
	@echo "Checking services health..."
	@docker-compose ps
	@curl -s http://localhost:8000/health | jq '.' || echo "Backend not responding"
	@curl -s http://localhost:3000 > /dev/null && echo "Frontend: OK" || echo "Frontend: Not responding"

# Setup commands
setup-dev:
	cp .env.example .env
	@echo "Please edit .env file with your configuration"
	@echo "Then run: make dev"

setup-prod:
	@echo "Please create .env file with production configuration"
	@echo "Required variables: SECRET_KEY, POSTGRES_PASSWORD, ADMIN_PASSWORD"
	@echo "Then run: make prod"