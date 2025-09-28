#!/bin/bash

# Script to switch between multi-container and simplified setup

echo "TowerView Container Setup Switcher"
echo "=================================="
echo ""
echo "Current setup uses these containers:"
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
echo ""
echo "Select setup:"
echo "1) Simplified (2 containers: DB + All-in-one App)"
echo "2) Original (7 containers: separate services)"
echo "3) Exit"
echo ""
read -p "Choice [1-3]: " choice

case $choice in
    1)
        echo "Switching to simplified setup..."

        # Stop current containers
        docker-compose down

        # Build and start simplified setup
        docker-compose -f docker-compose.simple.yml up --build -d

        echo ""
        echo "Simplified setup started!"
        echo "Access the app at: http://localhost"
        echo ""
        docker-compose -f docker-compose.simple.yml ps
        ;;

    2)
        echo "Switching to original setup..."

        # Stop simplified containers
        docker-compose -f docker-compose.simple.yml down

        # Start original setup
        docker-compose up -d

        echo ""
        echo "Original setup started!"
        echo "Access the app at: http://localhost:8080"
        echo ""
        docker-compose ps
        ;;

    3)
        echo "Exiting..."
        exit 0
        ;;

    *)
        echo "Invalid choice"
        exit 1
        ;;
esac