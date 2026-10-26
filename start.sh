#!/usr/bin/env bash
# Lance BookJob (API + interface) sur http://localhost:8000
cd "$(dirname "$0")/frontend"
[ -d node_modules ] || npm install
npm run build
cd ../backend
[ -d .venv ] || python3 -m venv .venv
. .venv/bin/activate
pip install -q -r requirements.txt
[ -f .env ] && set -a && . ./.env && set +a
python -m uvicorn app.main:app --port 8000
