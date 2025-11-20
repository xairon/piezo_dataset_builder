# Piezo Dataset Builder

Application Streamlit pour construire des datasets complets à partir de codes de stations piézométriques (BSS).

## 🎯 Concept

**Input** : Un simple CSV avec des codes BSS (stations piézométriques)
**Output** : Un dataset complet avec attributs stations, niveaux de nappe et données météorologiques

L'outil interroge automatiquement :
- **Hub'Eau API Piézométrie** : Attributs stations + chroniques de niveaux de nappe phréatique
- **Open-Meteo** : Données météorologiques historiques (température, précipitations, évapotranspiration, etc.)

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

```bash
# Cloner le repository
git clone https://github.com/brgm/piezo-dataset-builder.git
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

### 1. Lancer l'application

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

- **Open-Meteo API** : https://open-meteo.com
  - Données météo historiques
  - Variables : température air, précipitations, évapotranspiration, humidité, vent, rayonnement
  - Données mondiales

### Limitations et bonnes pratiques

- **Hub'Eau** :
  - Données France uniquement
  - Maximum recommandé : 500 stations par batch
  - Rate limit configuré : 0.3s entre requêtes
  - Retry automatique en cas d'erreur

- **Open-Meteo** :
  - 10,000 requêtes/jour (tier gratuit)
  - Rate limit configuré : 0.1s entre requêtes
  - Données mondiales disponibles

- **Période temporelle** :
  - Maximum recommandé : 2 ans (730 jours)
  - Au-delà, risque de timeout et surcharge API

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
│   │   └── meteo.py           # Client Open-Meteo
│   ├── core/                   # Logique métier
│   │   ├── validator.py       # Validation codes BSS
│   │   └── dataset_builder.py # Construction dataset
│   └── utils/                  # Utilitaires
│       └── export.py          # Export CSV/Excel/JSON
├── examples/                    # Exemples de fichiers CSV
│   └── codes_stations_piezo.csv
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

### Open-Meteo

**Variables météorologiques disponibles :**
- `precipitation` : Précipitations journalières (mm)
- `temperature` : Température air moyenne (°C)
- `temperature_min` : Température air minimale (°C)
- `temperature_max` : Température air maximale (°C)
- `evapotranspiration` : Évapotranspiration de référence (mm)
- `humidity` : Humidité relative (%)
- `wind` : Vitesse du vent (km/h)
- `radiation` : Rayonnement solaire (MJ/m²)

**Note :** Les données météo sont automatiquement associées à chaque station grâce aux coordonnées GPS extraites de Hub'Eau.

## 🤝 Contribution

Les contributions sont les bienvenues ! N'hésitez pas à :
- Signaler des bugs
- Proposer de nouvelles fonctionnalités
- Soumettre des pull requests

## 📄 Licence

MIT - BRGM 2025

## 📞 Support

Pour toute question : contact@brgm.fr
