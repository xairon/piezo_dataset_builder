# Changelog - Migration Docker & CI/CD

## 📦 Nouveaux fichiers ajoutés

### Configuration Docker

1. **Dockerfile** - Image Docker optimisée pour l'application
   - Base : Python 3.12-slim
   - Dépendances scientifiques : netCDF4, xarray
   - Utilisateur non-root pour la sécurité
   - Port 8501 exposé

2. **docker-compose.yml** - Orchestration simplifiée
   - Configuration service unique
   - Healthcheck intégré
   - Volumes persistants pour cache ERA5
   - Variables d'environnement configurables

3. **.dockerignore** - Optimisation du build
   - Exclusion fichiers inutiles (git, venv, IDE, etc.)
   - Réduction taille de l'image

### CI/CD

4. **.gitlab-ci.yml** - Pipeline complet
   - Stage test : Tests unitaires (à activer)
   - Stage build : Construction et push de l'image Docker
   - Stage deploy : Déploiement automatique staging/production
   - Job cleanup : Nettoyage images anciennes

### Scripts utilitaires

5. **start-docker.sh** - Script de démarrage Linux/Mac
   - Menu interactif
   - Options : start, build, stop, clean

6. **start-docker.bat** - Script de démarrage Windows
   - Menu interactif
   - Mêmes options que le script Linux

### Documentation

7. **DOCKER.md** - Guide complet Docker
   - Installation et configuration
   - Utilisation en développement
   - Déploiement en production
   - Configuration GitLab CI/CD
   - Dépannage

8. **CHANGELOG-DOCKER.md** - Ce fichier
   - Récapitulatif des modifications

## 🔧 Fichiers modifiés

### README.md
- Ajout section "Installation avec Docker" (Option 1)
- Mise à jour APIs utilisées (ERA5 au lieu d'Open-Meteo)
- Mise à jour structure du projet
- Mise à jour liste des variables météo disponibles
- Ajout liens vers documentation Docker

### src/piezo_dataset_builder/api/era5.py
- **Fix critique Windows** : Correction erreur `[Errno 22] Invalid argument`
  - Remplacement de `NamedTemporaryFile` par `mkstemp`
  - Fermeture immédiate du descripteur de fichier
  - Compatible Windows + Linux

### src/piezo_dataset_builder/app.py
- **Suppression** des variables `temperature_min` et `temperature_max`
  - Retrait de l'interface utilisateur (checkboxes)
  - Retrait du mapping de variables
  - Simplification du code (3 colonnes au lieu de 4)

## 🎯 Avantages de la conteneurisation

### Développement
- ✅ Plus de problèmes de compatibilité Windows/Linux
- ✅ Environnement reproductible
- ✅ Installation simplifiée (juste Docker)
- ✅ Pas de gestion d'environnement virtuel Python

### Production
- ✅ Déploiement automatisé via GitLab CI/CD
- ✅ Rollback facile en cas de problème
- ✅ Scaling horizontal possible
- ✅ Isolation des dépendances
- ✅ Healthcheck intégré

### CI/CD
- ✅ Pipeline complet prêt à l'emploi
- ✅ Déploiement staging + production
- ✅ Déploiement manuel contrôlé
- ✅ Nettoyage automatique des anciennes images

## 🚀 Comment démarrer

### En développement

```bash
# Option 1 : Docker Compose
docker-compose up -d

# Option 2 : Script interactif
./start-docker.sh  # Linux/Mac
start-docker.bat   # Windows
```

### En production

1. Configurer les variables GitLab CI/CD (voir DOCKER.md)
2. Pousser les modifications sur la branche `era5-integration`
3. Le pipeline build l'image automatiquement
4. Déclencher le déploiement manuel depuis GitLab

## 📝 Configuration requise

### Variables d'environnement (optionnelles)

```bash
# Token API Copernicus (peut être saisi dans l'UI aussi)
COPERNICUS_API_TOKEN=your-token-here
```

### Variables GitLab CI/CD (pour déploiement)

- `SSH_PRIVATE_KEY` : Clé SSH pour connexion serveur
- `DEPLOY_HOST` : Serveur staging
- `DEPLOY_USER` : Utilisateur SSH
- `DEPLOY_PATH` : Chemin installation staging
- `PROD_DEPLOY_HOST` : Serveur production
- `PROD_DEPLOY_PATH` : Chemin installation production

## 🔍 Prochaines étapes

### Recommandations

1. **Tests unitaires** : Ajouter des tests et activer le stage test dans `.gitlab-ci.yml`
2. **Reverse proxy** : Configurer Nginx ou Traefik pour HTTPS en production
3. **Monitoring** : Ajouter Prometheus + Grafana pour le monitoring
4. **Sauvegardes** : Configurer sauvegardes régulières des volumes Docker
5. **Secrets** : Utiliser GitLab Secrets ou Vault pour les tokens API

### Améliorations possibles

- [ ] Ajouter des tests unitaires
- [ ] Multi-stage build pour réduire taille image
- [ ] Cache Docker pour accélérer les builds
- [ ] Métriques Prometheus
- [ ] Logs centralisés (ELK/Loki)

## 📞 Support

Pour toute question sur Docker ou le CI/CD, consulter :
- [DOCKER.md](DOCKER.md) - Documentation complète
- [Documentation Docker](https://docs.docker.com/)
- [GitLab CI/CD Docs](https://docs.gitlab.com/ee/ci/)
