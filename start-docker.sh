#!/bin/bash

# Script de démarrage rapide pour Docker

echo "🐳 Piezo Dataset Builder - Docker Startup"
echo "=========================================="
echo ""

# Vérifier que Docker est installé
if ! command -v docker &> /dev/null; then
    echo "❌ Docker n'est pas installé. Veuillez installer Docker Desktop."
    exit 1
fi

# Vérifier que Docker est en cours d'exécution
if ! docker info &> /dev/null; then
    echo "❌ Docker n'est pas en cours d'exécution. Veuillez démarrer Docker Desktop."
    exit 1
fi

echo "✅ Docker est prêt"
echo ""

# Demander le mode de démarrage
echo "Choisissez une option :"
echo "1. Démarrage rapide (docker-compose)"
echo "2. Build et démarrage"
echo "3. Arrêter l'application"
echo "4. Nettoyer et reconstruire"
echo ""
read -p "Votre choix [1-4] : " choice

case $choice in
    1)
        echo "🚀 Démarrage de l'application..."
        docker-compose up -d
        ;;
    2)
        echo "🏗️  Construction de l'image..."
        docker-compose build
        echo "🚀 Démarrage de l'application..."
        docker-compose up -d
        ;;
    3)
        echo "🛑 Arrêt de l'application..."
        docker-compose down
        ;;
    4)
        echo "🧹 Nettoyage complet..."
        docker-compose down -v
        echo "🏗️  Reconstruction de l'image..."
        docker-compose build --no-cache
        echo "🚀 Démarrage de l'application..."
        docker-compose up -d
        ;;
    *)
        echo "❌ Option invalide"
        exit 1
        ;;
esac

echo ""
if [ "$choice" != "3" ]; then
    echo "✅ Application démarrée avec succès !"
    echo ""
    echo "📍 Accédez à l'application sur :"
    echo "   http://localhost:8501"
    echo ""
    echo "📋 Voir les logs :"
    echo "   docker-compose logs -f"
    echo ""
    echo "🛑 Arrêter l'application :"
    echo "   docker-compose down"
else
    echo "✅ Application arrêtée"
fi
