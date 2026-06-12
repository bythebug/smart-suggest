#!/bin/sh
set -e
mkdir -p /app/data
python seed.py
exec uvicorn app:app --host 0.0.0.0 --port 8000 --reload
