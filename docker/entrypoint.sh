#!/bin/bash
set -e

echo "Waiting for postgres..."
until python -c "
import asyncio, asyncpg, os, sys
async def check():
    try:
        conn = await asyncpg.connect(
            host=os.environ.get('DB_HOST', 'postgres'),
            port=int(os.environ.get('DB_PORT', '5432')),
            user=os.environ.get('DB_USER', 'jobseeker'),
            password=os.environ.get('DB_PASSWORD', 'jobseeker_secret'),
            database=os.environ.get('DB_NAME', 'jobseeker'),
        )
        await conn.close()
    except Exception:
        sys.exit(1)
asyncio.run(check())
" 2>/dev/null; do
    sleep 1
done
echo "PostgreSQL is ready."

echo "Running migrations..."
alembic upgrade head

exec "$@"
