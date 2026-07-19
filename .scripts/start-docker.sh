#!/bin/bash
set -e

echo "removing all running containers..."
docker-compose down --remove-orphans -v

echo "starting all containers again..."
# Build and start the containers in detached mode
docker-compose up --build -d

# Restart services
echo "Restarting services..."
sudo systemctl restart gunicorn
sudo systemctl restart nginx

echo "Deployment completed successfully!"
echo "All containers started successfully."