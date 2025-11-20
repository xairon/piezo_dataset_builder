"""
Client ERA5 - Données météorologiques historiques via Copernicus CDS.

ERA5 est la réanalyse atmosphérique de 5ème génération de l'ECMWF,
couvrant la période depuis 1940 jusqu'à présent.

Avantages:
- Gratuit (nécessite compte Copernicus)
- Données depuis 1940
- Qualité scientifique (utilisé par BRGM, Météo-France, etc.)
- Pas de rate limits restrictifs
- Variables complètes

Documentation: https://cds.climate.copernicus.eu/
API: https://github.com/ecmwf/cdsapi
"""

import cdsapi
import pandas as pd
import xarray as xr
from datetime import datetime
from typing import List, Dict, Optional
import logging
import tempfile
import os

logger = logging.getLogger(__name__)


class ERA5Client:
    """
    Client pour télécharger des données météo depuis ERA5 (Copernicus).

    Nécessite:
    1. Compte Copernicus: https://cds.climate.copernicus.eu/
    2. Fichier ~/.cdsapirc avec API key:
       url: https://cds.climate.copernicus.eu/api
       key: <YOUR-API-KEY>
    """

    # Dataset ERA5-Land (données de surface, résolution 9km)
    DATASET_LAND = "reanalysis-era5-land"

    # Mapping variables vers noms ERA5
    AVAILABLE_VARIABLES = {
        "precipitation": "total_precipitation",           # m -> mm
        "temperature": "2m_temperature",                  # K -> °C
        "temperature_min": "2m_temperature",              # (agrégation daily min)
        "temperature_max": "2m_temperature",              # (agrégation daily max)
        "evapotranspiration": "potential_evaporation",    # m -> mm
        "humidity": "2m_dewpoint_temperature",            # K (pour calculer humidité)
        "wind": "10m_u_component_of_wind",               # m/s (u+v)
        "radiation": "surface_solar_radiation_downwards", # J/m² -> MJ/m²
    }

    def __init__(self):
        """
        Initialise le client ERA5.

        Raises:
            Exception: Si le fichier ~/.cdsapirc n'existe pas
        """
        try:
            self.client = cdsapi.Client()
            logger.info("Initialized ERA5Client (Copernicus CDS)")
        except Exception as e:
            logger.error(
                f"Failed to initialize CDS API client: {e}\n"
                "Please ensure ~/.cdsapirc exists with your API key.\n"
                "See: https://cds.climate.copernicus.eu/how-to-api"
            )
            raise

    def get_weather_data(
        self,
        latitude: float,
        longitude: float,
        date_debut: datetime,
        date_fin: datetime,
        variables: List[str] = None
    ) -> pd.DataFrame:
        """
        Récupère les données météo ERA5 pour une localisation.

        Note: ERA5 est sur une grille ~9km, donc les coordonnées exactes
        sont arrondies à la cellule de grille la plus proche.

        Args:
            latitude: Latitude (°)
            longitude: Longitude (°)
            date_debut: Date début
            date_fin: Date fin
            variables: Variables à récupérer (défaut: precipitation, temperature, evapotranspiration)

        Returns:
            DataFrame avec données journalières
        """
        if variables is None:
            variables = ["precipitation", "temperature", "evapotranspiration"]

        # Validation variables
        invalid_vars = [v for v in variables if v not in self.AVAILABLE_VARIABLES]
        if invalid_vars:
            logger.warning(f"Variables non reconnues: {invalid_vars}")
            variables = [v for v in variables if v in self.AVAILABLE_VARIABLES]

        if not variables:
            logger.error("No valid variables specified")
            return pd.DataFrame()

        # Préparer requête ERA5
        era5_vars = [self.AVAILABLE_VARIABLES[v] for v in variables]

        # Zone géographique (petite bbox autour du point)
        bbox = {
            'north': min(latitude + 0.1, 90),
            'south': max(latitude - 0.1, -90),
            'east': min(longitude + 0.1, 180),
            'west': max(longitude - 0.1, -180),
        }

        logger.info(
            f"Requesting ERA5 data for ({latitude:.4f}, {longitude:.4f}) "
            f"from {date_debut.date()} to {date_fin.date()}"
        )

        try:
            # Créer fichier temporaire pour téléchargement
            with tempfile.NamedTemporaryFile(suffix='.nc', delete=False) as tmp:
                tmp_path = tmp.name

            # Requête CDS
            request = {
                'product_type': ['reanalysis'],
                'variable': era5_vars,
                'year': self._get_years(date_debut, date_fin),
                'month': [f'{m:02d}' for m in range(1, 13)],
                'day': [f'{d:02d}' for d in range(1, 32)],
                'time': ['00:00', '06:00', '12:00', '18:00'],  # 4x par jour
                'area': [bbox['north'], bbox['west'], bbox['south'], bbox['east']],
                'data_format': 'netcdf',
            }

            logger.debug(f"CDS request: {request}")

            # Télécharger
            self.client.retrieve(
                self.DATASET_LAND,
                request,
                tmp_path
            )

            logger.info(f"Downloaded ERA5 data to {tmp_path}")

            # Lire avec xarray
            ds = xr.open_dataset(tmp_path)

            # Extraire point le plus proche
            ds_point = ds.sel(
                latitude=latitude,
                longitude=longitude,
                method='nearest'
            )

            # Convertir en DataFrame
            df = ds_point.to_dataframe().reset_index()

            # Filtrer dates
            df = df[
                (df['time'] >= date_debut) &
                (df['time'] <= date_fin)
            ]

            # Agréger par jour
            df['date'] = pd.to_datetime(df['time']).dt.date
            df_daily = self._aggregate_daily(df, variables)

            # Nettoyer
            ds.close()
            os.unlink(tmp_path)

            logger.info(f"Processed {len(df_daily)} daily records")
            return df_daily

        except Exception as e:
            logger.error(f"Error retrieving ERA5 data: {e}")
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
            return pd.DataFrame()

    def _get_years(self, date_debut: datetime, date_fin: datetime) -> List[str]:
        """Retourne liste des années entre deux dates."""
        return [str(y) for y in range(date_debut.year, date_fin.year + 1)]

    def _aggregate_daily(self, df: pd.DataFrame, variables: List[str]) -> pd.DataFrame:
        """
        Agrège les données horaires en données journalières.

        ERA5 fournit des données toutes les 6h, on agrège en moyennes/sommes journalières.
        """
        agg_dict = {}

        # Précipitations: somme
        if "precipitation" in variables and "total_precipitation" in df.columns:
            agg_dict["precipitation"] = ("total_precipitation", "sum")

        # Température: moyenne
        if "temperature" in variables and "2m_temperature" in df.columns:
            agg_dict["temperature"] = ("2m_temperature", "mean")

        # Évapotranspiration: somme
        if "evapotranspiration" in variables and "potential_evaporation" in df.columns:
            agg_dict["evapotranspiration"] = ("potential_evaporation", "sum")

        # Autres variables (moyenne par défaut)
        # TODO: ajouter autres variables si besoin

        if not agg_dict:
            return pd.DataFrame()

        # Grouper par jour
        df_daily = df.groupby('date').agg(**agg_dict).reset_index()

        # Conversions d'unités
        if "precipitation" in df_daily.columns:
            df_daily["precipitation"] *= 1000  # m -> mm

        if "temperature" in df_daily.columns:
            df_daily["temperature"] -= 273.15  # K -> °C

        if "evapotranspiration" in df_daily.columns:
            df_daily["evapotranspiration"] *= 1000  # m -> mm

        return df_daily

    def get_weather_batch(
        self,
        locations: List[Dict[str, float]],
        date_debut: datetime,
        date_fin: datetime,
        variables: List[str] = None
    ) -> pd.DataFrame:
        """
        Récupère données météo ERA5 pour plusieurs localisations.

        Note: ERA5 ne supporte pas nativement les requêtes multi-points.
        On fait une seule requête pour une bbox qui couvre tous les points,
        puis on extrait chaque point.

        Args:
            locations: Liste de dict avec 'latitude', 'longitude', 'code_station'
            date_debut: Date début
            date_fin: Date fin
            variables: Variables météo

        Returns:
            DataFrame avec toutes les données
        """
        if not locations:
            logger.warning("get_weather_batch called with empty locations list")
            return pd.DataFrame()

        logger.info(
            f"Fetching ERA5 data for {len(locations)} locations "
            f"from {date_debut.date()} to {date_fin.date()}"
        )

        # Calculer bbox englobante
        lats = [float(loc['latitude']) for loc in locations]
        lons = [float(loc['longitude']) for loc in locations]

        bbox = {
            'north': min(max(lats) + 0.5, 90),
            'south': max(min(lats) - 0.5, -90),
            'east': min(max(lons) + 0.5, 180),
            'west': max(min(lons) - 0.5, -180),
        }

        logger.info(f"Requesting ERA5 bbox: {bbox}")

        # Variables
        if variables is None:
            variables = ["precipitation", "temperature", "evapotranspiration"]

        era5_vars = [self.AVAILABLE_VARIABLES[v] for v in variables if v in self.AVAILABLE_VARIABLES]

        if not era5_vars:
            logger.error("No valid ERA5 variables")
            return pd.DataFrame()

        try:
            # Télécharger données ERA5 pour bbox
            with tempfile.NamedTemporaryFile(suffix='.nc', delete=False) as tmp:
                tmp_path = tmp.name

            request = {
                'product_type': ['reanalysis'],
                'variable': era5_vars,
                'year': self._get_years(date_debut, date_fin),
                'month': [f'{m:02d}' for m in range(1, 13)],
                'day': [f'{d:02d}' for d in range(1, 32)],
                'time': ['00:00', '06:00', '12:00', '18:00'],
                'area': [bbox['north'], bbox['west'], bbox['south'], bbox['east']],
                'data_format': 'netcdf',
            }

            logger.info("Downloading ERA5 data (this may take several minutes)...")

            self.client.retrieve(
                self.DATASET_LAND,
                request,
                tmp_path
            )

            logger.info("ERA5 download complete, processing data...")

            # Lire dataset
            ds = xr.open_dataset(tmp_path)

            # Extraire données pour chaque point
            all_data = []

            for i, loc in enumerate(locations, 1):
                try:
                    lat = float(loc['latitude'])
                    lon = float(loc['longitude'])
                    code_station = loc.get('code_station', f'loc_{i}')

                    # Extraire point le plus proche
                    ds_point = ds.sel(
                        latitude=lat,
                        longitude=lon,
                        method='nearest'
                    )

                    # Convertir en DataFrame
                    df = ds_point.to_dataframe().reset_index()

                    # Filtrer dates
                    df = df[
                        (df['time'] >= date_debut) &
                        (df['time'] <= date_fin)
                    ]

                    # Agréger par jour
                    df['date'] = pd.to_datetime(df['time']).dt.date
                    df_daily = self._aggregate_daily(df, variables)

                    # Ajouter identifiants
                    df_daily['code_station'] = code_station
                    df_daily['latitude'] = lat
                    df_daily['longitude'] = lon

                    all_data.append(df_daily)

                    if i % 10 == 0:
                        logger.info(f"Processed {i}/{len(locations)} locations")

                except Exception as e:
                    logger.warning(f"Failed to process location {i}: {e}")
                    continue

            # Nettoyer
            ds.close()
            os.unlink(tmp_path)

            if not all_data:
                logger.warning("No data retrieved for any location")
                return pd.DataFrame()

            result = pd.concat(all_data, ignore_index=True)
            logger.info(
                f"Successfully retrieved {len(result)} records "
                f"from {len(all_data)}/{len(locations)} locations"
            )

            return result

        except Exception as e:
            logger.error(f"Error in ERA5 batch request: {e}")
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
            return pd.DataFrame()
