#!/bin/bash
set -e
echo "Waiting for database..."
until pg_isready -h database -p 5432 -U kinesisuser; do
  echo "Database unavailable - sleeping"
  sleep 2
done
echo "Database ready."
# Step 2 will add: alembic upgrade head
echo "Starting Kinesis API..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8080
