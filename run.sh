#!/bin/bash
if [ -f .env ]; then export $(cat .env | xargs); fi
mkdir -p static/uploads
pip install -r requirements.txt
python3 seed_db.py
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
