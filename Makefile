# Kulya — one command per job. Needs GNU make, Python 3.12+, Flutter 3.x.
# Loads .env if present (never committed).
-include .env
export

PY ?= python
APP = frontend/kulya_app

.PHONY: setup test lint run seed demo docs

setup:
	cd backend && $(PY) -m pip install -r requirements.txt
	cd backend && $(PY) manage.py migrate
	cd $(APP) && flutter pub get

test:
	cd backend && LLM_PROVIDER=mock $(PY) -m pytest -q
	cd $(APP) && flutter test

lint:
	cd backend && $(PY) -m ruff check . && $(PY) -m black --check .
	cd $(APP) && flutter analyze

# Builds the web app, then serves API + app together at http://localhost:8000 (needs DJANGO_DEBUG=true).
run:
	cd $(APP) && flutter build web
	cd backend && $(PY) manage.py runserver

docs:
	cd backend && $(PY) gen_api_md.py

# Implemented by the rules_data role (task R4).
seed:
	cd backend && $(PY) manage.py seed_demo --approve-facts

# Implemented by the devops role (task D4).
demo:
	DEMO_MODE=true LLM_PROVIDER=mock docker compose up --build
