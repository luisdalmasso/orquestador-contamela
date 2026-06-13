#!/bin/bash
echo "🤖 Iniciando Chat Directo con Nanobot Católico (CLI) 🤖"
docker exec -it -e HOME=/tenants/catolico conti-backend nanobot agent --config /tenants/catolico/.nanobot/config.json
