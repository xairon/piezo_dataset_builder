"""
Client pour récupérer des données météo depuis un fichier ERA5 NetCDF local.

Permet d'utiliser un fichier ERA5 déjà téléchargé au lieu de requêter l'API Copernicus.
Plus rapide et évite les problèmes de quota/rate limiting.
"""

import xarray as xr
import pandas as pd
import numpy as np
from datetime import datetime
from typing import List, Dict, Optional
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


class ERA5LocalClient:
    """Client pour extraire des données météo depuis un fichier ERA5 NetCDF local."""

    # Mapping des variables utilisateur vers les variables ERA5
    AVAILABLE_VARIABLES = {
        "precipitation": "total_precipitation",
        "temperature": "2m_temperature",
        "evapotranspiration": "potential_evaporation",
        "humidity": "2m_dewpoint_temperature",
        "wind": "10m_wind_speed",
        "radiation": "surface_solar_radiation_downwards",
    }

    # Mapping des noms courts NetCDF vers noms longs
    SHORT_TO_LONG = {
        "tp": "total_precipitation",
        "t2m": "2m_temperature",
        "pev": "potential_evaporation",
        "d2m": "2m_dewpoint_temperature",
        "si10": "10m_wind_speed",
        "ssrd": "surface_solar_radiation_downwards",
    }

    def __init__(self, netcdf_path: str):
        """
        Initialise le client ERA5 local.

        Args:
            netcdf_path: Chemin vers le fichier NetCDF ERA5

        Raises:
            FileNotFoundError: Si le fichier n'existe pas
            RuntimeError: Si le fichier ne peut pas être ouvert
        """
        self.netcdf_path = Path(netcdf_path)

        if not self.netcdf_path.exists():
            raise FileNotFoundError(f"NetCDF file not found: {netcdf_path}")

        try:
            # Tester l'ouverture du fichier
            with xr.open_dataset(self.netcdf_path, engine="netcdf4") as ds:
                # Détecter le nom de la dimension temporelle
                if "valid_time" in ds.dims:
                    self.time_dim = "valid_time"
                elif "time" in ds.dims:
                    self.time_dim = "time"
                else:
                    raise RuntimeError(f"No time dimension found in NetCDF file. Available dims: {list(ds.dims.keys())}")

                # Détecter les noms des dimensions spatiales
                if "latitude" in ds.dims:
                    self.lat_dim = "latitude"
                    self.lon_dim = "longitude"
                elif "lat" in ds.dims:
                    self.lat_dim = "lat"
                    self.lon_dim = "lon"
                else:
                    raise RuntimeError(f"No latitude/longitude dimensions found. Available dims: {list(ds.dims.keys())}")

                # Log infos sur le fichier
                time_range = f"{pd.to_datetime(ds[self.time_dim].values[0]).date()} to {pd.to_datetime(ds[self.time_dim].values[-1]).date()}"
                lat_range = f"{float(ds[self.lat_dim].values.min()):.2f} to {float(ds[self.lat_dim].values.max()):.2f}"
                lon_range = f"{float(ds[self.lon_dim].values.min()):.2f} to {float(ds[self.lon_dim].values.max()):.2f}"

                logger.info(f"ERA5 Local file opened successfully")
                logger.info(f"  Time range: {time_range}")
                logger.info(f"  Latitude range: {lat_range}")
                logger.info(f"  Longitude range: {lon_range}")
                logger.info(f"  Variables: {list(ds.data_vars.keys())}")

        except Exception as e:
            logger.error(f"Failed to open NetCDF file: {e}")
            raise RuntimeError(f"Cannot open ERA5 NetCDF file: {e}") from e

    def get_weather_batch(
        self,
        locations: List[Dict[str, float]],
        date_debut: datetime,
        date_fin: datetime,
        variables: List[str] = None,
        progress_callback=None,
    ) -> pd.DataFrame:
        """
        Récupère les données météo pour plusieurs stations depuis le fichier local.

        Args:
            locations: Liste de dicts avec 'latitude', 'longitude', 'code_station'
            date_debut: Date de début
            date_fin: Date de fin
            variables: Liste des variables à récupérer
            progress_callback: Callback pour reporting progress (optional)

        Returns:
            DataFrame avec colonnes: code_station, date, latitude, longitude, variable1, ...
        """
        if not locations:
            return pd.DataFrame()

        if variables is None:
            variables = ["precipitation", "temperature", "evapotranspiration"]

        # Convertir les variables utilisateur en variables ERA5
        era5_vars = []
        for var in variables:
            if var in self.AVAILABLE_VARIABLES:
                era5_var = self.AVAILABLE_VARIABLES[var]
                if era5_var not in era5_vars:
                    era5_vars.append(era5_var)

        if not era5_vars:
            logger.warning("No valid variables specified")
            return pd.DataFrame()

        logger.info(
            f"Extracting ERA5 data from local file for {len(locations)} locations "
            f"from {date_debut.date()} to {date_fin.date()}"
        )

        if progress_callback:
            progress_callback(60, "Loading ERA5 local file...")

        try:
            # Ouvrir le dataset
            ds = xr.open_dataset(self.netcdf_path, engine="netcdf4")

            # Filtrer par dates
            ds_filtered = ds.sel(
                {self.time_dim: slice(
                    date_debut.strftime("%Y-%m-%d"),
                    date_fin.strftime("%Y-%m-%d")
                )}
            )

            if progress_callback:
                progress_callback(70, f"Extracting {len(locations)} station points...")

            # Extraire les données pour chaque station
            dfs = []
            grid_lats = ds_filtered[self.lat_dim].values
            grid_lons = ds_filtered[self.lon_dim].values

            for idx, loc in enumerate(locations, 1):
                lat = loc["latitude"]
                lon = loc["longitude"]
                code = loc.get("code_station", f"{lat}_{lon}")

                # Vérifier si la station est dans les limites du fichier
                if lat < grid_lats.min() or lat > grid_lats.max():
                    logger.warning(f"Station {code} latitude {lat} is outside NetCDF bounds ({grid_lats.min():.2f} to {grid_lats.max():.2f})")
                    continue
                if lon < grid_lons.min() or lon > grid_lons.max():
                    logger.warning(f"Station {code} longitude {lon} is outside NetCDF bounds ({grid_lons.min():.2f} to {grid_lons.max():.2f})")
                    continue

                # Trouver le point de grille le plus proche
                lat_idx = np.abs(grid_lats - lat).argmin()
                lon_idx = np.abs(grid_lons - lon).argmin()
                nearest_lat = float(grid_lats[lat_idx])
                nearest_lon = float(grid_lons[lon_idx])

                # Extraire les données pour ce point
                ds_point = ds_filtered.sel({self.lat_dim: nearest_lat, self.lon_dim: nearest_lon})
                df_point = ds_point.to_dataframe().reset_index()

                # Ajouter les coordonnées et le code station
                df_point["latitude"] = nearest_lat
                df_point["longitude"] = nearest_lon
                df_point["code_station"] = code

                dfs.append(df_point)

                if progress_callback and idx % 10 == 0:
                    pct = 70 + int((idx / len(locations)) * 10)
                    progress_callback(pct, f"Extracted {idx}/{len(locations)} stations...")

            ds.close()

            if not dfs:
                logger.warning("No stations extracted from NetCDF file (all out of bounds?)")
                return pd.DataFrame()

            df_all = pd.concat(dfs, ignore_index=True)

            logger.info(f"Extracted {len(dfs)} stations, {len(df_all)} total records from local ERA5 file")

            # Nettoyer les noms de colonnes
            df_all = df_all.rename(
                columns={
                    self.time_dim: "date",
                    "time": "date",
                    self.lat_dim: "latitude",
                    self.lon_dim: "longitude"
                }
            )

            # Renommer les variables courtes en variables longues
            df_all = df_all.rename(columns=self.SHORT_TO_LONG)

            # Décaler la date de -1 jour car les valeurs à 00:00 du jour J
            # représentent le cumul du jour J-1 (pour précip, ET, radiation)
            df_all["date"] = pd.to_datetime(df_all["date"]) - pd.Timedelta(days=1)

            # Convertir les unités et agréger par jour
            df_all = self._process_era5_data(df_all, era5_vars)

            if progress_callback:
                progress_callback(80, "ERA5 data processed successfully")

            # Réorganiser les colonnes
            cols = ["code_station", "date", "latitude", "longitude"]
            other_cols = [c for c in df_all.columns if c not in cols]
            df_all = df_all[cols + other_cols]

            return df_all

        except Exception as e:
            logger.error(f"Failed to extract data from local ERA5 file: {e}")
            raise RuntimeError(f"Error reading local ERA5 file: {e}") from e

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
        # Supprimer les colonnes inutiles (expver, number)
        df = df.drop(columns=["expver", "number"], errors="ignore")

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
        group_cols = ["code_station", "date", "latitude", "longitude"]
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
