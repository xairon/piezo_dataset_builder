# Piezo Dataset Builder

Application Streamlit pour construire des datasets complets à partir de codes de stations piézométriques (BSS).

## 🎯 Concept

**Input** : Un simple CSV avec des codes BSS (stations piézométriques)
**Output** : Un dataset complet avec attributs stations, niveaux de nappe et données météorologiques

L'outil interroge automatiquement :
- **Hub'Eau API Piézométrie** : Attributs stations + chroniques de niveaux de nappe phréatique
- **ERA5 (Copernicus)** : Données météorologiques historiques depuis 1940 (température, précipitations, évapotranspiration, etc.)

### 🌟 Fonctionnalités principales

- ✅ **Validation automatique** des codes BSS avant construction
- ✅ **Extraction des coordonnées GPS** depuis l'API Hub'Eau (geometry/x/y → latitude/longitude)
- ✅ **Données piézométriques complètes** : niveau nappe NGF, profondeur nappe
- ✅ **Enrichissement météorologique** automatique basé sur les coordonnées GPS
- ✅ **Agrégation journalière** pour éviter les doublons
- ✅ **Interface intuitive** avec sélection fine des champs à exporter
- ✅ **Export multi-format** : CSV, Excel, JSON
- ✅ **Rate limiting et retry logic** pour respecter les limites API

## 📋 Prérequis

- Python 3.9+
- Connexion internet (pour les APIs)

## 🚀 Installation

### Option 1 : Docker (Recommandé) 🐳

**Avantages :** Pas de configuration Python, fonctionne sur tous les OS, prêt pour le déploiement

```bash
# Démarrage rapide
docker-compose up -d

# Ou utilisez le script de démarrage
# Windows:
start-docker.bat

# Linux/Mac:
./start-docker.sh
```

L'application sera accessible sur http://localhost:8501

📖 **Documentation complète :** Voir [DOCKER.md](DOCKER.md) pour plus de détails (CI/CD, déploiement, etc.)

### Option 2 : Installation Python classique

```bash
# Cloner le repository
git clone https://scm.univ-tours.fr/ringuet/piezo_dataset_builder.git
cd piezo-dataset-builder

# Créer environnement virtuel
python -m venv venv
source venv/bin/activate  # Linux/Mac
# ou
venv\Scripts\activate     # Windows

# Installer le package
pip install -e .
```

## 💻 Utilisation

### Avec Docker

```bash
# Démarrer l'application
docker-compose up -d

# Voir les logs
docker-compose logs -f

# Arrêter l'application
docker-compose down
```

### Sans Docker

```bash
streamlit run src/piezo_dataset_builder/app.py
```

