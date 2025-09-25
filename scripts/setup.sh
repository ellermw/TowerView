#!/bin/bash

# Towerview Setup Script

set -e

echo "🎬 Welcome to Towerview Setup!"
echo "================================"

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    echo "❌ Docker is not installed. Please install Docker first."
    exit 1
fi

if ! command -v docker-compose &> /dev/null; then
    echo "❌ Docker Compose is not installed. Please install Docker Compose first."
    exit 1
fi

echo "✅ Docker and Docker Compose are installed"

# Create .env file if it doesn't exist
if [ ! -f .env ]; then
    echo "📝 Creating .env file..."
    cp .env.example .env

    # Generate secret key
    SECRET_KEY=$(openssl rand -base64 32)
    sed -i "s/your-very-secure-secret-key-here/$SECRET_KEY/" .env

    # Generate admin password
    ADMIN_PASSWORD=$(openssl rand -base64 16)
    sed -i "s/secure_password_here/$ADMIN_PASSWORD/" .env

    echo "✅ .env file created with random secrets"
    echo "🔐 Admin credentials: admin / $ADMIN_PASSWORD"
    echo "📝 Please review and update .env file as needed"
else
    echo "✅ .env file already exists"
fi

# Setup mode selection
echo ""
echo "Choose setup mode:"
echo "1) Development (with hot reload)"
echo "2) Production (optimized)"
read -p "Enter choice [1-2]: " choice

case $choice in
    1)
        echo "🚀 Starting development environment..."
        docker-compose up --build -d
        ;;
    2)
        echo "🚀 Starting production environment..."
        docker-compose -f docker-compose.prod.yml up --build -d
        ;;
    *)
        echo "❌ Invalid choice"
        exit 1
        ;;
esac

echo ""
echo "⏳ Waiting for services to start..."
sleep 10

# Wait for database and run migrations
echo "📊 Running database migrations..."
docker-compose exec -T backend alembic upgrade head

echo ""
echo "✅ Setup complete!"
echo ""
echo "🌐 Access the application:"
echo "   Frontend: http://localhost:3000"
echo "   Backend API: http://localhost:8000"
echo "   API Docs: http://localhost:8000/docs"
echo ""
echo "🔐 Default admin login:"
echo "   Username: admin"
echo "   Password: Check .env file for ADMIN_PASSWORD"
echo ""
echo "📚 Useful commands:"
echo "   make logs          - View all logs"
echo "   make logs-backend  - View backend logs"
echo "   make clean         - Stop and clean up"
echo "   make health        - Check service health"