# ERA5 Setup Guide

ERA5 est la réanalyse atmosphérique de 5ème génération de l'ECMWF (European Centre for Medium-Range Weather Forecasts), couvrant la période depuis 1940 jusqu'à présent.

## Avantages

- **Gratuit** : Nécessite seulement un compte Copernicus (gratuit)
- **Historique long** : Données depuis 1940 jusqu'à aujourd'hui
- **Qualité scientifique** : Utilisé par BRGM, Météo-France, et de nombreux organismes de recherche
- **Pas de rate limits restrictifs** : Contrairement à Open-Meteo
- **Variables complètes** : Température, précipitations, évapotranspiration, humidité, vent, rayonnement, etc.

## Prérequis

### 1. Créer un compte Copernicus CDS

1. Aller sur https://cds.climate.copernicus.eu/
2. Cliquer sur "Register" en haut à droite
3. Remplir le formulaire d'inscription
4. Valider votre email
5. Accepter les termes et conditions

### 2. Obtenir votre clé API

1. Se connecter sur https://cds.climate.copernicus.eu/
2. Aller dans votre profil (cliquer sur votre nom en haut à droite)
3. Copier votre **UID** et votre **API Key**

### 3. Configurer le fichier `.cdsapirc`

#### Sur Linux/Mac

Créer le fichier `~/.cdsapirc` avec le contenu suivant :

```
url: https://cds.climate.copernicus.eu/api
key: UID:API_KEY
```

Remplacer `UID` et `API_KEY` par vos valeurs copiées à l'étape 2.

Exemple :
```
url: https://cds.climate.copernicus.eu/api
key: 12345:abcdef01-2345-6789-abcd-ef0123456789
```

#### Sur Windows

Créer le fichier `%USERPROFILE%\.cdsapirc` (par exemple `C:\Users\VotreNom\.cdsapirc`) avec le même contenu.

**Note** : Sous Windows, vous devrez peut-être créer le fichier via la ligne de commande :
```cmd
notepad %USERPROFILE%\.cdsapirc
```

### 4. Vérifier l'installation

Lancer le script de test fourni :

```bash
python test_era5.py
```

Si tout est correctement configuré, vous devriez voir :
- ✓ ERA5 client initialized successfully
- ✓ Retrieved X records

## Utilisation dans l'application Streamlit

1. Lancer l'application : `streamlit run src/piezo_dataset_builder/app.py`
2. À l'étape de configuration, sélectionner **"ERA5 Copernicus"** dans le menu "Source de données météo"
3. Configurer les variables météo souhaitées
4. Lancer la construction du dataset

## Variables disponibles

- **precipitation** : Précipitations totales (mm)
- **temperature** : Température de l'air à 2m (°C)
- **evapotranspiration** : Évapotranspiration potentielle (mm)
- **humidity** : Humidité (calculée depuis température de point de rosée)
- **wind** : Vitesse du vent à 10m (m/s)
- **radiation** : Rayonnement solaire incident (MJ/m²)

## Résolution spatiale

ERA5-Land fournit des données avec une résolution d'environ **9 km**. Les coordonnées GPS exactes sont arrondies à la cellule de grille la plus proche.

## Performance

- **Première requête** : Peut prendre plusieurs minutes (téléchargement NetCDF)
- **Batch de stations** : Plus efficace que les requêtes individuelles
- **Cache CDS** : Les requêtes récentes peuvent être plus rapides grâce au cache Copernicus

## Limites

- **Délai de traitement** : Les requêtes peuvent être mises en queue si beaucoup d'utilisateurs utilisent le service
- **Taille des requêtes** : Éviter les requêtes très larges (> 100 ans × 100 stations)
- **Pas de données futures** : ERA5 ne fournit que des données historiques

## Dépannage

### Erreur : "Failed to initialize CDS API client"

- Vérifier que le fichier `.cdsapirc` existe au bon emplacement
- Vérifier que le format est correct (pas d'espaces inutiles)
- Vérifier que votre UID et API Key sont corrects

### Erreur : "Request failed" ou timeout

- Vérifier votre connexion Internet
- Réessayer plus tard (le service CDS peut être surchargé)
- Réduire la taille de la requête (moins de stations ou période plus courte)

### Les données semblent incorrectes

- Vérifier les unités (mm, °C, etc.)
- ERA5 fournit des moyennes sur des cellules de 9 km, pas des points exacts

## Ressources

- Documentation CDS API : https://cds.climate.copernicus.eu/how-to-api
- Documentation ERA5 : https://confluence.ecmwf.int/display/CKB/ERA5
- Python cdsapi : https://github.com/ecmwf/cdsapi
- Forum support : https://forum.ecmwf.int/

## Support

En cas de problème :
1. Consulter ce guide
2. Vérifier les logs de l'application
3. Tester avec le script `test_era5.py`
4. Consulter le forum ECMWF