L'application s'ouvre dans votre navigateur (http://localhost:8501)

### 2. Préparer votre fichier CSV

Créez un CSV avec une colonne contenant les codes BSS (stations piézométriques) :

```csv
code_bss
07548X0009/F
BSS000AUZM
BSS000BDNZ
```

Le nom de la colonne n'importe pas, l'outil détectera automatiquement les codes BSS.

### 3. Workflow dans l'application

1. **Upload** : Chargez votre CSV contenant les codes BSS
   - Validation automatique des codes avec échantillonnage
   - Détection automatique de la colonne contenant les codes BSS
2. **Période** : Sélectionnez les dates début/fin pour les données chroniques
3. **Configuration des données** :
   - **Stations** : Libellé, commune, département
   - **Chroniques** : Niveau NGF (altitude nappe), profondeur nappe
   - **Météo** : Précipitations, température, évapotranspiration, humidité, vent, rayonnement
4. **Options avancées** : Timeout, rate limits, agrégation journalière
5. **Construire** : Lancez la construction du dataset
   - Barre de progression en temps réel
   - Logs détaillés des opérations
6. **Export** : Téléchargez en CSV, Excel ou JSON

## 📊 Exemple de dataset généré

| code_bss | date | nom_commune | niveau_nappe_ngf | profondeur_nappe | precipitation | temperature | evapotranspiration | nom_departement |
|----------|------|-------------|------------------|------------------|---------------|-------------|--------------------|-----------------|
| 07548X0009/F | 2025-11-13 | Saint-Estèphe | 21.86 | -15.88 | 0.0 | 17.1 | 1.77 | Gironde |
| 07548X0009/F | 2025-11-14 | Saint-Estèphe | 21.94 | -15.96 | 0.2 | 17.2 | 1.91 | Gironde |
| 07548X0009/F | 2025-11-15 | Saint-Estèphe | 21.94 | -15.96 | 8.3 | 14.5 | 1.41 | Gironde |
| ... | ... | ... | ... | ... | ... | ... | ... | ... |

**Notes importantes :**
- `niveau_nappe_ngf` : Altitude de la nappe en mètres NGF (Nivellement Général de la France)
- `profondeur_nappe` : Profondeur de la nappe par rapport au sol (valeurs négatives = nappe en dessous du sol)
- `precipitation` : Précipitations journalières en mm
- `temperature` : Température moyenne journalière en °C
- `evapotranspiration` : Évapotranspiration de référence en mm

## 🔧 Configuration

### APIs utilisées

- **Hub'Eau API Piézométrie** : https://hubeau.eaufrance.fr/page/api-piezometrie
  - Attributs des stations piézométriques
  - Chroniques de niveaux de nappe phréatique
  - Données France uniquement

- **ERA5-Land (Copernicus CDS)** : https://cds.climate.copernicus.eu/
  - Réanalyse atmosphérique de l'ECMWF
  - Données météo historiques depuis 1940
  - Résolution : ~9 km
  - Variables : température, précipitations, évapotranspiration, humidité, vent, rayonnement
  - Données mondiales
  - ⚠️ **Compte gratuit requis** : [Créer un compte](https://cds.climate.copernicus.eu/)
  - ⚠️ **Licence ERA5-Land à accepter** : [Accepter la licence](https://cds.climate.copernicus.eu/datasets/reanalysis-era5-land?tab=download#manage-licences)

### Limitations et bonnes pratiques

- **Hub'Eau** :
  - Données France uniquement
  - Maximum recommandé : 500 stations par batch
  - Rate limit configuré : 0.1s entre requêtes
  - Retry automatique en cas d'erreur

- **ERA5 (Copernicus)** :
  - Compte gratuit requis avec token API
  - Licence ERA5-Land à accepter (gratuit, un clic)
  - Pas de rate limit restrictif
  - Téléchargements optimisés par chunks de 2 ans
  - Extraction uniquement des points de grille nécessaires

- **Période temporelle** :
  - Données disponibles depuis 1940
  - Recommandé : jusqu'à 10 ans par requête
  - Au-delà, découpage automatique en chunks

- **Agrégation journalière** :
  - Activée par défaut pour éviter les doublons
  - Moyenne pour valeurs numériques, première valeur pour le texte

## 📁 Structure du projet

```
piezo-dataset-builder/
├── src/piezo_dataset_builder/
│   ├── app.py                  # Application Streamlit
│   ├── api/                    # Clients API
│   │   ├── hubeau.py          # Client Hub'Eau Piézométrie
│   │   └── era5.py            # Client ERA5 (Copernicus)
│   ├── core/                   # Logique métier
│   │   ├── validator.py       # Validation codes BSS
│   │   └── dataset_builder.py # Construction dataset
│   └── utils/                  # Utilitaires
│       └── export.py          # Export CSV/Excel/JSON/ZIP
├── examples/                    # Exemples de fichiers CSV
│   └── codes_stations_piezo.csv
├── Dockerfile                   # Configuration Docker
├── docker-compose.yml          # Orchestration Docker
├── .gitlab-ci.yml              # Pipeline CI/CD
├── DOCKER.md                   # Documentation Docker
├── pyproject.toml              # Configuration Python
└── README.md                   # Documentation
```

## 🔍 Données disponibles

### Hub'Eau Piézométrie

**Champs stations disponibles :**
- `code_bss` : Code unique de la station (BSS)
- `libelle_station` : Nom/libellé de la station
- `nom_commune` : Commune où se situe la station
- `nom_departement` : Département
- `latitude` / `longitude` : Coordonnées GPS (WGS84) - extraites automatiquement depuis geometry/x/y

**Champs chroniques disponibles :**
- `date` : Date de la mesure
- `niveau_nappe_ngf` : Altitude de la nappe en mètres NGF (extrait depuis `niveau_nappe_eau` de l'API)
- `profondeur_nappe` : Profondeur de la nappe par rapport au sol (m)

### ERA5-Land (Copernicus)

**Variables météorologiques disponibles :**
- `precipitation` : Précipitations journalières (mm) - converties depuis m
- `temperature` : Température air moyenne à 2m (°C) - convertie depuis Kelvin
- `evapotranspiration` : Évapotranspiration potentielle (mm) - convertie depuis m
- `humidity` : Humidité relative (%) - calculée depuis température + point de rosée
- `wind` : Vitesse du vent à 10m (m/s)
- `radiation` : Rayonnement solaire descendant (MJ/m²) - converti depuis J/m²

**Note :**
- Les données météo sont automatiquement associées à chaque station grâce aux coordonnées GPS extraites de Hub'Eau
- ERA5 fournit des données depuis 1940 avec une résolution spatiale de ~9 km
- Les valeurs sont extraites du point de grille le plus proche de chaque station

