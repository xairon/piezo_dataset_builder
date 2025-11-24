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
import zipfile

logger = logging.getLogger(__name__)


class ERA5Client:
    """Client pour télécharger des données météo depuis ERA5 (Copernicus)."""

    DATASET_LAND = "reanalysis-era5-land"

    # Mapping des variables utilisateur vers les variables ERA5
    AVAILABLE_VARIABLES = {
        "precipitation": "total_precipitation",
        "temperature": "2m_temperature",
        "evapotranspiration": "potential_evaporation",
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
                    verify=False  # Désactiver vérification SSL (problème certificat auto-signé)
                )
            else:
                # Utiliser le fichier ~/.cdsapirc par défaut
                logger.info("Using credentials from ~/.cdsapirc")
                self.client = cdsapi.Client(verify=False)

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
        progress_callback=None,
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

        # Validation: ERA5 data is not available for very recent dates (5-day delay minimum)
        today = datetime.now()
        max_date = today - timedelta(days=7)  # Use 7 days to be safe

        if date_fin > max_date:
            logger.warning(
                f"ERA5 data requested until {date_fin.date()}, but data is only available "
                f"up to approximately {max_date.date()} (7-day delay). "
                f"Adjusting end date to {max_date.date()}."
            )
            date_fin = max_date

        if date_debut > max_date:
            raise ValueError(
                f"Cannot fetch ERA5 data: start date {date_debut.date()} is too recent. "
                f"ERA5 has approximately a 5-7 day delay. "
                f"Data is available up to approximately {max_date.date()}."
            )

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

        # Télécharger les données pour toute la bbox, avec les locations pour extraction optimisée
        df_all = self._fetch_era5_data(bbox, date_debut, date_fin, era5_vars, locations, progress_callback)

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
        locations: List[Dict[str, float]] = None,
        progress_callback=None,
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
        # Découper en chunks de 2 ans max pour éviter les limites de taille
        CHUNK_YEARS = 2
        years = list(range(date_debut.year, date_fin.year + 1))

        if len(years) > CHUNK_YEARS:
            # Créer des chunks de 5 ans
            chunks = []
            for i in range(0, len(years), CHUNK_YEARS):
                chunk_years = years[i:i + CHUNK_YEARS]
                chunk_start = datetime(chunk_years[0], 1, 1) if chunk_years[0] > date_debut.year else date_debut
                chunk_end = datetime(chunk_years[-1], 12, 31) if chunk_years[-1] < date_fin.year else date_fin
                chunks.append((chunk_start, chunk_end, chunk_years))

            logger.info(f"Splitting request into {len(chunks)} chunks of up to {CHUNK_YEARS} years")
            dfs = []
            for i, (chunk_start, chunk_end, chunk_years) in enumerate(chunks, 1):
                years_str = f"{chunk_years[0]}-{chunk_years[-1]}" if len(chunk_years) > 1 else str(chunk_years[0])
                msg = f"ERA5: Downloading chunk {i}/{len(chunks)} ({years_str})"
                logger.info(f"[ERA5 Progress] {msg}")
                if progress_callback:
                    # Progress entre 60% et 80% pendant le téléchargement ERA5
                    pct = 60 + int((i - 1) / len(chunks) * 20)
                    progress_callback(pct, msg)

                try:
                    df_chunk = self._fetch_era5_chunk(bbox, chunk_start, chunk_end, era5_vars, locations)
                    if not df_chunk.empty:
                        dfs.append(df_chunk)
                        logger.info(f"[ERA5 Progress] Chunk {years_str} complete - {len(df_chunk)} records")
                except Exception as e:
                    logger.error(f"Failed to download chunk {i}/{len(chunks)} ({years_str}): {e}")
                    # Si on a déjà des données, les retourner avec une exception qui contient les données partielles
                    if dfs:
                        partial_df = pd.concat(dfs, ignore_index=True)
                        logger.warning(f"Returning {len(dfs)} successfully downloaded chunks before error")
                        # Créer une exception personnalisée qui contient les données partielles
                        error = RuntimeError(f"ERA5 download failed at chunk {i}/{len(chunks)}: {e}")
                        error.partial_data = partial_df
                        raise error from e
                    else:
                        # Pas de données récupérées du tout, re-raise l'exception originale
                        raise

            return pd.concat(dfs, ignore_index=True) if dfs else pd.DataFrame()

        return self._fetch_era5_chunk(bbox, date_debut, date_fin, era5_vars, locations)

    def _fetch_era5_chunk(
        self,
        bbox: Dict[str, float],
        date_debut: datetime,
        date_fin: datetime,
        era5_vars: List[str],
        locations: List[Dict[str, float]] = None,
    ) -> pd.DataFrame:
        """
        Télécharge les données ERA5 pour une période (jusqu'à 5 ans).
        """
        # Créer un nom de fichier temporaire unique
        # Note: On n'utilise pas NamedTemporaryFile car il garde le fichier ouvert sur Windows,
        # ce qui empêche cdsapi d'écrire dedans
        temp_dir = tempfile.gettempdir()
        tmp_fd, tmp_path = tempfile.mkstemp(suffix=".nc", dir=temp_dir)
        os.close(tmp_fd)  # Fermer immédiatement le descripteur de fichier
        os.remove(tmp_path)  # Supprimer le fichier vide créé par mkstemp

        download_path = None
        nc_path = None

        try:
            # Générer la liste des années
            years = list(range(date_debut.year, date_fin.year + 1))

            # Pour un chunk multi-années, on demande tous les mois/jours
            # Le filtrage par date exacte se fait après avec xarray
            if len(years) > 1:
                months = list(range(1, 13))
                days = list(range(1, 32))
            else:
                # Pour une seule année, optimiser les mois/jours
                months = set()
                days = set()
                current = date_debut
                while current <= date_fin:
                    months.add(current.month)
                    days.add(current.day)
                    current += timedelta(days=1)
                months = sorted(months)
                days = sorted(days)

            # Préparer la requête CDS
            request = {
                "variable": era5_vars,
                "year": [str(y) for y in years],
                "month": [f"{m:02d}" for m in months],
                "day": [f"{d:02d}" for d in days],
                "time": ["00:00"],  # Cumul journalier (00h = cumul des 24h précédentes)
                "area": [
                    bbox["north"],
                    bbox["west"],
                    bbox["south"],
                    bbox["east"],
                ],
                "format": "netcdf",
            }

            years_str = f"{years[0]}-{years[-1]}" if len(years) > 1 else str(years[0])
            logger.info(f"Downloading ERA5 data for {years_str} ({len(years)} years, {len(months)} months, {len(days)} days)...")

            # Télécharger dans un fichier temporaire (peut être .zip ou .nc)
            download_path = tmp_path.replace(".nc", ".download")
            self.client.retrieve(self.DATASET_LAND, request, download_path)

            # Vérifier si c'est un zip et extraire si nécessaire
            nc_path = tmp_path
            if zipfile.is_zipfile(download_path):
                logger.info("Extracting downloaded zip file...")
                with zipfile.ZipFile(download_path, 'r') as zf:
                    # Trouver le fichier .nc dans le zip
                    nc_files = [f for f in zf.namelist() if f.endswith('.nc')]
                    if nc_files:
                        zf.extract(nc_files[0], os.path.dirname(tmp_path))
                        nc_path = os.path.join(os.path.dirname(tmp_path), nc_files[0])
                    else:
                        raise RuntimeError("No NetCDF file found in downloaded zip")
                os.remove(download_path)
            else:
                # Fichier déjà en NetCDF - simplement renommer
                os.rename(download_path, nc_path)

            # Charger le NetCDF avec xarray
            ds = xr.open_dataset(nc_path, engine="netcdf4")

            # Déterminer le nom de la dimension temporelle (time ou valid_time)
            time_dim = "valid_time" if "valid_time" in ds.dims else "time"

            # Filtrer par dates
            ds = ds.sel(
                {time_dim: slice(
                    date_debut.strftime("%Y-%m-%d"), date_fin.strftime("%Y-%m-%d")
                )}
            )

            # Si on a des locations, extraire uniquement les points les plus proches
            # pour éviter de charger toute la grille en mémoire
            if locations:
                dfs = []
                grid_lats = ds.latitude.values
                grid_lons = ds.longitude.values

                for loc in locations:
                    # Trouver le point de grille le plus proche
                    lat_idx = np.abs(grid_lats - loc["latitude"]).argmin()
                    lon_idx = np.abs(grid_lons - loc["longitude"]).argmin()
                    nearest_lat = grid_lats[lat_idx]
                    nearest_lon = grid_lons[lon_idx]

                    # Extraire les données pour ce point
                    ds_point = ds.sel(latitude=nearest_lat, longitude=nearest_lon)
                    df_point = ds_point.to_dataframe().reset_index()
                    df_point["latitude"] = nearest_lat
                    df_point["longitude"] = nearest_lon
                    dfs.append(df_point)

                df = pd.concat(dfs, ignore_index=True)
                logger.info(f"Extracted {len(locations)} station points from ERA5 grid")
            else:
                # Convertir toute la grille en DataFrame
                df = ds.to_dataframe().reset_index()

            # Nettoyer les noms de colonnes
            df = df.rename(
                columns={time_dim: "date", "time": "date", "latitude": "latitude", "longitude": "longitude"}
            )

            # Décaler la date de -1 jour car les valeurs à 00:00 du jour J
            # représentent le cumul du jour J-1 (pour précip, ET, radiation)
            df["date"] = pd.to_datetime(df["date"]) - pd.Timedelta(days=1)

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
                    "X Erreur 403 Forbidden : Vous devez accepter la licence ERA5-Land.\n\n"
                    "-> Cliquez ici pour accepter (gratuit, 1 clic) :\n"
                    "https://cds.climate.copernicus.eu/datasets/reanalysis-era5-land?tab=download#manage-licences\n\n"
                    "Apres avoir accepte, reessayez de lancer le build."
                ) from e
            elif "401" in error_msg or "Unauthorized" in error_msg:
                raise RuntimeError(
                    "X Erreur 401 Unauthorized : Token API invalide ou expire.\n\n"
                    "Verifiez votre token sur : https://cds.climate.copernicus.eu/profile"
                ) from e
            elif "No space left on device" in error_msg or "MARS" in error_msg:
                raise RuntimeError(
                    "X Erreur serveur ERA5 (Copernicus CDS) : Le serveur rencontre des problemes techniques.\n\n"
                    "Causes possibles :\n"
                    "1. Serveur MARS saturé (No space left on device)\n"
                    "2. Données trop récentes demandées (ERA5 a un délai de 5-7 jours)\n"
                    "3. Requête trop volumineuse\n\n"
                    "Solutions :\n"
                    "- Réessayez dans quelques heures\n"
                    "- Réduisez la période de temps demandée\n"
                    "- Vérifiez que la date de fin n'est pas trop récente (aujourd'hui - 7 jours minimum)\n\n"
                    f"Erreur technique : {error_msg[:500]}"
                ) from e
            else:
                raise RuntimeError(
                    f"Failed to download ERA5 data: {e}. "
                    "Please check your internet connection and CDS credentials."
                ) from e

        finally:
            # Nettoyer les fichiers temporaires
            for path in [tmp_path, download_path, nc_path]:
                if path and os.path.exists(path):
                    try:
                        os.remove(path)
                    except Exception:
                        pass

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

        # Mapping des noms courts ERA5 (NetCDF) vers noms longs
        short_to_long = {
            "tp": "total_precipitation",
            "t2m": "2m_temperature",
            "pev": "potential_evaporation",
            "d2m": "2m_dewpoint_temperature",
            "si10": "10m_wind_speed",
            "ssrd": "surface_solar_radiation_downwards",
        }
        df = df.rename(columns=short_to_long)

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
