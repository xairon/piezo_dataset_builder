# 🐳 Docker Guide - Piezo Dataset Builder

This guide explains how to use Docker to run and deploy the Piezo Dataset Builder application.

## 📋 Prerequisites

- Docker >= 20.10
- Docker Compose >= 2.0
- (Optional) Access to GitLab Container Registry

## 🚀 Quick Start

### 1. Launch the application with Docker Compose

```bash
# Build and start the application
docker-compose up --build

# Or in detached mode (background)
docker-compose up -d --build
```

**Find the allocated port:**

Docker automatically allocates an available port. To discover it:

```bash
docker ps
# or
docker compose ps
```

The application will be accessible on the indicated port (e.g., `0.0.0.0:32768->8501/tcp`).
Example: `http://localhost:32768` or `http://<server-ip>:32768`

### 2. Stop the application

```bash
# Stop containers
docker-compose down

# Stop and remove volumes
docker-compose down -v
```

## 🔧 Configuration

### Environment Variables

You can configure the application via environment variables in the `docker-compose.yml` file:

```yaml
environment:
  - COPERNICUS_API_TOKEN=your-token-here  # Copernicus API token (optional)
```

Or create a `.env` file at the project root:

```env
COPERNICUS_API_TOKEN=your-token-here
STREAMLIT_SERVER_PORT=8501
```

### Persistent Volumes

ERA5 temporary data is stored in a Docker volume named `era5-cache` to avoid re-downloading the same data.

To delete this cache:

```bash
docker volume rm piezo-dataset-builder_era5-cache
```

## 🏗️ Manual Docker Image Build

```bash
# Build the image
docker build -t piezo-dataset-builder:latest .

# Run the container
docker run -p 8501:8501 piezo-dataset-builder:latest
```

## 🔄 CI/CD with GitLab

### GitLab Configuration

The `.gitlab-ci.yml` file configures a complete CI/CD pipeline with:

1. **Tests**: Unit test execution (to be enabled)
2. **Build**: Docker image construction and push to registry
3. **Deploy**: Automatic deployment to staging/production

### GitLab Variables to Configure

Go to **Settings > CI/CD > Variables** and add:

| Variable | Description | Example |
|----------|-------------|---------|
| `SSH_PRIVATE_KEY` | SSH key for deployment | `-----BEGIN PRIVATE KEY-----...` |
| `DEPLOY_HOST` | Staging server host | `staging.example.com` |
| `DEPLOY_USER` | SSH user | `deploy` |
| `DEPLOY_PATH` | Server installation path | `/opt/piezo-dataset-builder` |
| `PROD_DEPLOY_HOST` | Production server host | `piezo.example.com` |
| `PROD_DEPLOY_PATH` | Production installation path | `/opt/piezo-dataset-builder` |

### Server Deployment

#### Server Preparation

1. Install Docker and Docker Compose:
```bash
# Ubuntu/Debian
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose
```

2. Create the deployment directory:
```bash
sudo mkdir -p /opt/piezo-dataset-builder
sudo chown $USER:$USER /opt/piezo-dataset-builder
```

3. Copy the `docker-compose.yml` file to the server:
```bash
scp docker-compose.yml user@server:/opt/piezo-dataset-builder/
```

4. Log in to GitLab Container Registry:
```bash
docker login registry.gitlab.com
```

#### Manual Deployment

On the server:

```bash
cd /opt/piezo-dataset-builder
docker-compose pull
docker-compose up -d
```

#### Application Update

```bash
cd /opt/piezo-dataset-builder
docker-compose pull
docker-compose down
docker-compose up -d
```

## 🔒 Security

### Production

For production, it is recommended to:

1. **Use a reverse proxy (Nginx/Traefik)** with HTTPS:

```yaml
# Example with Traefik
labels:
  - "traefik.enable=true"
  - "traefik.http.routers.piezo.rule=Host(`piezo.example.com`)"
  - "traefik.http.routers.piezo.tls=true"
  - "traefik.http.routers.piezo.tls.certresolver=letsencrypt"
```

2. **Configure authentication** (if necessary)

3. **Limit network access**:

```yaml
networks:
  app-network:
    internal: true
```

## 📊 Monitoring and Logs

### View Logs

```bash
# All logs
docker-compose logs -f

# Logs for a specific service
docker-compose logs -f piezo-dataset-builder
```

### Health Check

The application includes an automatic health check. Check the status:

```bash
docker ps
```

The status should show `healthy` after a few seconds.

## 🐛 Troubleshooting

### Container doesn't start

```bash
# Check logs
docker-compose logs

# Check container status
docker-compose ps
```

### Permission issues

```bash
# Rebuild the image
docker-compose build --no-cache
docker-compose up -d
```

### Clean Docker

```bash
# Remove all stopped containers
docker container prune

# Remove all unused images
docker image prune -a

# Full cleanup (warning: deletes everything!)
docker system prune -a --volumes
```

## 📦 Image Size

The Docker image is approximately **800-900 MB** due to scientific dependencies (netCDF4, xarray, etc.).

To reduce size:
- Layers are cached to speed up subsequent builds
- `.dockerignore` excludes unnecessary files
- Base image `python:3.12-slim` is already optimized

## 🔗 Useful Links

- [Docker Documentation](https://docs.docker.com/)
- [Docker Compose Documentation](https://docs.docker.com/compose/)
- [GitLab CI/CD](https://docs.gitlab.com/ee/ci/)
- [Streamlit in Production](https://docs.streamlit.io/knowledge-base/deploy/deploy-streamlit-docker)
