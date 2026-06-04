.PHONY: up down demo test gate benchmark logs clean

# ─────────────────────────────────────────────────────────────────────────────
# AegisStream Makefile
# ─────────────────────────────────────────────────────────────────────────────

up:
	@echo "🚀 Starting AegisStream stack..."
	docker compose up --build -d
	@echo ""
	@echo "  Dashboard → http://localhost:8501"
	@echo "  API       → http://localhost:8000"
	@echo "  API Docs  → http://localhost:8000/docs"
	@echo ""
	@echo "Run 'make demo' to seed demo data."

down:
	@echo "🛑 Stopping AegisStream..."
	docker compose down -v

demo:
	@echo "🌱 Seeding demo data (500 events)..."
	docker compose exec api python scripts/seed_demo_data.py
	@echo "✅ Demo data seeded. Open http://localhost:8501"

test:
	@echo "🧪 Running tests..."
	docker compose exec api python -m pytest tests/ -v

gate:
	@echo "🔍 Running deployment gate..."
	docker compose exec api python scripts/deployment_gate.py

benchmark:
	@echo "📊 Running research experiments..."
	docker compose exec api python scripts/run_experiments.py --output /data/experiment_results.json

logs:
	docker compose logs -f evaluator producer

clean:
	docker compose down -v --rmi local
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
