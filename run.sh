#!/bin/bash

# Load environment variables
if [ -f .env ]; then
    export $(cat .env | xargs)
fi

# Ensure directories exist
mkdir -p static/uploads

# Install dependencies
pip install -r requirements.txt

# Seed the database
python3 seed_db.py

# Run the application
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
