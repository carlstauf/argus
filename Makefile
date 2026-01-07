# ARGUS Makefile
# Quick commands for common operations

.PHONY: help setup init install clean run live dashboard query test

help:
	@echo "ARGUS - The All-Seeing Intelligence Layer"
	@echo ""
	@echo "Available commands:"
	@echo "  make setup      - Full setup (venv + install + init db)"
	@echo "  make install    - Install Python dependencies"
	@echo "  make init       - Initialize database schema"
	@echo "  make live       - Launch LIVE terminal (recommended) 🔴"
	@echo "  make run        - Start ingestion (background mode)"
	@echo "  make dashboard  - Launch static dashboard"
	@echo "  make query      - Run intelligence queries"
	@echo "  make test       - Test API connectivity"
	@echo "  make clean      - Clean up generated files"
	@echo ""

setup: install init
	@echo "✓ Setup complete! Run 'make live' to launch the LIVE terminal."

install:
	@echo "Installing dependencies..."
	pip install -r requirements.txt

init:
	@echo "Initializing database..."
	python argus.py init

live:
	@echo "Launching LIVE terminal..."
	python argus.py live

run:
	@echo "Starting ARGUS ingestion (background)..."
	python argus.py ingest

dashboard:
	@echo "Launching static dashboard..."
	python argus.py dashboard

query:
	@echo "Available queries:"
	@echo "  fresh   - Fresh wallets with large bets"
	@echo "  insider - Insider trading patterns"
	@echo "  copy    - Copy leaderboard"
	@echo "  whale   - Whale movements"
	@echo "  anomaly - Statistical anomalies"
	@echo "  gap     - Reality gap opportunities"
	@echo ""
	@echo "Usage: make query-fresh"

query-fresh:
	python argus.py query fresh

query-insider:
	python argus.py query insider

query-copy:
	python argus.py query copy

query-whale:
	python argus.py query whale

query-anomaly:
	python argus.py query anomaly

query-gap:
	python argus.py query gap

test:
	@echo "Testing Polymarket API connectivity..."
	python test_api.py

clean:
	@echo "Cleaning up..."
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	rm -rf .pytest_cache
	@echo "✓ Cleaned"
