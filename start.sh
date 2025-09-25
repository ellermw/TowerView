#!/bin/bash
set -e

echo "Starting TowerView..."

# Wait for database to be ready
echo "Waiting for database..."
while ! pg_isready -h ${DB_HOST:-db} -p ${DB_PORT:-5432} -U ${DB_USER:-mediaapp} > /dev/null 2>&1; do
    echo "Database not ready, waiting..."
    sleep 2
done
echo "Database is ready!"

# Run database migrations if needed
echo "Initializing database..."
cd /app/backend
python -c "
from app.core.database import engine, Base
from app.models import *
Base.metadata.create_all(bind=engine)
print('Database tables created/verified')
"

# Create initial admin user if needed
python -c "
import asyncio
from app.core.database import get_db
from app.services.auth_service import AuthService

async def create_admin():
    db = next(get_db())
    auth_service = AuthService(db)
    await auth_service.create_initial_admin()
    db.close()
    print('Admin user created/verified')

asyncio.run(create_admin())
"

# Start supervisor
echo "Starting services..."
exec /usr/bin/supervisord -c /etc/supervisor/conf.d/supervisord.conf