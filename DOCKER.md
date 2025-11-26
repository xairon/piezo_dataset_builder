# 🐳 Guide Docker - Piezo Dataset Builder

Ce guide explique comment utiliser Docker pour exécuter et déployer l'application Piezo Dataset Builder.

## 📋 Prérequis

- Docker >= 20.10
- Docker Compose >= 2.0
- (Optionnel) Accès au GitLab Container Registry

## 🚀 Démarrage rapide

### 1. Lancer l'application avec Docker Compose

```bash
# Construire et démarrer l'application
docker-compose up --build

# Ou en mode détaché (arrière-plan)
docker-compose up -d --build
```

**Trouver le port alloué :**

Docker alloue automatiquement un port disponible. Pour le découvrir :

```bash
docker ps
# ou
docker compose ps
```

L'application sera accessible sur le port indiqué (ex: `0.0.0.0:32768->8501/tcp`).
Exemple : `http://localhost:32768` ou `http://<ip-serveur>:32768`

### 2. Arrêter l'application

```bash
# Arrêter les conteneurs
docker-compose down

# Arrêter et supprimer les volumes
docker-compose down -v
```

## 🔧 Configuration

### Variables d'environnement

Vous pouvez configurer l'application via des variables d'environnement dans le fichier `docker-compose.yml` :

```yaml
environment:
  - COPERNICUS_API_TOKEN=your-token-here  # Token API Copernicus (optionnel)
```

Ou créer un fichier `.env` à la racine du projet :

```env
COPERNICUS_API_TOKEN=your-token-here
STREAMLIT_SERVER_PORT=8501
```

### Volumes persistants

Les données temporaires ERA5 sont stockées dans un volume Docker nommé `era5-cache` pour éviter de retélécharger les mêmes données.

Pour supprimer ce cache :

```bash
docker volume rm piezo-dataset-builder_era5-cache
```

## 🏗️ Build manuel de l'image Docker

```bash
# Construire l'image
docker build -t piezo-dataset-builder:latest .

# Lancer le conteneur
docker run -p 8501:8501 piezo-dataset-builder:latest
```

## 🔄 CI/CD avec GitLab

### Configuration GitLab

Le fichier `.gitlab-ci.yml` configure un pipeline CI/CD complet avec :

1. **Tests** : Exécution des tests unitaires (à activer)
2. **Build** : Construction de l'image Docker et push vers le registry
3. **Deploy** : Déploiement automatique sur staging/production

### Variables GitLab à configurer

Allez dans **Settings > CI/CD > Variables** et ajoutez :

| Variable | Description | Exemple |
|----------|-------------|---------|
| `SSH_PRIVATE_KEY` | Clé SSH pour le déploiement | `-----BEGIN PRIVATE KEY-----...` |
| `DEPLOY_HOST` | Hôte du serveur de staging | `staging.example.com` |
| `DEPLOY_USER` | Utilisateur SSH | `deploy` |
| `DEPLOY_PATH` | Chemin d'installation sur le serveur | `/opt/piezo-dataset-builder` |
| `PROD_DEPLOY_HOST` | Hôte du serveur de production | `piezo.example.com` |
| `PROD_DEPLOY_PATH` | Chemin d'installation en production | `/opt/piezo-dataset-builder` |

### Déploiement sur un serveur

#### Préparation du serveur

1. Installer Docker et Docker Compose :
```bash
# Ubuntu/Debian
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose
```

2. Créer le répertoire de déploiement :
```bash
sudo mkdir -p /opt/piezo-dataset-builder
sudo chown $USER:$USER /opt/piezo-dataset-builder
```

3. Copier le fichier `docker-compose.yml` sur le serveur :
```bash
scp docker-compose.yml user@server:/opt/piezo-dataset-builder/
```

4. Se connecter au GitLab Container Registry :
```bash
docker login registry.gitlab.com
```

#### Déploiement manuel

Sur le serveur :

```bash
cd /opt/piezo-dataset-builder
docker-compose pull
docker-compose up -d
```

#### Mise à jour de l'application

```bash
cd /opt/piezo-dataset-builder
docker-compose pull
docker-compose down
docker-compose up -d
```

## 🔒 Sécurité

### Production

Pour la production, il est recommandé de :

1. **Utiliser un reverse proxy (Nginx/Traefik)** avec HTTPS :

```yaml
# Exemple avec Traefik
labels:
  - "traefik.enable=true"
  - "traefik.http.routers.piezo.rule=Host(`piezo.example.com`)"
  - "traefik.http.routers.piezo.tls=true"
  - "traefik.http.routers.piezo.tls.certresolver=letsencrypt"
```

2. **Configurer l'authentification** (si nécessaire)

3. **Limiter l'accès réseau** :

```yaml
networks:
  app-network:
    internal: true
```

## 📊 Monitoring et Logs

### Voir les logs

```bash
# Tous les logs
docker-compose logs -f

# Logs d'un service spécifique
docker-compose logs -f piezo-dataset-builder
```

### Health check

L'application inclut un health check automatique. Vérifier l'état :

```bash
docker ps
```

Le statut devrait afficher `healthy` après quelques secondes.

## 🐛 Dépannage

### Le conteneur ne démarre pas

```bash
# Vérifier les logs
docker-compose logs

# Vérifier l'état du conteneur
docker-compose ps
```

### Problèmes de permissions

```bash
# Reconstruire l'image
docker-compose build --no-cache
docker-compose up -d
```

### Nettoyer Docker

```bash
# Supprimer tous les conteneurs arrêtés
docker container prune

# Supprimer toutes les images non utilisées
docker image prune -a

# Nettoyage complet (attention : supprime tout !)
docker system prune -a --volumes
```

## 📦 Taille de l'image

L'image Docker fait environ **800-900 MB** en raison des dépendances scientifiques (netCDF4, xarray, etc.).

Pour réduire la taille :
- Les layers sont mis en cache pour accélérer les builds suivants
- Le `.dockerignore` exclut les fichiers inutiles
- L'image de base `python:3.12-slim` est déjà optimisée

## 🔗 Liens utiles

- [Documentation Docker](https://docs.docker.com/)
- [Documentation Docker Compose](https://docs.docker.com/compose/)
- [GitLab CI/CD](https://docs.gitlab.com/ee/ci/)
- [Streamlit en production](https://docs.streamlit.io/knowledge-base/deploy/deploy-streamlit-docker)
