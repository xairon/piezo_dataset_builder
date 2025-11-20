"""
Client API Open-Meteo - Données météorologiques historiques avec retry logic.

Documentation : https://open-meteo.com/en/docs/historical-weather-api

Features:
- Automatic retry logic
- Rate limiting (10,000 requests/day free tier)
- Comprehensive logging
- GPS coordinates validation
"""

import requests
import pandas as pd
from datetime import datetime
from typing import List, Dict, Any, Optional
import logging
import time
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logger = logging.getLogger(__name__)


class OpenMeteoClient:
    """
    Client pour l'API Open-Meteo avec retry logic et rate limiting.

    Limites API (free tier):
    - 10,000 requêtes par jour
    - Pas de rate limit par seconde, mais recommandation de ne pas spammer
    """

    BASE_URL = "https://archive-api.open-meteo.com/v1/archive"

    # Variables météo disponibles et leurs noms dans l'API
    AVAILABLE_VARIABLES = {
        "precipitation": "precipitation_sum",              # Précipitations journalières (mm)
        "temperature": "temperature_2m_mean",              # Température moyenne (°C)
        "temperature_min": "temperature_2m_min",           # Température min (°C)
        "temperature_max": "temperature_2m_max",           # Température max (°C)
        "evapotranspiration": "et0_fao_evapotranspiration",  # ET référence (mm)
        "humidity": "relative_humidity_2m_mean",           # Humidité relative (%)
        "wind": "wind_speed_10m_mean",                     # Vitesse vent (km/h)
        "radiation": "shortwave_radiation_sum",            # Rayonnement solaire (MJ/m²)
    }

    def __init__(self, timeout: int = 30, rate_limit: float = 2.0):
        """
        Initialise le client Open-Meteo.

        Args:
            timeout: Timeout requêtes HTTP en secondes
            rate_limit: Délai minimum entre requêtes (secondes) pour respecter API limits
        """
        self.timeout = timeout
        self.rate_limit = rate_limit
        self._last_request_time = 0.0

        # Setup session with connection pooling and retry logic
        self.session = requests.Session()

        # Retry strategy
        retry_strategy = Retry(
            total=3,  # Max 3 retries (moins que HubEau car API plus stable)
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET"]
        )

        adapter = HTTPAdapter(
            max_retries=retry_strategy,
            pool_connections=10,
            pool_maxsize=10
        )

        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)

        logger.info(
            f"Initialized OpenMeteoClient "
            f"(timeout={timeout}s, rate_limit={rate_limit}s)"
        )

    def _apply_rate_limit(self):
        """Apply rate limiting between requests."""
        elapsed = time.time() - self._last_request_time
        if elapsed < self.rate_limit:
            sleep_time = self.rate_limit - elapsed
            time.sleep(sleep_time)
        self._last_request_time = time.time()

    def _validate_coordinates(self, latitude: float, longitude: float) -> bool:
        """
        Validate GPS coordinates.

        Args:
            latitude: Latitude in degrees
            longitude: Longitude in degrees

        Returns:
            True if valid, False otherwise
        """
        if not isinstance(latitude, (int, float)) or not isinstance(longitude, (int, float)):
            logger.error(f"Invalid coordinate types: lat={type(latitude)}, lon={type(longitude)}")
            return False

        if not (-90 <= latitude <= 90):
            logger.error(f"Invalid latitude: {latitude} (must be between -90 and 90)")
            return False

        if not (-180 <= longitude <= 180):
            logger.error(f"Invalid longitude: {longitude} (must be between -180 and 180)")
            return False

        return True

    def _split_date_range(self, date_debut: datetime, date_fin: datetime, chunk_years: int = 10):
        """
        Divise une plage de dates en chunks pour réduire le poids des requêtes API.

        Args:
            date_debut: Date de début
            date_fin: Date de fin
            chunk_years: Nombre d'années par chunk

        Returns:
            Liste de tuples (start_date, end_date)
        """
        from dateutil.relativedelta import relativedelta

        chunks = []
        current_start = date_debut

        while current_start < date_fin:
            # Calculer la fin du chunk (current_start + chunk_years)
            current_end = min(
                current_start + relativedelta(years=chunk_years),
                date_fin
            )
            chunks.append((current_start, current_end))
            current_start = current_end + relativedelta(days=1)

        return chunks

    def get_weather_data(
        self,
        latitude: float,
        longitude: float,
        date_debut: datetime,
        date_fin: datetime,
        variables: List[str] = None,
        chunk_years: int = 10
    ) -> pd.DataFrame:
        """
        Récupère les données météo pour une localisation.

        Pour éviter les erreurs 429 (rate limit), les longues périodes sont divisées
        en chunks de chunk_years années.

        Args:
            latitude: Latitude (degrés, -90 à 90)
            longitude: Longitude (degrés, -180 à 180)
            date_debut: Date de début
            date_fin: Date de fin
            variables: Liste de variables (par défaut: precipitation, temperature, ET)
            chunk_years: Nombre d'années par chunk (défaut: 10)

        Returns:
            DataFrame avec données météo journalières
        """
        # Validate coordinates
        if not self._validate_coordinates(latitude, longitude):
            return pd.DataFrame()

        # Variables par défaut
        if variables is None:
            variables = ["precipitation", "temperature", "evapotranspiration"]

        # Validation variables
        invalid_vars = [v for v in variables if v not in self.AVAILABLE_VARIABLES]
        if invalid_vars:
            logger.warning(f"Variables non reconnues (ignorées): {invalid_vars}")
            variables = [v for v in variables if v in self.AVAILABLE_VARIABLES]

        if not variables:
            logger.warning("No valid variables specified")
            return pd.DataFrame()

        # Diviser en chunks si la période est longue
        years_span = (date_fin - date_debut).days / 365.25

        if years_span > chunk_years:
            logger.debug(
                f"Splitting {years_span:.1f} years into chunks of {chunk_years} years "
                f"to reduce API request weight"
            )
            chunks = self._split_date_range(date_debut, date_fin, chunk_years)
            all_chunks = []

            for chunk_start, chunk_end in chunks:
                chunk_df = self._fetch_weather_chunk(
                    latitude, longitude, chunk_start, chunk_end, variables
                )
                if not chunk_df.empty:
                    all_chunks.append(chunk_df)

            if not all_chunks:
                return pd.DataFrame()

            return pd.concat(all_chunks, ignore_index=True)
        else:
            # Période courte, requête directe
            return self._fetch_weather_chunk(
                latitude, longitude, date_debut, date_fin, variables
            )

    def _fetch_weather_chunk(
        self,
        latitude: float,
        longitude: float,
        date_debut: datetime,
        date_fin: datetime,
        variables: List[str]
    ) -> pd.DataFrame:
        """
        Récupère un chunk de données météo (méthode interne).

        Args:
            latitude: Latitude
            longitude: Longitude
            date_debut: Date de début
            date_fin: Date de fin
            variables: Liste de variables validées

        Returns:
            DataFrame avec données météo
        """
        # Mapping vers noms API
        api_variables = [self.AVAILABLE_VARIABLES[v] for v in variables]

        # Paramètres requête
        params = {
            "latitude": round(latitude, 6),  # Limit precision
            "longitude": round(longitude, 6),
            "start_date": date_debut.strftime("%Y-%m-%d"),
            "end_date": date_fin.strftime("%Y-%m-%d"),
            "daily": ",".join(api_variables),
            "timezone": "Europe/Paris"
        }

        # Apply rate limiting
        self._apply_rate_limit()

        try:
            logger.debug(
                f"Fetching weather data for ({latitude:.4f}, {longitude:.4f}) "
                f"from {date_debut.date()} to {date_fin.date()}"
            )

            response = self.session.get(self.BASE_URL, params=params, timeout=self.timeout)
            response.raise_for_status()

            data = response.json()

            # Validation de la réponse
            if 'daily' not in data or 'time' not in data['daily']:
                logger.error(f"Malformed API response: missing 'daily' or 'time' keys")
                return pd.DataFrame()

            # Construire DataFrame
            # pd.to_datetime() retourne déjà un DatetimeIndex/Series
            time_data = pd.to_datetime(data['daily']['time'])
            df_data = {
                'date': time_data.date if hasattr(time_data, 'date') else [d.date() for d in time_data]
            }

            # Ajouter variables avec noms simplifiés
            for var_key, api_var in zip(variables, api_variables):
                if api_var in data['daily']:
                    df_data[var_key] = data['daily'][api_var]
                else:
                    logger.warning(f"Variable '{api_var}' not found in API response")

            df = pd.DataFrame(df_data)
            logger.debug(f"Retrieved {len(df)} weather records")

            return df

        except requests.exceptions.Timeout as e:
            logger.error(
                f"Timeout fetching weather data for ({latitude}, {longitude}): {e}"
            )
            return pd.DataFrame()

        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 429:
                logger.error(
                    "Open-Meteo API rate limit exceeded (429). "
                    "Free tier weight limit exceeded. Try reducing date range or variables."
                )
            else:
                logger.error(
                    f"HTTP error {e.response.status_code} for ({latitude}, {longitude}): {e}"
                )
            return pd.DataFrame()

        except requests.exceptions.RequestException as e:
            logger.error(
                f"Request error for ({latitude}, {longitude}): {e}"
            )
            return pd.DataFrame()

        except (KeyError, ValueError) as e:
            logger.error(f"Error parsing weather data: {e}")
            return pd.DataFrame()

    def get_weather_batch(
        self,
        locations: List[Dict[str, float]],
        date_debut: datetime,
        date_fin: datetime,
        variables: List[str] = None
    ) -> pd.DataFrame:
        """
        Récupère données météo pour plusieurs localisations.

        Args:
            locations: Liste de dict avec 'latitude', 'longitude', 'code_station'
            date_debut: Date de début
            date_fin: Date de fin
            variables: Variables météo à récupérer

        Returns:
            DataFrame avec toutes les données météo
        """
        if not locations:
            logger.warning("get_weather_batch called with empty locations list")
            return pd.DataFrame()

        logger.info(
            f"Fetching weather data for {len(locations)} locations "
            f"from {date_debut.date()} to {date_fin.date()}"
        )

        all_data = []
        success_count = 0
        fail_count = 0

        for idx, loc in enumerate(locations, 1):
            # Validation des données de localisation
            if 'latitude' not in loc or 'longitude' not in loc:
                logger.warning(f"Location {idx}: Missing latitude or longitude, skipping")
                fail_count += 1
                continue

            try:
                lat = float(loc['latitude'])
                lon = float(loc['longitude'])
            except (ValueError, TypeError) as e:
                logger.warning(
                    f"Location {idx}: Invalid coordinate values "
                    f"(lat={loc.get('latitude')}, lon={loc.get('longitude')}), skipping"
                )
                fail_count += 1
                continue

            df = self.get_weather_data(
                lat,
                lon,
                date_debut,
                date_fin,
                variables
            )

            if not df.empty:
                # Ajouter identifiant station
                if 'code_station' in loc:
                    df['code_station'] = loc['code_station']
                df['latitude'] = lat
                df['longitude'] = lon

                all_data.append(df)
                success_count += 1
            else:
                fail_count += 1

            # Log progress every 10 locations
            if idx % 10 == 0:
                logger.info(
                    f"Progress: {idx}/{len(locations)} locations "
                    f"({success_count} success, {fail_count} failed)"
                )

        if not all_data:
            logger.warning("No weather data retrieved for any location")
            return pd.DataFrame()

        result = pd.concat(all_data, ignore_index=True)
        logger.info(
            f"Successfully retrieved weather data: {len(result)} total records "
            f"from {success_count}/{len(locations)} locations"
        )

        return result
