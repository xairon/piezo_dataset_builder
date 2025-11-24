# Utiliser une image Python officielle comme base
FROM python:3.12-slim

# Définir le répertoire de travail
WORKDIR /app

# Installer les dépendances système nécessaires pour netCDF4 et autres bibliothèques scientifiques
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    libhdf5-dev \
    libnetcdf-dev \
    libssl-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copier les fichiers de configuration du projet
COPY pyproject.toml ./

# Copier le code source de l'application (nécessaire AVANT pip install -e .)
COPY src/ ./src/

# Installer les dépendances Python
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -e .

# Créer un répertoire pour les fichiers temporaires
RUN mkdir -p /tmp/era5_downloads

# Exposer le port Streamlit (par défaut 8501)
EXPOSE 8501

# Définir les variables d'environnement pour Streamlit
ENV STREAMLIT_SERVER_PORT=8501
ENV STREAMLIT_SERVER_ADDRESS=0.0.0.0
ENV STREAMLIT_SERVER_HEADLESS=true
ENV STREAMLIT_BROWSER_GATHER_USAGE_STATS=false

# Créer un utilisateur non-root pour des raisons de sécurité
RUN useradd -m -u 1000 streamlit && \
    chown -R streamlit:streamlit /app /tmp/era5_downloads

# Passer à l'utilisateur non-root
USER streamlit

# Commande de démarrage
CMD ["python", "-m", "streamlit", "run", "src/piezo_dataset_builder/app.py"]
