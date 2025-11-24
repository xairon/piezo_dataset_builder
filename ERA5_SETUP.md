# Guide de Configuration ERA5

ERA5 est la réanalyse atmosphérique de 5ème génération de l'ECMWF (European Centre for Medium-Range Weather Forecasts). C'est la source de données météorologiques de référence pour la recherche scientifique et les applications opérationnelles.

## Pourquoi ERA5 ?

- **Gratuit** : Nécessite seulement un compte Copernicus (gratuit)
- **Historique complet** : Données depuis **1940** jusqu'à aujourd'hui (mise à jour continue)
- **Qualité scientifique** : Utilisé par BRGM, Météo-France, et de nombreux organismes de recherche
- **Pas de rate limits restrictifs** : Contrairement à Open-Meteo et autres APIs REST
- **Variables complètes** : Température, précipitations, évapotranspiration, humidité, vent, rayonnement, etc.
- **Résolution spatiale** : ~9km (ERA5-Land)

## Installation et Configuration

### Étape 1 : Créer un compte Copernicus CDS

1. Allez sur [https://cds.climate.copernicus.eu/](https://cds.climate.copernicus.eu/)
2. Cliquez sur "Register" en haut à droite
3. Remplissez le formulaire d'inscription (nom, email, mot de passe)
4. Validez votre email (vérifiez vos spams si besoin)
5. Connectez-vous et acceptez les termes et conditions d'utilisation

### Étape 2 : Accepter la licence ERA5-Land (OBLIGATOIRE ⚠️)

**Cette étape est OBLIGATOIRE avant de pouvoir télécharger des données.**

1. Une fois connecté sur Copernicus CDS
2. Allez sur cette page : [👉 Accepter la Licence ERA5-Land](https://cds.climate.copernicus.eu/datasets/reanalysis-era5-land?tab=download#manage-licences)
3. Cliquez sur **"Accept Licence"** (gratuit, instantané, un seul clic)
4. La licence sera acceptée immédiatement

**⛔ Sans cette étape, vous obtiendrez une erreur 403 Forbidden lors du téléchargement.**

### Étape 3 : Obtenir votre Token API

1. Cliquez sur votre nom en haut à droite
2. Allez dans "Profile" ou "User profile"
3. Vous verrez votre **API Token** (format : `abcd1234-5678-90ab-cdef-1234567890ab`)
4. Copiez ce token (vous en aurez besoin pour l'application)

**Note importante** : Le nouveau format Copernicus (2024+) n'utilise plus d'UID séparé. Il n'y a qu'un seul token unique.

### Étape 4 : Configurer vos credentials (2 options)

Vous avez **2 façons** de fournir vos credentials à l'application :

#### Option A : Via l'interface Streamlit (RECOMMANDÉ - Plus simple)

Vous entrerez vos credentials directement dans l'application lors de la configuration du dataset (voir section "Utilisation dans l'Application" ci-dessous).

**Avantages :**
- Pas besoin de créer de fichier
- Facile à utiliser
- Pas de manipulation technique

**Inconvénient :**
- Vous devrez re-saisir vos credentials à chaque nouvelle session

#### Option B : Via le fichier `.cdsapirc` (Optionnel - Pour utilisateurs avancés)

Si vous utilisez souvent l'application ou d'autres outils ERA5, vous pouvez configurer le fichier `.cdsapirc` :

**Sur Windows:**
1. Ouvrez l'invite de commande et tapez :
   ```cmd
   notepad %USERPROFILE%\.cdsapirc
   ```
2. Collez :
   ```
   url: https://cds.climate.copernicus.eu/api
   key: <VOTRE_TOKEN_API>
   ```
   (Remplacez `<VOTRE_TOKEN_API>` par votre token, ex: `abcd1234-5678-90ab-cdef-1234567890ab`)
3. Enregistrez

**Sur Linux/Mac:**
1. Dans un terminal, tapez :
   ```bash
   nano ~/.cdsapirc
   ```
2. Collez :
   ```
   url: https://cds.climate.copernicus.eu/api
   key: <VOTRE_TOKEN_API>
   ```
   (Remplacez `<VOTRE_TOKEN_API>` par votre token)
3. Sauvegardez (Ctrl+O, Entrée, Ctrl+X)
4. Définissez les permissions :
   ```bash
   chmod 600 ~/.cdsapirc
   ```

## Utilisation dans l'Application

### Étapes :

1. **Lancez l'application Streamlit** :
   ```bash
   streamlit run src/piezo_dataset_builder/app.py
   ```

2. **Étape 1 - Chargez votre fichier CSV** avec les codes BSS des stations piézométriques

3. **Étape 2 - Configuration**

   Dans la section **"Météo (ERA5 - Copernicus)"** :

   - 🔑 **Entrez votre Token API Copernicus** :
     - **API Token Copernicus** : Votre token unique (ex: `abcd1234-5678-90ab-cdef-1234567890ab`)
     - Note : Le nouveau format n'utilise plus d'UID séparé

   - ✅ Ce champ est **obligatoire** si vous cochez "Inclure Météo"
   - 🔒 Votre token est **masqué** et n'est **PAS sauvegardé** (stocké uniquement dans la session en cours)

   - Cochez **"Inclure Météo"**
   - Sélectionnez les **variables météo** souhaitées (précipitations, température, etc.)

4. **Lancez la construction du dataset**
   - Les données ERA5 seront téléchargées automatiquement depuis Copernicus
   - ⏱️ Cela peut prendre **plusieurs minutes** selon la taille de la requête
   - Suivez la progression dans les logs en temps réel

### Notes importantes

- ⚠️ **Votre token n'est PAS sauvegardé** : il reste dans la session Streamlit uniquement
- 🔒 Le token est masqué dans l'interface (champ mot de passe)
- Si vous fermez l'onglet/navigateur, vous devrez le re-saisir
- Si vous avez configuré le fichier `~/.cdsapirc` (Option B), vous pouvez laisser le champ vide dans l'interface

## Variables Météorologiques Disponibles

| Variable | Description | Unité | Agrégation |
|----------|-------------|-------|-----------|
| **Précipitations** | Précipitations totales | mm | Somme journalière |
| **Température** | Température de l'air à 2m | °C | Moyenne journalière |
| **Évapotranspiration** | Évapotranspiration potentielle | mm | Somme journalière |
| **Température Min** | Température minimale journalière | °C | Min journalier |
| **Température Max** | Température maximale journalière | °C | Max journalier |
| **Humidité** | Humidité relative | % | Moyenne journalière |
| **Vent** | Vitesse du vent à 10m | m/s | Moyenne journalière |
| **Rayonnement** | Rayonnement solaire incident | MJ/m² | Somme journalière |

## Performance et Limites

### Temps de Téléchargement

Les temps de téléchargement dépendent de :
- **Nombre de stations** : Plus il y a de stations, plus long sera le téléchargement
- **Période temporelle** : Les longues périodes (> 10 ans) prennent plus de temps
- **Charge du serveur** : Le service CDS peut être surchargé aux heures de pointe

**Exemples de temps typiques :**
- 5 stations × 1 an : ~2-3 minutes
- 25 stations × 5 ans : ~10-15 minutes
- 100 stations × 10 ans : ~30-60 minutes

### Optimisations

L'application utilise plusieurs optimisations :
1. **Bounding box** : Une seule requête CDS couvre toutes les stations d'une région
2. **Extraction par point** : Les données sont extraites pour chaque station depuis la bbox
3. **Agrégation journalière** : Les données 6-horaires sont agrégées en moyennes/sommes journalières

### Limites Pratiques

- **Pas de données futures** : ERA5 ne fournit que des données historiques (pas de prévisions)
- **Résolution spatiale** : ~9km, donc pas de variations locales très fines
- **Queue CDS** : Les requêtes peuvent être mises en file d'attente si le service est surchargé

## Dépannage

### Erreur: "Failed to initialize CDS API client"

**Causes possibles :**
1. Le fichier `.cdsapirc` n'existe pas au bon endroit
2. Le format du fichier est incorrect
3. Le token API est incorrect ou expiré

**Solutions :**
1. Vérifiez que le fichier existe :
   - Windows : `%USERPROFILE%\.cdsapirc`
   - Linux/Mac : `~/.cdsapirc`
2. Vérifiez le contenu du fichier (pas d'espaces inutiles, format : `key: votre_token`)
3. Reconnectez-vous sur le site CDS et vérifiez votre token (copiez-le à nouveau)
4. Assurez-vous d'avoir accepté les termes et conditions sur le site CDS

### Erreur: "Request failed" ou timeout

**Causes possibles :**
1. Connexion Internet instable
2. Service CDS temporairement surchargé
3. Requête trop large

**Solutions :**
1. Vérifiez votre connexion Internet
2. Réessayez plus tard (évitez les heures de pointe : 9h-17h CET)
3. Réduisez la taille de la requête :
   - Moins de stations
   - Période plus courte
   - Moins de variables

### Les données semblent incorrectes

**Vérifications :**
1. ERA5 fournit des moyennes spatiales sur des cellules de ~9km, pas des points exacts
2. Les précipitations sont en mm (cumulées sur 24h)
3. Les températures sont en °C
4. L'évapotranspiration est en mm (cumul journalier)

### L'application est bloquée sur "Downloading ERA5 data..."

C'est normal ! Le téléchargement ERA5 peut prendre plusieurs minutes. Soyez patient.

Si cela dure plus de 30 minutes :
1. Vérifiez les logs pour voir s'il y a des erreurs
2. Vérifiez que votre connexion Internet est stable
3. Essayez avec une requête plus petite

## Ressources Utiles

### Documentation

- **CDS API** : https://cds.climate.copernicus.eu/how-to-api
- **ERA5 Documentation** : https://confluence.ecmwf.int/display/CKB/ERA5
- **ERA5-Land** : https://confluence.ecmwf.int/display/CKB/ERA5-Land
- **Python cdsapi** : https://github.com/ecmwf/cdsapi

### Support

- **Forum ECMWF** : https://forum.ecmwf.int/
- **CDS Support** : https://support.ecmwf.int/

### Exemples et Tutoriels

- **CDS Toolbox** : https://cds.climate.copernicus.eu/toolbox
- **Jupyter Notebooks** : https://github.com/ecmwf/notebook-examples

## FAQ

### Puis-je utiliser ERA5 pour des données en temps réel ?

Non, ERA5 a un délai de publication d'environ 5 jours. Pour des données plus récentes, utilisez ERA5T (version temporaire) ou attendez la mise à jour.

### Combien de requêtes puis-je faire par jour ?

Il n'y a pas de limite stricte, mais le service CDS limite le nombre de requêtes simultanées. Évitez de faire des centaines de requêtes d'affilée.

### Les données ERA5 sont-elles fiables ?

Oui, ERA5 est la référence mondiale pour les données météorologiques historiques. C'est un produit scientifique validé, utilisé pour la recherche et les applications opérationnelles.

### Quelle est la différence entre ERA5 et ERA5-Land ?

- **ERA5** : Résolution ~31km, données atmosphériques complètes
- **ERA5-Land** : Résolution ~9km, focalisé sur les variables de surface (ce que nous utilisons)

Pour la plupart des applications hydrologiques, ERA5-Land est préférable.

### Puis-je télécharger les données manuellement ?

Oui, vous pouvez télécharger les données NetCDF directement depuis le site CDS, puis les charger dans Python avec xarray. Mais l'application fait cela automatiquement pour vous.

## Contact

Pour tout problème lié à cette application : ouvrez une issue sur le dépôt GitHub/GitLab.

Pour les problèmes liés au service CDS : contactez le support ECMWF via leur forum.
