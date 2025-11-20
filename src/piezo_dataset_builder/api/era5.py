"""
Client pour récupérer des données météo depuis ERA5 (Copernicus Climate Data Store).

ERA5 est la réanalyse atmosphérique de 5ème génération de l'ECMWF.
Données disponibles depuis 1940 jusqu'à présent avec une résolution de ~9km.
"""

import cdsapi
import xarray as xr
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import logging
import os
import tempfile

logger = logging.getLogger(__name__)


class ERA5Client:
    """Client pour télécharger des données météo depuis ERA5 (Copernicus)."""

    DATASET_LAND = "reanalysis-era5-land"

    # Mapping des variables utilisateur vers les variables ERA5
    AVAILABLE_VARIABLES = {
        "precipitation": "total_precipitation",
        "temperature": "2m_temperature",
        "evapotranspiration": "potential_evaporation",
        "temperature_min": "2m_temperature",  # Même variable, agrégation différente
        "temperature_max": "2m_temperature",
        "humidity": "2m_dewpoint_temperature",  # Utilisé pour calculer l'humidité
        "wind": "10m_wind_speed",
        "radiation": "surface_solar_radiation_downwards",
    }

    def __init__(self, api_token: str = None):
        """
        Initialise le client ERA5.

        Args:
            api_token: Token API du compte Copernicus CDS (optionnel, sinon utilise ~/.cdsapirc)

        Si api_token est fourni, il sera utilisé directement.
        Sinon, le client cherchera les credentials dans ~/.cdsapirc

        Note: Le nouveau format Copernicus n'utilise plus d'UID, juste un token unique.
        """
        try:
            if api_token:
                # Utiliser le token fourni directement
                logger.info("Using provided Copernicus CDS API token")
                self.client = cdsapi.Client(
                    url="https://cds.climate.copernicus.eu/api",
                    key=api_token,
                    verify=True
                )
            else:
                # Utiliser le fichier ~/.cdsapirc par défaut
                logger.info("Using credentials from ~/.cdsapirc")
                self.client = cdsapi.Client()

            logger.info("ERA5 client initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize ERA5 client: {e}")
            raise RuntimeError(
                "Could not initialize ERA5 client. "
                "Please provide a valid Copernicus CDS API token. "
                "You can get it from: https://cds.climate.copernicus.eu/"
            ) from e

    def get_weather_data(
        self,
        latitude: float,
        longitude: float,
        date_debut: datetime,
        date_fin: datetime,
        variables: List[str] = None,
    ) -> pd.DataFrame:
        """
        Récupère les données météo pour une station.

        Args:
            latitude: Latitude (degrés)
            longitude: Longitude (degrés)
            date_debut: Date de début
            date_fin: Date de fin
            variables: Liste des variables à récupérer

        Returns:
            DataFrame avec colonnes: date, variable1, variable2, ...
        """
        if variables is None:
            variables = ["precipitation", "temperature", "evapotranspiration"]

        # Convertir les variables utilisateur en variables ERA5
        era5_vars = []
        for var in variables:
            if var in self.AVAILABLE_VARIABLES:
                era5_var = self.AVAILABLE_VARIABLES[var]
                if era5_var not in era5_vars:
                    era5_vars.append(era5_var)
            else:
                logger.warning(f"Unknown variable: {var}, skipping")

        if not era5_vars:
            logger.error("No valid variables specified")
            return pd.DataFrame()

        logger.info(
            f"Fetching ERA5 data for point ({latitude}, {longitude}) "
            f"from {date_debut.date()} to {date_fin.date()}"
        )

        # Créer une petite bounding box autour du point
        bbox = {
            "north": min(latitude + 0.25, 90),
            "south": max(latitude - 0.25, -90),
            "east": min(longitude + 0.25, 180),
            "west": max(longitude - 0.25, -180),
        }

        # Télécharger les données
        df = self._fetch_era5_data(bbox, date_debut, date_fin, era5_vars)

        if df.empty:
            return df

        # Extraire les données pour le point le plus proche
        df_point = df[
            (df["latitude"] == df["latitude"].iloc[0])
            & (df["longitude"] == df["longitude"].iloc[0])
        ].copy()

        # Supprimer les coordonnées (on a un seul point)
        df_point = df_point.drop(columns=["latitude", "longitude"], errors="ignore")

        return df_point

    def get_weather_batch(
        self,
        locations: List[Dict[str, float]],
        date_debut: datetime,
        date_fin: datetime,
        variables: List[str] = None,
    ) -> pd.DataFrame:
        """
        Récupère les données météo pour plusieurs stations en une requête.

        Plus efficace que de faire plusieurs requêtes individuelles.

        Args:
            locations: Liste de dicts avec 'latitude', 'longitude', 'code_station'
            date_debut: Date de début
            date_fin: Date de fin
            variables: Liste des variables à récupérer

        Returns:
            DataFrame avec colonnes: code_station, date, latitude, longitude, variable1, ...
        """
        if not locations:
            return pd.DataFrame()

        if variables is None:
            variables = ["precipitation", "temperature", "evapotranspiration"]

        # Convertir les variables
        era5_vars = []
        for var in variables:
            if var in self.AVAILABLE_VARIABLES:
                era5_var = self.AVAILABLE_VARIABLES[var]
                if era5_var not in era5_vars:
                    era5_vars.append(era5_var)

        if not era5_vars:
            return pd.DataFrame()

        logger.info(
            f"Fetching ERA5 data for {len(locations)} locations "
            f"from {date_debut.date()} to {date_fin.date()}"
        )

        # Calculer la bounding box englobant toutes les stations
        lats = [loc["latitude"] for loc in locations]
        lons = [loc["longitude"] for loc in locations]

        bbox = {
            "north": min(max(lats) + 0.5, 90),
            "south": max(min(lats) - 0.5, -90),
            "east": min(max(lons) + 0.5, 180),
            "west": max(min(lons) - 0.5, -180),
        }

        # Télécharger les données pour toute la bbox
        df_all = self._fetch_era5_data(bbox, date_debut, date_fin, era5_vars)

        if df_all.empty:
            return df_all

        # Extraire les données pour chaque station
        dfs = []
        for loc in locations:
            lat = loc["latitude"]
            lon = loc["longitude"]
            code = loc.get("code_station", f"{lat}_{lon}")

            # Trouver le point le plus proche dans la grille ERA5
            df_point = self._extract_nearest_point(df_all, lat, lon)

            if not df_point.empty:
                df_point["code_station"] = code
                dfs.append(df_point)

        if not dfs:
            return pd.DataFrame()

        df_result = pd.concat(dfs, ignore_index=True)

        # Réorganiser les colonnes
        cols = ["code_station", "date", "latitude", "longitude"]
        other_cols = [c for c in df_result.columns if c not in cols]
        df_result = df_result[cols + other_cols]

        return df_result

    def _fetch_era5_data(
        self,
        bbox: Dict[str, float],
        date_debut: datetime,
        date_fin: datetime,
        era5_vars: List[str],
    ) -> pd.DataFrame:
        """
        Télécharge les données ERA5 pour une bounding box.

        Args:
            bbox: Dict avec 'north', 'south', 'east', 'west'
            date_debut: Date de début
            date_fin: Date de fin
            era5_vars: Variables ERA5 à récupérer

        Returns:
            DataFrame avec toutes les données
        """
        # Créer fichier temporaire pour le NetCDF
        with tempfile.NamedTemporaryFile(suffix=".nc", delete=False) as tmp:
            tmp_path = tmp.name

        try:
            # Préparer la requête CDS
            request = {
                "variable": era5_vars,
                "year": [str(year) for year in range(date_debut.year, date_fin.year + 1)],
                "month": [f"{m:02d}" for m in range(1, 13)],
                "day": [f"{d:02d}" for d in range(1, 32)],
                "time": [f"{h:02d}:00" for h in [0, 6, 12, 18]],  # 6-hourly
                "area": [
                    bbox["north"],
                    bbox["west"],
                    bbox["south"],
                    bbox["east"],
                ],
                "format": "netcdf",
            }

            logger.info(f"Downloading ERA5 data from CDS (this may take several minutes)...")
            self.client.retrieve(self.DATASET_LAND, request, tmp_path)

            # Charger le NetCDF avec xarray
            ds = xr.open_dataset(tmp_path)

            # Filtrer par dates
            ds = ds.sel(
                time=slice(
                    date_debut.strftime("%Y-%m-%d"), date_fin.strftime("%Y-%m-%d")
                )
            )

            # Convertir en DataFrame
            df = ds.to_dataframe().reset_index()

            # Nettoyer les noms de colonnes
            df = df.rename(
                columns={"time": "date", "latitude": "latitude", "longitude": "longitude"}
            )

            # Convertir les unités et agréger par jour
            df = self._process_era5_data(df, era5_vars)

            ds.close()

            logger.info(f"Loaded {len(df)} records from ERA5")

            return df

        except Exception as e:
            error_msg = str(e)
            logger.error(f"Failed to fetch ERA5 data: {e}")

            # Message d'erreur personnalisé selon le type d'erreur
            if "403" in error_msg and "Forbidden" in error_msg:
                raise RuntimeError(
                    "❌ Erreur 403 Forbidden : Vous devez accepter la licence ERA5-Land.\n\n"
                    "👉 Cliquez ici pour accepter (gratuit, 1 clic) :\n"
                    "https://cds.climate.copernicus.eu/datasets/reanalysis-era5-land?tab=download#manage-licences\n\n"
                    "Après avoir accepté, réessayez de lancer le build."
                ) from e
            elif "401" in error_msg or "Unauthorized" in error_msg:
                raise RuntimeError(
                    "❌ Erreur 401 Unauthorized : Token API invalide ou expiré.\n\n"
                    "Vérifiez votre token sur : https://cds.climate.copernicus.eu/profile"
                ) from e
            else:
                raise RuntimeError(
                    f"Failed to download ERA5 data: {e}. "
                    "Please check your internet connection and CDS credentials."
                ) from e

        finally:
            # Nettoyer le fichier temporaire
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

    def _process_era5_data(
        self, df: pd.DataFrame, era5_vars: List[str]
    ) -> pd.DataFrame:
        """
        Traite les données ERA5 : conversions d'unités et agrégation journalière.

        Args:
            df: DataFrame brut depuis ERA5
            era5_vars: Variables ERA5 présentes

        Returns:
            DataFrame traité et agrégé par jour
        """
        # Convertir la date en date uniquement (pas de temps)
        df["date"] = pd.to_datetime(df["date"]).dt.date

        # Conversions d'unités
        if "total_precipitation" in df.columns:
            # ERA5 donne en mètres, on veut en mm
            df["precipitation"] = df["total_precipitation"] * 1000
            df = df.drop(columns=["total_precipitation"])

        if "2m_temperature" in df.columns:
            # ERA5 donne en Kelvin, on veut en Celsius
            df["temperature"] = df["2m_temperature"] - 273.15
            df = df.drop(columns=["2m_temperature"])

        if "potential_evaporation" in df.columns:
            # ERA5 donne en mètres (négatif), on veut en mm positif
            df["evapotranspiration"] = -df["potential_evaporation"] * 1000
            df = df.drop(columns=["potential_evaporation"])

        if "2m_dewpoint_temperature" in df.columns:
            # Calculer l'humidité relative depuis température et point de rosée
            # Formule simplifiée : RH = 100 * (exp((17.625*Td)/(243.04+Td)) / exp((17.625*T)/(243.04+T)))
            temp_k = df["2m_temperature"] if "2m_temperature" in df.columns else df["temperature"] + 273.15
            dew_k = df["2m_dewpoint_temperature"]
            temp_c = temp_k - 273.15
            dew_c = dew_k - 273.15

            df["humidity"] = 100 * (
                np.exp((17.625 * dew_c) / (243.04 + dew_c))
                / np.exp((17.625 * temp_c) / (243.04 + temp_c))
            )
            df = df.drop(columns=["2m_dewpoint_temperature"])

        if "10m_wind_speed" in df.columns:
            df["wind"] = df["10m_wind_speed"]
            df = df.drop(columns=["10m_wind_speed"])

        if "surface_solar_radiation_downwards" in df.columns:
            # ERA5 donne en J/m², on veut en MJ/m² par jour
            df["radiation"] = df["surface_solar_radiation_downwards"] / 1_000_000
            df = df.drop(columns=["surface_solar_radiation_downwards"])

        # Agrégation journalière
        group_cols = ["date", "latitude", "longitude"]
        agg_dict = {}

        # Somme pour précipitations, ET, radiation
        for col in ["precipitation", "evapotranspiration", "radiation"]:
            if col in df.columns:
                agg_dict[col] = "sum"

        # Moyenne pour température, vent, humidité
        for col in ["temperature", "wind", "humidity"]:
            if col in df.columns:
                agg_dict[col] = "mean"

        if agg_dict:
            df = df.groupby(group_cols, as_index=False).agg(agg_dict)

        return df

    def _extract_nearest_point(
        self, df: pd.DataFrame, latitude: float, longitude: float
    ) -> pd.DataFrame:
        """
        Extrait les données pour le point le plus proche dans la grille ERA5.

        Args:
            df: DataFrame avec toutes les données
            latitude: Latitude cible
            longitude: Longitude cible

        Returns:
            DataFrame pour le point le plus proche
        """
        if df.empty:
            return df

        # Calculer la distance à chaque point de grille
        unique_coords = df[["latitude", "longitude"]].drop_duplicates()

        distances = np.sqrt(
            (unique_coords["latitude"] - latitude) ** 2
            + (unique_coords["longitude"] - longitude) ** 2
        )

        # Trouver le point le plus proche
        nearest_idx = distances.idxmin()
        nearest_lat = unique_coords.loc[nearest_idx, "latitude"]
        nearest_lon = unique_coords.loc[nearest_idx, "longitude"]

        # Extraire les données pour ce point
        df_point = df[
            (df["latitude"] == nearest_lat) & (df["longitude"] == nearest_lon)
        ].copy()

        return df_point
