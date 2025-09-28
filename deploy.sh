#!/bin/bash

# TowerView Production Deployment Script

set -e  # Exit on error

echo "======================================"
echo "   TowerView Production Deployment"
echo "======================================"
echo ""

# Check if .env exists
if [ ! -f .env ]; then
    echo "Creating .env file with secure defaults..."

    # Generate secure passwords
    DB_PASSWORD=$(openssl rand -base64 32)
    SECRET_KEY=$(openssl rand -base64 64)
    ADMIN_PASSWORD=$(openssl rand -base64 16)

    cat > .env << EOF
# Auto-generated on $(date)
# Database
DB_PASSWORD=$DB_PASSWORD

# App Security
SECRET_KEY=$SECRET_KEY

# Admin Account (CHANGE THIS!)
ADMIN_USERNAME=admin
ADMIN_PASSWORD=$ADMIN_PASSWORD

# Timezone
TZ=UTC

# Ports
HTTP_PORT=80
EOF

    echo "✅ Created .env file with secure passwords"
    echo ""
    echo "⚠️  IMPORTANT: Save these credentials!"
    echo "Admin Username: admin"
    echo "Admin Password: $ADMIN_PASSWORD"
    echo ""
    echo "Press Enter to continue..."
    read
fi

# Build and deploy
echo "Building application..."
docker-compose -f docker-compose.production.yml build

echo ""
echo "Starting services..."
docker-compose -f docker-compose.production.yml up -d

echo ""
echo "Waiting for services to be healthy..."
sleep 10

# Check status
echo ""
echo "Service Status:"
docker-compose -f docker-compose.production.yml ps

echo ""
echo "======================================"
echo "   Deployment Complete!"
echo "======================================"
echo ""
echo "Access TowerView at:"
echo "  http://$(hostname -I | cut -d' ' -f1)"
echo ""
echo "To view logs:"
echo "  docker-compose -f docker-compose.production.yml logs -f"
echo ""
echo "To stop:"
echo "  docker-compose -f docker-compose.production.yml down"
echo ""